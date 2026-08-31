from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.disease import (
    DiseaseCondition,
    DiseasePopulationRequest,
    DiseaseSpecification,
)
from vascuquest.errors import AdmissibilityError


def test_disease_specification_is_immutable_and_normalized() -> None:
    specification = DiseaseSpecification.from_mapping(
        DiseaseCondition.CAROTID_STENOSIS,
        {"z": 2, "a": 1.0},
    )
    assert specification.parameters == (("a", 1.0), ("z", 2))
    with pytest.raises(FrozenInstanceError):
        specification.preset_version = "changed"  # type: ignore[misc]


def test_disease_specification_rejects_non_scalar_parameter_values() -> None:
    with pytest.raises(AdmissibilityError):
        DiseaseSpecification.from_mapping(
            DiseaseCondition.CAROTID_STENOSIS,
            {"bad": [1, 2, 3]},
        )


def test_population_request_validates_count_age_and_seed() -> None:
    specification = DiseaseSpecification(DiseaseCondition.LARGE_ARTERY_STIFFENING)
    request = DiseasePopulationRequest(
        patients=10,
        age_group=65,
        specification=specification,
        seed=7,
    )
    assert request.patients == 10
    assert request.age_group == 65
    assert request.seed == 7

    with pytest.raises(ValueError):
        DiseasePopulationRequest(0, 65, specification)
    with pytest.raises(TypeError):
        DiseasePopulationRequest(True, 65, specification)  # type: ignore[arg-type]
