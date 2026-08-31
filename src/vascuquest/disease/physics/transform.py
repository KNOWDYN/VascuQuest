"""Causal Virtual Disease v1 transformations of a healthy PWDB solver state."""

from __future__ import annotations

import math

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState, BaselineSegment
from vascuquest.disease.catalogue import preset
from vascuquest.disease.model import (
    DiseaseCondition,
    DiseaseSpecification,
    VIRTUAL_DISEASE_CONTRACT_VERSION,
)
from vascuquest.disease.solver.losses import LocalizedPressureLoss
from vascuquest.disease.solver.model import SegmentMesh, SolverOptions
from vascuquest.disease.solver.network import (
    NetworkDiscretization,
    ThinWallLaw,
    build_network,
    wall_eh_n_per_m,
    wall_gamma_source,
)
from vascuquest.errors import AdmissibilityError

from .anatomy import (
    AAA_PATH_SEGMENTS,
    LARGE_ARTERY_STIFFENING_SEGMENTS,
    LEFT_CAROTID_TRAVEL_PATH,
    LEFT_FEMORAL_TRAVEL_PATH,
    PWDB_116_ARTERY_MODEL_SOURCE,
    carotid_segment,
    iliac_segment,
)
from .model import DiseasePhysicsModel
from .stenosis import SEELEY_YOUNG_1976_DOI, young_seeley_excess_coefficients

PWDB_MODEL_DOI = "doi:10.1152/ajpheart.00218.2019"


def _segment(state: BaselineCardiovascularState, segment_id: str) -> BaselineSegment:
    for item in state.segments:
        if item.segment_id == segment_id:
            return item
    raise AdmissibilityError(
        f"PWDB baseline subject lacks required disease target segment {segment_id!r}"
    )


def _grid(segment: BaselineSegment, options: SolverOptions, target_dx_m: float) -> tuple[np.ndarray, np.ndarray]:
    dx_target = min(options.target_dx_m, float(target_dx_m))
    cells = max(
        options.minimum_cells_per_segment,
        int(math.ceil(segment.length_m / dx_target)),
    )
    edges = np.linspace(0.0, segment.length_m, cells + 1)
    return 0.5 * (edges[:-1] + edges[1:]), np.diff(edges)


def _baseline_radius(segment: BaselineSegment, x_m: np.ndarray) -> np.ndarray:
    fraction = x_m / segment.length_m
    return segment.inlet_radius_m + fraction * (
        segment.outlet_radius_m - segment.inlet_radius_m
    )


def _mesh_from_radius(
    state: BaselineCardiovascularState,
    segment: BaselineSegment,
    x_m: np.ndarray,
    dx_m: np.ndarray,
    radius_m: np.ndarray,
    *,
    beta_scale: float = 1.0,
) -> SegmentMesh:
    radius = np.asarray(radius_m, dtype=float)
    if radius.shape != x_m.shape or np.any(radius <= 0) or not np.all(np.isfinite(radius)):
        raise AdmissibilityError("disease transformation produced invalid arterial radius")
    if not math.isfinite(beta_scale) or beta_scale <= 0:
        raise AdmissibilityError("disease wall-stiffness scale must be positive and finite")
    area = math.pi * radius * radius
    eh = wall_eh_n_per_m(state, radius)
    beta = beta_scale * 4.0 * eh / (3.0 * radius)
    gamma = wall_gamma_source(state, radius)
    return SegmentMesh(
        segment_id=segment.segment_id,
        x_m=x_m,
        dx_m=dx_m,
        reference_area_m2=area,
        beta_pa=beta,
        source_gamma_pa_s_per_m=gamma,
    )


def _replace_meshes(
    network: NetworkDiscretization,
    replacements: dict[str, SegmentMesh],
) -> NetworkDiscretization:
    return NetworkDiscretization(
        tuple(replacements.get(mesh.segment_id, mesh) for mesh in network.meshes)
    )


def _raised_cosine(x_m: np.ndarray, start_m: float, end_m: float) -> np.ndarray:
    center = 0.5 * (start_m + end_m)
    half = 0.5 * (end_m - start_m)
    if half <= 0:
        raise AdmissibilityError("disease lesion length must be positive")
    shape = np.zeros_like(x_m, dtype=float)
    mask = (x_m >= start_m) & (x_m <= end_m)
    shape[mask] = 0.5 * (
        1.0 + np.cos(math.pi * (x_m[mask] - center) / half)
    )
    return shape


def _distributed_weights(
    x_m: np.ndarray,
    dx_m: np.ndarray,
    start_m: float,
    end_m: float,
) -> np.ndarray:
    left = x_m - 0.5 * dx_m
    right = x_m + 0.5 * dx_m
    overlap = np.maximum(0.0, np.minimum(right, end_m) - np.maximum(left, start_m))
    total = float(np.sum(overlap))
    if total <= 0:
        raise AdmissibilityError("disease lesion has no support on the solver mesh")
    weights = overlap / (dx_m * total)
    if not math.isclose(float(np.sum(weights * dx_m)), 1.0, rel_tol=1e-10, abs_tol=1e-12):
        raise RuntimeError("internal disease pressure-loss weighting failed normalization")
    return weights


def _canonical_specification(specification: DiseaseSpecification) -> DiseaseSpecification:
    if not isinstance(specification, DiseaseSpecification):
        raise TypeError("specification must be a DiseaseSpecification")
    if specification.preset_version != VIRTUAL_DISEASE_CONTRACT_VERSION:
        raise AdmissibilityError(
            f"unsupported disease preset version {specification.preset_version!r}"
        )
    return preset(specification.condition).specification(specification.parameter_mapping())


def _focal_stenosis(
    baseline: BaselineCardiovascularState,
    specification: DiseaseSpecification,
    options: SolverOptions,
    *,
    segment_id: str,
    severity_parameter: str,
) -> DiseasePhysicsModel:
    parameters = specification.parameter_mapping()
    severity = float(parameters[severity_parameter])
    lesion_length = float(parameters["lesion_length_m"])
    center_fraction = float(parameters["lesion_center_fraction"])
    if severity < 0 or severity >= 1.0:
        raise AdmissibilityError(
            f"{severity_parameter} must satisfy 0 <= severity < 1 for executable disease physics"
        )
    segment = _segment(baseline, segment_id)
    center = center_fraction * segment.length_m
    start = center - 0.5 * lesion_length
    end = center + 0.5 * lesion_length
    if start < 0 or end > segment.length_m:
        raise AdmissibilityError(
            "focal stenosis must fit entirely inside the selected PWDB arterial segment"
        )

    healthy_network = build_network(baseline, options)
    if severity == 0.0:
        return DiseasePhysicsModel(
            baseline=baseline,
            specification=specification,
            network=healthy_network,
            pressure_losses=(),
            modified_segment_ids=(),
            assumptions=(
                "Zero requested diameter stenosis is an exact causal no-op.",
                "The healthy cardiac inflow and all parent PWDB inputs are unchanged.",
            ),
            citations=(PWDB_MODEL_DOI, PWDB_116_ARTERY_MODEL_SOURCE, SEELEY_YOUNG_1976_DOI),
        )

    x, dx = _grid(segment, options, lesion_length / 24.0)
    radius0 = _baseline_radius(segment, x)
    shape = _raised_cosine(x, start, end)
    radius = radius0 * (1.0 - severity * shape)
    lesion_mesh = _mesh_from_radius(baseline, segment, x, dx, radius)
    network = _replace_meshes(healthy_network, {segment_id: lesion_mesh})

    nominal_radius = segment.radius_at(center_fraction)
    stenosis_radius = nominal_radius * (1.0 - severity)
    coefficients = young_seeley_excess_coefficients(
        nominal_diameter_m=2.0 * nominal_radius,
        stenosis_diameter_m=2.0 * stenosis_radius,
        lesion_length_m=lesion_length,
        blood_density_kg_per_m3=baseline.blood_density_kg_per_m3,
        blood_viscosity_pa_s=baseline.blood_viscosity_pa_s,
    )
    weights = _distributed_weights(x, dx, start, end)
    loss = LocalizedPressureLoss(
        segment_id=segment_id,
        weights_per_m=weights,
        linear_resistance_pa_s_per_m3=coefficients.linear_excess_pa_s_per_m3,
        quadratic_resistance_pa_s2_per_m6=coefficients.quadratic_pa_s2_per_m6,
        inertance_pa_s2_per_m3=0.0,
        model_id="seeley_young_1976_excess_viscous_separation",
        citation=SEELEY_YOUNG_1976_DOI,
    )
    return DiseasePhysicsModel(
        baseline=baseline,
        specification=specification,
        network=network,
        pressure_losses=(loss,),
        modified_segment_ids=(segment_id,),
        assumptions=(
            "The focal lumen reduction uses a smooth raised-cosine diameter profile.",
            "Young-Seeley excess viscous and separation losses supplement the native 1-D solver.",
            "The original empirical inertial term is not added because native 1-D momentum already contains fluid inertia.",
            "The healthy cardiac inflow, distal Windkessel beds and parent PWDB source state are unchanged.",
            "This is a mechanistic model intervention, not a clinical stenosis measurement or validation claim.",
        ),
        citations=(PWDB_MODEL_DOI, PWDB_116_ARTERY_MODEL_SOURCE, SEELEY_YOUNG_1976_DOI),
    )


def _aaa_path_offsets(baseline: BaselineCardiovascularState) -> tuple[dict[str, float], float]:
    offsets: dict[str, float] = {}
    cursor = 0.0
    for segment_id in AAA_PATH_SEGMENTS:
        offsets[segment_id] = cursor
        cursor += _segment(baseline, segment_id).length_m
    return offsets, cursor


def _fusiform_aaa(
    baseline: BaselineCardiovascularState,
    specification: DiseaseSpecification,
    options: SolverOptions,
) -> DiseasePhysicsModel:
    parameters = specification.parameter_mapping()
    maximum_diameter = float(parameters["maximum_diameter_m"])
    aneurysm_length = float(parameters["aneurysm_length_m"])
    center_fraction = float(parameters["aneurysm_center_fraction"])
    offsets, path_length = _aaa_path_offsets(baseline)
    center = center_fraction * path_length
    start = center - 0.5 * aneurysm_length
    end = center + 0.5 * aneurysm_length
    if start < 0 or end > path_length:
        raise AdmissibilityError(
            "fusiform AAA must fit entirely inside the frozen abdominal-aortic path"
        )

    maximum_baseline_radius = 0.0
    overlaps: dict[str, tuple[float, float]] = {}
    for segment_id in AAA_PATH_SEGMENTS:
        segment = _segment(baseline, segment_id)
        offset = offsets[segment_id]
        local_start = max(0.0, start - offset)
        local_end = min(segment.length_m, end - offset)
        if local_end <= local_start:
            continue
        overlaps[segment_id] = (local_start, local_end)
        for local_x in (local_start, local_end):
            maximum_baseline_radius = max(
                maximum_baseline_radius,
                segment.radius_at(local_x / segment.length_m),
            )
    target_radius = 0.5 * maximum_diameter
    if not overlaps:
        raise AdmissibilityError("AAA request has no support on the abdominal-aortic path")
    if target_radius <= maximum_baseline_radius:
        raise AdmissibilityError(
            "maximum_diameter_m must exceed the healthy diameter everywhere within the requested aneurysm region"
        )

    healthy_network = build_network(baseline, options)
    replacements: dict[str, SegmentMesh] = {}
    for segment_id, (local_start, local_end) in overlaps.items():
        segment = _segment(baseline, segment_id)
        x, dx = _grid(segment, options, aneurysm_length / 32.0)
        global_x = offsets[segment_id] + x
        shape = _raised_cosine(global_x, start, end)
        radius0 = _baseline_radius(segment, x)
        radius = radius0 + shape * (target_radius - radius0)
        replacements[segment_id] = _mesh_from_radius(
            baseline, segment, x, dx, radius
        )

    network = _replace_meshes(healthy_network, replacements)
    return DiseasePhysicsModel(
        baseline=baseline,
        specification=specification,
        network=network,
        pressure_losses=(),
        modified_segment_ids=tuple(
            segment_id for segment_id in AAA_PATH_SEGMENTS if segment_id in replacements
        ),
        assumptions=(
            "The aneurysm is an idealised smooth fusiform dilation over the frozen main abdominal-aortic path.",
            "The requested maximum diameter is an absolute model-space lumen diameter and must exceed the local healthy diameter.",
            "The 1-D model does not represent three-dimensional aneurysm vortices, recirculation or wall-thickness remodelling.",
            "The healthy cardiac inflow, terminal beds and parent PWDB source state are unchanged.",
        ),
        citations=(PWDB_MODEL_DOI, PWDB_116_ARTERY_MODEL_SOURCE),
    )


def _path_travel(
    network: NetworkDiscretization,
    baseline: BaselineCardiovascularState,
    path: tuple[tuple[str, float], ...],
) -> tuple[float, float]:
    distance = 0.0
    travel_time = 0.0
    rho = baseline.blood_density_kg_per_m3
    for segment_id, terminal_fraction in path:
        try:
            mesh = network.mesh(segment_id)
        except KeyError as exc:
            raise AdmissibilityError(
                f"baseline network lacks required cfPWV path segment {segment_id!r}"
            ) from exc
        segment_length = float(np.sum(mesh.dx_m))
        cutoff = terminal_fraction * segment_length
        left = mesh.x_m - 0.5 * mesh.dx_m
        right = mesh.x_m + 0.5 * mesh.dx_m
        overlap = np.maximum(0.0, np.minimum(right, cutoff) - np.maximum(left, 0.0))
        c0 = ThinWallLaw.wave_speed_m_per_s(
            mesh.reference_area_m2,
            mesh.reference_area_m2,
            mesh.beta_pa,
            rho,
        )
        distance += float(np.sum(overlap))
        travel_time += float(np.sum(overlap / c0))
    return distance, travel_time


def model_cfpwv_m_per_s(
    network: NetworkDiscretization,
    baseline: BaselineCardiovascularState,
) -> float:
    """Return differential characteristic PWV between left carotid/femoral paths."""

    carotid_distance, carotid_time = _path_travel(
        network, baseline, LEFT_CAROTID_TRAVEL_PATH
    )
    femoral_distance, femoral_time = _path_travel(
        network, baseline, LEFT_FEMORAL_TRAVEL_PATH
    )
    distance = femoral_distance - carotid_distance
    travel_time = femoral_time - carotid_time
    if distance <= 0 or travel_time <= 0:
        raise AdmissibilityError("PWDB topology produced a non-positive cfPWV path difference")
    return distance / travel_time


def _large_artery_stiffening(
    baseline: BaselineCardiovascularState,
    specification: DiseaseSpecification,
    options: SolverOptions,
) -> DiseasePhysicsModel:
    target = float(specification.parameter_mapping()["target_cfpwv_m_per_s"])
    healthy_network = build_network(baseline, options)
    baseline_cfpwv = model_cfpwv_m_per_s(healthy_network, baseline)
    tolerance = max(1e-10, 1e-10 * baseline_cfpwv)
    if target < baseline_cfpwv - tolerance:
        raise AdmissibilityError(
            f"large_artery_stiffening target {target:.6g} m/s is below the subject's model-space baseline {baseline_cfpwv:.6g} m/s"
        )
    scale = (target / baseline_cfpwv) ** 2
    if math.isclose(scale, 1.0, rel_tol=1e-12, abs_tol=1e-12):
        network = healthy_network
        modified: tuple[str, ...] = ()
    else:
        replacements: dict[str, SegmentMesh] = {}
        for mesh in healthy_network.meshes:
            if mesh.segment_id not in LARGE_ARTERY_STIFFENING_SEGMENTS:
                continue
            replacements[mesh.segment_id] = SegmentMesh(
                segment_id=mesh.segment_id,
                x_m=mesh.x_m,
                dx_m=mesh.dx_m,
                reference_area_m2=mesh.reference_area_m2,
                beta_pa=mesh.beta_pa * scale,
                source_gamma_pa_s_per_m=mesh.source_gamma_pa_s_per_m,
            )
        network = _replace_meshes(healthy_network, replacements)
        modified = tuple(
            mesh.segment_id
            for mesh in healthy_network.meshes
            if mesh.segment_id in replacements
        )
    achieved = model_cfpwv_m_per_s(network, baseline)
    if not math.isclose(achieved, target, rel_tol=1e-10, abs_tol=1e-10):
        raise RuntimeError("large-artery stiffness transform failed its target cfPWV invariant")
    return DiseasePhysicsModel(
        baseline=baseline,
        specification=specification,
        network=network,
        pressure_losses=(),
        modified_segment_ids=modified,
        assumptions=(
            "Target cfPWV is a model-space differential characteristic travel-time metric, not a simulated clinical tonometry procedure.",
            "Large-conduit beta stiffness is scaled uniformly by the square of the target-to-baseline model cfPWV ratio.",
            "Reference geometry and source Voigt wall-viscosity coefficients are unchanged.",
            "The healthy cardiac inflow, terminal beds and parent PWDB source state are unchanged.",
        ),
        citations=(PWDB_MODEL_DOI, PWDB_116_ARTERY_MODEL_SOURCE),
        baseline_cfpwv_m_per_s=baseline_cfpwv,
        target_cfpwv_m_per_s=target,
    )


def transform_disease(
    baseline: BaselineCardiovascularState,
    specification: DiseaseSpecification,
    *,
    options: SolverOptions | None = None,
) -> DiseasePhysicsModel:
    """Apply one frozen Virtual Disease v1 causal intervention to solver inputs."""

    if not isinstance(baseline, BaselineCardiovascularState):
        raise TypeError("baseline must be a BaselineCardiovascularState")
    resolved_options = SolverOptions() if options is None else options
    if not isinstance(resolved_options, SolverOptions):
        raise TypeError("options must be SolverOptions")
    canonical = _canonical_specification(specification)
    parameters = canonical.parameter_mapping()

    if canonical.condition is DiseaseCondition.CAROTID_STENOSIS:
        return _focal_stenosis(
            baseline,
            canonical,
            resolved_options,
            segment_id=carotid_segment(str(parameters["side"]), str(parameters["artery"])),
            severity_parameter="nascet_stenosis",
        )
    if canonical.condition is DiseaseCondition.ILIAC_STENOSIS:
        return _focal_stenosis(
            baseline,
            canonical,
            resolved_options,
            segment_id=iliac_segment(str(parameters["side"]), str(parameters["artery"])),
            severity_parameter="diameter_stenosis",
        )
    if canonical.condition is DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM:
        return _fusiform_aaa(baseline, canonical, resolved_options)
    if canonical.condition is DiseaseCondition.LARGE_ARTERY_STIFFENING:
        return _large_artery_stiffening(baseline, canonical, resolved_options)
    raise RuntimeError(f"unhandled frozen disease condition {canonical.condition.value!r}")


__all__ = ["model_cfpwv_m_per_s", "transform_disease"]
