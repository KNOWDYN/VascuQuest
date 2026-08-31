from __future__ import annotations

import pytest

from vascuquest.disease.model import DiseaseCondition
from vascuquest.disease.naming import disease_vector_name


def test_vector_names_are_disease_qualified_without_changing_alias() -> None:
    assert disease_vector_name("P", DiseaseCondition.CAROTID_STENOSIS) == (
        "P__vd_carotid_stenosis"
    )
    assert disease_vector_name("PPG", "large_artery_stiffening") == (
        "PPG__vd_large_artery_stiffening"
    )


def test_vector_names_are_unique_across_frozen_conditions() -> None:
    names = {disease_vector_name("P", condition) for condition in DiseaseCondition}
    assert len(names) == len(DiseaseCondition)


def test_vector_name_rejects_non_identifier_alias() -> None:
    with pytest.raises(ValueError):
        disease_vector_name("pressure signal", "carotid_stenosis")
