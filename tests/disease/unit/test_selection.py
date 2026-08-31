from __future__ import annotations

import pytest

from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import DiseasePopulationRequest
from vascuquest.disease.selection import select_population
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.errors import SelectionError


class _FakeSession:
    def __init__(self, identity: DatasetIdentity, subject_ids: tuple[str, ...]) -> None:
        self._identity = identity
        self._subject_ids = subject_ids

    @property
    def identity(self) -> DatasetIdentity:
        return self._identity

    def select(self, *, subject_ids: object | None = None, where: object | None = None) -> Cohort:
        assert subject_ids is None
        assert where == {"age": 65}
        return Cohort(
            dataset_identity=self._identity,
            canonical_subject_ids=self._subject_ids,
            ordering_rule="canonical_backend_subject_order",
            inclusion_filters=("age=65",),
        )


def _identity() -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )


def _request(patients: int = 3, seed: int = 7) -> DiseasePopulationRequest:
    return DiseasePopulationRequest(
        patients=patients,
        age_group=65,
        specification=specification(
            "large_artery_stiffening", {"target_cfpwv_m_per_s": 11.0}
        ),
        seed=seed,
    )


def test_selection_is_deterministic_without_replacement_and_preserves_order() -> None:
    subject_ids = ("10", "20", "30", "40", "50", "60")
    session = _FakeSession(_identity(), subject_ids)

    first = select_population(session, _request())
    second = select_population(session, _request())

    assert first.cohort.canonical_subject_ids == second.cohort.canonical_subject_ids
    assert first.run_identity.run_id == second.run_identity.run_id
    assert len(first.cohort.canonical_subject_ids) == 3
    assert len(set(first.cohort.canonical_subject_ids)) == 3
    positions = [subject_ids.index(item) for item in first.cohort.canonical_subject_ids]
    assert positions == sorted(positions)
    assert first.run_identity.canonical_subject_ids == first.cohort.canonical_subject_ids


def test_selection_rejects_request_larger_than_eligible_age_cohort() -> None:
    session = _FakeSession(_identity(), ("10", "20"))
    with pytest.raises(SelectionError):
        select_population(session, _request(patients=3))


def test_selection_seed_participates_in_run_identity() -> None:
    session = _FakeSession(_identity(), ("10", "20", "30", "40", "50", "60"))
    first = select_population(session, _request(seed=1))
    second = select_population(session, _request(seed=2))
    assert first.run_identity.run_id != second.run_identity.run_id
