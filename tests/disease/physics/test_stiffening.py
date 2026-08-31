from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.catalogue import specification
from vascuquest.disease.physics.transform import model_cfpwv_m_per_s, transform_disease
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network
from vascuquest.errors import AdmissibilityError


def test_large_artery_stiffening_hits_model_cfpwv_target_without_geometry_change(
    vascular_baseline,
) -> None:
    options = SolverOptions(target_dx_m=0.02)
    healthy = build_network(vascular_baseline, options)
    baseline_cfpwv = model_cfpwv_m_per_s(healthy, vascular_baseline)
    target = 1.25 * baseline_cfpwv
    request = specification(
        "large_artery_stiffening",
        {"target_cfpwv_m_per_s": target},
    )
    model = transform_disease(vascular_baseline, request, options=options)

    assert model.baseline_cfpwv_m_per_s == pytest.approx(baseline_cfpwv)
    assert model.target_cfpwv_m_per_s == pytest.approx(target)
    assert model_cfpwv_m_per_s(model.network, vascular_baseline) == pytest.approx(target)
    assert model.modified_segment_ids
    for segment_id in model.modified_segment_ids:
        before = healthy.mesh(segment_id)
        after = model.network.mesh(segment_id)
        np.testing.assert_array_equal(before.reference_area_m2, after.reference_area_m2)
        np.testing.assert_array_equal(
            before.source_gamma_pa_s_per_m,
            after.source_gamma_pa_s_per_m,
        )
        assert np.all(after.beta_pa > before.beta_pa)


def test_large_artery_stiffening_rejects_softening_target(vascular_baseline) -> None:
    healthy = build_network(vascular_baseline)
    baseline_cfpwv = model_cfpwv_m_per_s(healthy, vascular_baseline)
    request = specification(
        "large_artery_stiffening",
        {"target_cfpwv_m_per_s": 0.90 * baseline_cfpwv},
    )
    with pytest.raises(AdmissibilityError):
        transform_disease(vascular_baseline, request)
