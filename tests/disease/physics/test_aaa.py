from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.catalogue import specification
from vascuquest.disease.physics.transform import transform_disease
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network
from vascuquest.errors import AdmissibilityError


def test_fusiform_aaa_changes_only_supported_abdominal_aortic_path(
    vascular_baseline,
) -> None:
    options = SolverOptions(target_dx_m=0.02)
    healthy = build_network(vascular_baseline, options)
    request = specification(
        "fusiform_abdominal_aortic_aneurysm",
        {
            "maximum_diameter_m": 0.030,
            "aneurysm_length_m": 0.12,
            "aneurysm_center_fraction": 0.50,
        },
    )
    model = transform_disease(vascular_baseline, request, options=options)

    assert model.pressure_losses == ()
    assert model.modified_segment_ids
    assert set(model.modified_segment_ids) <= {"28", "35", "37", "39", "41"}
    assert "15" not in model.modified_segment_ids
    np.testing.assert_array_equal(
        model.network.mesh("15").reference_area_m2,
        healthy.mesh("15").reference_area_m2,
    )
    assert any(
        np.max(model.network.mesh(segment_id).reference_area_m2)
        > np.max(healthy.mesh(segment_id).reference_area_m2)
        for segment_id in model.modified_segment_ids
    )


def test_aaa_maximum_diameter_must_be_a_true_dilation(vascular_baseline) -> None:
    request = specification(
        "fusiform_abdominal_aortic_aneurysm",
        {
            "maximum_diameter_m": 0.010,
            "aneurysm_length_m": 0.10,
            "aneurysm_center_fraction": 0.50,
        },
    )
    with pytest.raises(AdmissibilityError):
        transform_disease(vascular_baseline, request)
