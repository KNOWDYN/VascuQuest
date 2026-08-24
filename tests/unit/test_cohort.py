"""Unit tests for reproducible virtual-subject cohorts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity


def _dataset() -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )


def _cohort(**overrides: object) -> Cohort:
    values: dict[str, object] = {
        "dataset_identity": _dataset(),
        "canonical_subject_ids": ("1", "2", "3"),
        "ordering_rule": "canonical_subject_id_ascending",
        "selection_specification": ("age=45",),
        "inclusion_filters": ("age=45",),
        "exclusion_filters": (),
        "plausibility_filter": "source_plausible=true",
        "creation_provenance_ref": "provenance:cohort:example",
    }
    values.update(overrides)
    return Cohort(**values)  # type: ignore[arg-type]


def test_cohort_preserves_dataset_selection_and_order() -> None:
    cohort = _cohort()

    assert cohort.dataset_identity == _dataset()
    assert cohort.canonical_subject_ids == ("1", "2", "3")
    assert cohort.ordering_rule == "canonical_subject_id_ascending"
    assert cohort.selection_specification == ("age=45",)
    assert cohort.inclusion_filters == ("age=45",)
    assert cohort.plausibility_filter == "source_plausible=true"
    assert cohort.creation_provenance_ref == "provenance:cohort:example"


def test_cohort_preserves_selection_order_without_inventing_sorting() -> None:
    cohort = _cohort(
        canonical_subject_ids=("3", "1", "2"),
        ordering_rule="source_selection_order",
    )

    assert cohort.canonical_subject_ids == ("3", "1", "2")
    assert cohort.ordering_rule == "source_selection_order"


def test_duplicate_subject_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError):
        _cohort(canonical_subject_ids=("1", "2", "1"))


def test_subject_identifiers_must_be_an_immutable_tuple() -> None:
    with pytest.raises(TypeError):
        _cohort(canonical_subject_ids=["1", "2"])  # type: ignore[list-item]


def test_cohort_requires_exact_dataset_identity() -> None:
    with pytest.raises(TypeError):
        _cohort(dataset_identity="pwdb:3275625")


def test_cohort_rejects_invalid_selection_metadata() -> None:
    with pytest.raises(ValueError):
        _cohort(ordering_rule="")

    with pytest.raises(ValueError):
        _cohort(selection_specification=(" age=45",))

    with pytest.raises(ValueError):
        _cohort(plausibility_filter="source_plausible=true ")

    with pytest.raises(ValueError):
        _cohort(creation_provenance_ref=" provenance:cohort:example")


def test_optional_filters_and_provenance_reference_may_be_absent() -> None:
    cohort = _cohort(plausibility_filter=None, creation_provenance_ref=None)

    assert cohort.plausibility_filter is None
    assert cohort.creation_provenance_ref is None


def test_cohort_is_immutable_and_hashable() -> None:
    cohort = _cohort()

    assert {cohort}
    with pytest.raises(FrozenInstanceError):
        cohort.ordering_rule = "changed"  # type: ignore[misc]
