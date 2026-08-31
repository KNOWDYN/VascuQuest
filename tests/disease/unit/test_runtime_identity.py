from __future__ import annotations

from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import DiseasePopulationRequest, DiseaseRunIdentity
from vascuquest.domain.identity import DatasetIdentity


def _identity() -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )


def test_run_identity_is_content_addressed_and_parameter_order_independent() -> None:
    first_spec = specification(
        "large_artery_stiffening", {"target_cfpwv_m_per_s": 11.0}
    )
    second_spec = specification(
        "large_artery_stiffening", {"target_cfpwv_m_per_s": 11.0}
    )
    first = DiseaseRunIdentity(
        _identity(),
        ("100", "200"),
        DiseasePopulationRequest(2, 65, first_spec, seed=3),
    )
    second = DiseaseRunIdentity(
        _identity(),
        ("100", "200"),
        DiseasePopulationRequest(2, 65, second_spec, seed=3),
    )
    assert first.run_id == second.run_id
    assert len(first.run_id) == 64


def test_run_identity_changes_when_request_changes() -> None:
    disease = specification(
        "large_artery_stiffening", {"target_cfpwv_m_per_s": 11.0}
    )
    first = DiseaseRunIdentity(
        _identity(),
        ("100", "200"),
        DiseasePopulationRequest(2, 65, disease, seed=3),
    )
    second = DiseaseRunIdentity(
        _identity(),
        ("100", "200"),
        DiseasePopulationRequest(2, 65, disease, seed=4),
    )
    assert first.run_id != second.run_id
