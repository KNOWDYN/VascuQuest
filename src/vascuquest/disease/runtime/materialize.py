"""Materialise one disease-transformed subject into VascuQuest result objects."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from vascuquest.api import DatasetSession
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, ValueState, Waveform
from vascuquest.domain.subject import VirtualSubject
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.baseline.model import BaselineCardiovascularState, MMHG_TO_PA
from vascuquest.disease.model import DiseaseQuantityStatus, DiseaseRunIdentity
from vascuquest.disease.naming import disease_vector_name
from vascuquest.disease.physics import DiseasePhysicsModel, transform_disease
from vascuquest.disease.solver.disease_finite_volume import DiseaseOneDSolver
from vascuquest.disease.solver.model import ForwardSolution, SolverOptions
from vascuquest.disease.validation.reconstruction import PWDB_COMMON_SITE_MODEL_LOCATIONS
from vascuquest.errors import NumericalMethodError
from vascuquest.provenance import ProvenanceRecord

from .geometry import RuntimeGeometrySegment
from .provenance import RUNTIME_METHOD_ID, build_runtime_provenance
from .quantities import canonical_quantity, status_mapping

_RUNTIME_WARNINGS = (
    "Virtual Disease output is MODELLED and is not a clinical observation.",
    "Healthy PWDB reconstruction thresholds remain unfrozen; disease output is not clinically validated.",
)

_ALIAS_BY_QUANTITY = {
    "pressure": "P",
    "flow_velocity": "U",
    "luminal_area": "A",
    "flow_rate": "Q",
    "age": "age",
    "heart_rate": "HR",
    "stroke_volume": "SV",
    "cardiac_output": "CO",
    "brachial_systolic_pressure": "SBP_b",
    "vascular_geometry": "geo",
}


@dataclass(frozen=True, slots=True, eq=False)
class RuntimeSubjectState:
    """Complete in-memory counterfactual state for one preserved PWDB subject ID."""

    subject: VirtualSubject
    baseline: BaselineCardiovascularState
    physics: DiseasePhysicsModel
    solution: ForwardSolution
    results: tuple[ScientificResult, ...]
    provenance_records: tuple[ProvenanceRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.subject, VirtualSubject):
            raise TypeError("subject must be a VirtualSubject")
        if not isinstance(self.baseline, BaselineCardiovascularState):
            raise TypeError("baseline must be a BaselineCardiovascularState")
        if not isinstance(self.physics, DiseasePhysicsModel):
            raise TypeError("physics must be a DiseasePhysicsModel")
        if not isinstance(self.solution, ForwardSolution):
            raise TypeError("solution must be a ForwardSolution")
        if self.subject.canonical_subject_id != self.baseline.canonical_subject_id:
            raise ValueError("runtime subject must preserve the parent canonical subject ID")
        if self.physics.baseline is not self.baseline:
            raise ValueError("physics must retain the exact assembled healthy parent state")
        if not isinstance(self.results, tuple) or any(
            not isinstance(item, ScientificResult) for item in self.results
        ):
            raise TypeError("results must be a tuple of ScientificResult values")
        if any(item.dataset_identity != self.subject.dataset_identity for item in self.results):
            raise ValueError("all runtime results must use the runtime dataset identity")
        if any(
            item.subject is not None
            and item.subject.canonical_subject_id != self.subject.canonical_subject_id
            for item in self.results
        ):
            raise ValueError("runtime result subject IDs must preserve parent subject identity")
        if not isinstance(self.provenance_records, tuple) or any(
            not isinstance(item, ProvenanceRecord) for item in self.provenance_records
        ):
            raise TypeError("provenance_records must contain ProvenanceRecord values")
        refs = {item.record_id for item in self.provenance_records}
        if any(item.provenance_ref not in refs for item in self.results):
            raise ValueError("every runtime result must resolve to retained provenance")

    def result(
        self,
        quantity: str,
        *,
        location: MeasurementSite | None = None,
    ) -> ScientificResult:
        matches = tuple(
            item
            for item in self.results
            if item.quantity.canonical_name == quantity and item.location == location
        )
        if len(matches) != 1:
            raise KeyError(
                f"runtime subject {self.subject.canonical_subject_id!r} has no unique "
                f"result for quantity={quantity!r}, location={location!r}"
            )
        return matches[0]


def _readonly(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    array.setflags(write=False)
    return array


def _output_identity(
    quantity: str,
    subject_id: str,
    location: MeasurementSite | None,
) -> str:
    base = f"{quantity}@subject:{subject_id}"
    if location is not None:
        base += f"@site:{location.canonical_site_id}"
    return base


def _source_label(quantity: str, run_identity: DiseaseRunIdentity) -> str:
    return disease_vector_name(
        _ALIAS_BY_QUANTITY[quantity],
        run_identity.request.specification.condition,
    )


def _provenance(
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject: SubjectKey,
    physics: DiseasePhysicsModel,
    options: SolverOptions,
    solution: ForwardSolution,
    quantity: str,
    status: DiseaseQuantityStatus,
    location: MeasurementSite | None = None,
    source_fields: tuple[str, ...] = (),
) -> ProvenanceRecord:
    definition = canonical_quantity(quantity)
    return build_runtime_provenance(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject,
        physics=physics,
        solver_options=options,
        diagnostics=solution.diagnostics,
        quantity_name=quantity,
        quantity_status=status,
        output_identity=_output_identity(
            quantity, subject.canonical_subject_id, location
        ),
        location=location,
        source_fields=source_fields,
        citations=definition.citations,
    )


def _scalar_result(
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject: SubjectKey,
    physics: DiseasePhysicsModel,
    options: SolverOptions,
    solution: ForwardSolution,
    quantity: str,
    value: float | int,
    status: DiseaseQuantityStatus,
    location: MeasurementSite | None = None,
) -> tuple[ScientificResult, ProvenanceRecord]:
    provenance = _provenance(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject,
        physics=physics,
        options=options,
        solution=solution,
        quantity=quantity,
        status=status,
        location=location,
        source_fields=(physics.baseline.source_configuration_member,),
    )
    definition = canonical_quantity(quantity)
    result = ScientificResult(
        dataset_identity=runtime_identity,
        quantity=definition,
        values=value,
        provenance_ref=provenance.record_id,
        source_unit=definition.canonical_unit,
        source_label=_source_label(quantity, run_identity),
        subject=subject,
        location=location,
        evidence=EvidenceClass.MODELLED,
        value_state=ValueState.PRESENT,
        validity=ValidityState.NOT_EVALUATED,
        warnings=_RUNTIME_WARNINGS,
        method_id=RUNTIME_METHOD_ID,
    )
    return result, provenance


def _resample_history(
    solution: ForwardSolution,
    segment_id: str,
    fraction: float,
    target_time_s: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    segment = solution.segment(segment_id)
    index = segment.spatial_index(fraction)
    source_time = np.asarray(solution.time_s, dtype=float)
    target_phase = np.asarray(target_time_s, dtype=float) - float(target_time_s[0])
    if target_phase[0] < -1e-12 or target_phase[-1] > source_time[-1] + 1e-10:
        raise NumericalMethodError("runtime output sampling grid lies outside the solved cardiac cycle")
    area = np.interp(target_phase, source_time, segment.area_m2[:, index])
    flow = np.interp(target_phase, source_time, segment.flow_m3_per_s[:, index])
    pressure = np.interp(target_phase, source_time, segment.pressure_pa[:, index])
    return _readonly(area), _readonly(flow), _readonly(pressure)


def _waveform_result(
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject: SubjectKey,
    physics: DiseasePhysicsModel,
    options: SolverOptions,
    solution: ForwardSolution,
    quantity: str,
    values: np.ndarray,
    location: MeasurementSite,
    time_s: np.ndarray,
    status: DiseaseQuantityStatus,
    segment_id: str,
) -> tuple[Waveform, ProvenanceRecord]:
    provenance = _provenance(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject,
        physics=physics,
        options=options,
        solution=solution,
        quantity=quantity,
        status=status,
        location=location,
        source_fields=(
            physics.baseline.aortic_inflow.source_identity,
            f"solver_segment:{segment_id}",
        ),
    )
    definition = canonical_quantity(quantity)
    mask = np.zeros(values.shape, dtype=bool)
    mask.setflags(write=False)
    result = Waveform(
        dataset_identity=runtime_identity,
        quantity=definition,
        values=_readonly(values),
        provenance_ref=provenance.record_id,
        dimensions=("time",),
        coordinates=(Coordinate("time", _readonly(time_s), unit="s"),),
        source_unit=definition.canonical_unit,
        source_label=_source_label(quantity, run_identity),
        subject=subject,
        location=location,
        evidence=EvidenceClass.MODELLED,
        value_state=ValueState.PRESENT,
        validity=ValidityState.NOT_EVALUATED,
        warnings=_RUNTIME_WARNINGS,
        method_id=RUNTIME_METHOD_ID,
        missing_mask=mask,
        padding_mask=mask,
    )
    return result, provenance


def _geometry_result(
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject: SubjectKey,
    physics: DiseasePhysicsModel,
    options: SolverOptions,
    solution: ForwardSolution,
    status: DiseaseQuantityStatus,
) -> tuple[ScientificResult, ProvenanceRecord]:
    baseline_segments = {item.segment_id: item for item in physics.baseline.segments}
    values: list[RuntimeGeometrySegment] = []
    for mesh in physics.network.meshes:
        segment = baseline_segments[mesh.segment_id]
        radius = np.sqrt(mesh.reference_area_m2 / math.pi)
        values.append(
            RuntimeGeometrySegment(
                segment_id=mesh.segment_id,
                inlet_node=segment.inlet_node,
                outlet_node=segment.outlet_node,
                length_m=segment.length_m,
                x_m=mesh.x_m,
                reference_radius_m=radius,
                reference_area_m2=mesh.reference_area_m2,
                beta_pa=mesh.beta_pa,
                source_gamma_pa_s_per_m=mesh.source_gamma_pa_s_per_m,
                peripheral_c=segment.peripheral_compliance_m3_per_pa,
                peripheral_r=segment.peripheral_resistance_pa_s_per_m3,
            )
        )
    provenance = _provenance(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject,
        physics=physics,
        options=options,
        solution=solution,
        quantity="vascular_geometry",
        status=status,
        source_fields=(physics.baseline.source_geometry_member,),
    )
    result = ScientificResult(
        dataset_identity=runtime_identity,
        quantity=canonical_quantity("vascular_geometry"),
        values=tuple(values),
        provenance_ref=provenance.record_id,
        dimensions=("segment",),
        coordinates=(Coordinate("segment", tuple(item.segment_id for item in values)),),
        source_label=_source_label("vascular_geometry", run_identity),
        subject=subject,
        evidence=EvidenceClass.MODELLED,
        value_state=ValueState.PRESENT,
        validity=ValidityState.NOT_EVALUATED,
        warnings=_RUNTIME_WARNINGS,
        method_id=RUNTIME_METHOD_ID,
    )
    return result, provenance


def materialize_subject(
    session: DatasetSession,
    *,
    runtime_identity: DatasetIdentity,
    run_identity: DiseaseRunIdentity,
    subject_id: str,
    assembler: PWDBBaselineAssembler,
    solver_options: SolverOptions | None = None,
) -> RuntimeSubjectState:
    """Fork, transform, solve and materialise one selected PWDB subject."""

    if not isinstance(session, DatasetSession):
        raise TypeError("session must be a DatasetSession")
    if not isinstance(runtime_identity, DatasetIdentity):
        raise TypeError("runtime_identity must be a DatasetIdentity")
    if not isinstance(run_identity, DiseaseRunIdentity):
        raise TypeError("run_identity must be a DiseaseRunIdentity")
    if subject_id not in run_identity.canonical_subject_ids:
        raise ValueError("subject_id is not a member of the disease run selection")
    if not isinstance(assembler, PWDBBaselineAssembler):
        raise TypeError("assembler must be a PWDBBaselineAssembler")
    options = SolverOptions() if solver_options is None else solver_options
    if not isinstance(options, SolverOptions):
        raise TypeError("solver_options must be SolverOptions or None")

    baseline = assembler.assemble(session, subject_id)
    physics = transform_disease(
        baseline,
        run_identity.request.specification,
        options=options,
    )
    solution = DiseaseOneDSolver(options).solve(
        baseline,
        physics.network,
        pressure_losses=physics.pressure_losses,
    )
    if not solution.diagnostics.converged:
        raise NumericalMethodError(
            f"disease runtime subject {subject_id!r} did not reach periodic convergence"
        )

    runtime_subject = VirtualSubject(SubjectKey(runtime_identity, subject_id))
    subject_key = runtime_subject.key
    statuses = status_mapping(run_identity.request.specification.condition)
    results: list[ScientificResult] = []
    provenance_records: list[ProvenanceRecord] = []

    for quantity, value in (
        ("age", baseline.age_years),
        ("heart_rate", baseline.heart_rate_bpm),
        ("stroke_volume", baseline.stroke_volume_ml),
        (
            "cardiac_output",
            baseline.heart_rate_bpm * baseline.stroke_volume_ml / 1000.0,
        ),
    ):
        result, record = _scalar_result(
            runtime_identity=runtime_identity,
            run_identity=run_identity,
            subject=subject_key,
            physics=physics,
            options=options,
            solution=solution,
            quantity=quantity,
            value=value,
            status=statuses[quantity],
        )
        results.append(result)
        provenance_records.append(record)

    geometry, geometry_provenance = _geometry_result(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject_key,
        physics=physics,
        options=options,
        solution=solution,
        status=statuses["vascular_geometry"],
    )
    results.append(geometry)
    provenance_records.append(geometry_provenance)

    target_time = np.asarray(baseline.aortic_inflow.time_s, dtype=float)
    brachial_pressure: np.ndarray | None = None
    for site_id, (segment_id, fraction) in PWDB_COMMON_SITE_MODEL_LOCATIONS.items():
        location = MeasurementSite(site_id)
        area, flow, pressure_pa = _resample_history(
            solution,
            segment_id,
            fraction,
            target_time,
        )
        pressure = pressure_pa / MMHG_TO_PA
        velocity = flow / area
        waveforms = {
            "pressure": pressure,
            "flow_velocity": velocity,
            "luminal_area": area,
            "flow_rate": flow,
        }
        for quantity, values in waveforms.items():
            result, record = _waveform_result(
                runtime_identity=runtime_identity,
                run_identity=run_identity,
                subject=subject_key,
                physics=physics,
                options=options,
                solution=solution,
                quantity=quantity,
                values=values,
                location=location,
                time_s=target_time,
                status=statuses[quantity],
                segment_id=segment_id,
            )
            results.append(result)
            provenance_records.append(record)
        if site_id == "Brachial":
            brachial_pressure = pressure

    if brachial_pressure is None:
        raise RuntimeError("canonical Brachial site is missing from runtime site mapping")
    brachial_location = MeasurementSite("Brachial")
    sbp, sbp_record = _scalar_result(
        runtime_identity=runtime_identity,
        run_identity=run_identity,
        subject=subject_key,
        physics=physics,
        options=options,
        solution=solution,
        quantity="brachial_systolic_pressure",
        value=float(np.max(brachial_pressure)),
        status=statuses["brachial_systolic_pressure"],
        location=brachial_location,
    )
    results.append(sbp)
    provenance_records.append(sbp_record)

    return RuntimeSubjectState(
        subject=runtime_subject,
        baseline=baseline,
        physics=physics,
        solution=solution,
        results=tuple(results),
        provenance_records=tuple(provenance_records),
    )


__all__ = ["RuntimeSubjectState", "materialize_subject"]
