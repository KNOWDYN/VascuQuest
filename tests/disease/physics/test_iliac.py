from __future__ import annotations

import numpy as np

from vascuquest.disease.catalogue import specification
from vascuquest.disease.physics.transform import transform_disease
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network


def test_iliac_stenosis_executes_on_frozen_common_iliac_target(vascular_baseline) -> None:
    options = SolverOptions(target_dx_m=0.02)
    healthy = build_network(vascular_baseline, options)
    request = specification(
        "iliac_stenosis",
        {
            "side": "left",
            "artery": "common_iliac",
            "diameter_stenosis": 0.50,
            "lesion_length_m": 0.02,
        },
    )
    model = transform_disease(vascular_baseline, request, options=options)

    assert model.modified_segment_ids == ("42",)
    assert model.pressure_losses[0].segment_id == "42"
    assert np.min(model.network.mesh("42").reference_area_m2) < np.min(
        healthy.mesh("42").reference_area_m2
    )
    np.testing.assert_array_equal(
        model.network.mesh("44").reference_area_m2,
        healthy.mesh("44").reference_area_m2,
    )
