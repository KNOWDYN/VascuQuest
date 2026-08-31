from __future__ import annotations

import pytest

from vascuquest.disease.catalogue import preset, presets, specification
from vascuquest.disease.model import DiseaseCondition
from vascuquest.errors import AdmissibilityError


def test_frozen_catalogue_contains_exactly_four_conditions_in_enum_order() -> None:
    assert tuple(item.condition for item in presets()) == tuple(DiseaseCondition)
    assert len(presets()) == 4


def test_carotid_contract_normalizes_parameters_and_default_center() -> None:
    result = specification(
        "carotid_stenosis",
        {
            "side": "left",
            "artery": "internal_carotid",
            "nascet_stenosis": 0.70,
            "lesion_length_m": 0.012,
        },
    )
    values = result.parameter_mapping()
    assert values["side"] == "left"
    assert values["artery"] == "internal_carotid"
    assert values["nascet_stenosis"] == 0.70
    assert values["lesion_length_m"] == 0.012
    assert values["lesion_center_fraction"] == 0.5


def test_catalogue_rejects_unknown_condition_parameter_and_structural_bound() -> None:
    with pytest.raises(AdmissibilityError):
        preset("hypertension")

    with pytest.raises(AdmissibilityError):
        specification(
            "large_artery_stiffening",
            {"target_cfpwv_m_per_s": 10.0, "invented": 1},
        )

    with pytest.raises(AdmissibilityError):
        specification(
            "carotid_stenosis",
            {
                "side": "left",
                "artery": "internal_carotid",
                "nascet_stenosis": 1.1,
                "lesion_length_m": 0.01,
            },
        )
