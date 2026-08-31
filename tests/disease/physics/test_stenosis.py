from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.catalogue import specification
from vascuquest.disease.physics.stenosis import young_seeley_excess_coefficients
from vascuquest.disease.physics.transform import transform_disease
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network
from vascuquest.errors import AdmissibilityError


def test_young_seeley_excess_is_exact_noop_without_narrowing() -> None:
    coefficients = young_seeley_excess_coefficients(
        nominal_diameter_m=0.008,
        stenosis_diameter_m=0.008,
        lesion_length_m=0.02,
        blood_density_kg_per_m3=1050.0,
        blood_viscosity_pa_s=0.004,
    )
    assert coefficients.linear_excess_pa_s_per_m3 == pytest.approx(0.0)
    assert coefficients.quadratic_pa_s2_per_m6 == pytest.approx(0.0)
    assert coefficients.pressure_drop_pa(5.0e-6) == pytest.approx(0.0)


def test_young_seeley_excess_opposes_flow_and_grows_with_stenosis() -> None:
    mild = young_seeley_excess_coefficients(
        nominal_diameter_m=0.008,
        stenosis_diameter_m=0.0064,
        lesion_length_m=0.02,
        blood_density_kg_per_m3=1050.0,
        blood_viscosity_pa_s=0.004,
    )
    severe = young_seeley_excess_coefficients(
        nominal_diameter_m=0.008,
        stenosis_diameter_m=0.0032,
        lesion_length_m=0.02,
        blood_density_kg_per_m3=1050.0,
        blood_viscosity_pa_s=0.004,
    )
    q = 5.0e-6
    assert mild.pressure_drop_pa(q) > 0
    assert mild.pressure_drop_pa(-q) == pytest.approx(-mild.pressure_drop_pa(q))
    assert severe.pressure_drop_pa(q) > mild.pressure_drop_pa(q)


def test_carotid_stenosis_changes_only_target_solver_mesh_and_adds_loss(
    vascular_baseline,
) -> None:
    options = SolverOptions(target_dx_m=0.02)
    healthy = build_network(vascular_baseline, options)
    original_radius = next(
        item.inlet_radius_m for item in vascular_baseline.segments if item.segment_id == "15"
    )
    request = specification(
        "carotid_stenosis",
        {
            "side": "left",
            "artery": "common_carotid",
            "nascet_stenosis": 0.60,
            "lesion_length_m": 0.04,
        },
    )
    model = transform_disease(vascular_baseline, request, options=options)

    assert model.modified_segment_ids == ("15",)
    assert len(model.pressure_losses) == 1
    loss = model.pressure_losses[0]
    assert loss.segment_id == "15"
    assert np.sum(loss.weights_per_m * model.network.mesh("15").dx_m) == pytest.approx(1.0)
    assert np.min(model.network.mesh("15").reference_area_m2) < np.min(
        healthy.mesh("15").reference_area_m2
    )
    np.testing.assert_array_equal(
        model.network.mesh("1").reference_area_m2,
        healthy.mesh("1").reference_area_m2,
    )
    assert next(
        item.inlet_radius_m for item in vascular_baseline.segments if item.segment_id == "15"
    ) == original_radius


def test_zero_carotid_stenosis_is_a_causal_noop(vascular_baseline) -> None:
    options = SolverOptions(target_dx_m=0.02)
    healthy = build_network(vascular_baseline, options)
    request = specification(
        "carotid_stenosis",
        {
            "side": "left",
            "artery": "common_carotid",
            "nascet_stenosis": 0.0,
            "lesion_length_m": 0.04,
        },
    )
    model = transform_disease(vascular_baseline, request, options=options)
    assert model.modified_segment_ids == ()
    assert model.pressure_losses == ()
    for source, transformed in zip(healthy.meshes, model.network.meshes, strict=True):
        np.testing.assert_array_equal(source.reference_area_m2, transformed.reference_area_m2)
        np.testing.assert_array_equal(source.beta_pa, transformed.beta_pa)


def test_complete_occlusion_is_outside_executable_v1_stenosis_domain(
    vascular_baseline,
) -> None:
    request = specification(
        "carotid_stenosis",
        {
            "side": "left",
            "artery": "common_carotid",
            "nascet_stenosis": 1.0,
            "lesion_length_m": 0.04,
        },
    )
    with pytest.raises(AdmissibilityError):
        transform_disease(vascular_baseline, request)
