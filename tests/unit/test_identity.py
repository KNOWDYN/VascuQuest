"""Unit tests for storage-independent dataset and subject identity."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.identity import DatasetIdentity, SubjectKey


def _dataset(*, record_id: str = "3275625") -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id=record_id,
        persistent_identifier=f"10.5281/zenodo.{record_id}",
        schema_version="1",
    )


def test_dataset_identity_has_value_semantics() -> None:
    left = _dataset()
    right = _dataset()
    other = _dataset(record_id="9999999")

    assert left == right
    assert hash(left) == hash(right)
    assert left != other


def test_subject_key_identity_includes_dataset_identity() -> None:
    canonical_subject_id = "1"

    canonical = SubjectKey(_dataset(), canonical_subject_id)
    other_dataset = SubjectKey(_dataset(record_id="9999999"), canonical_subject_id)

    assert canonical != other_dataset
    assert canonical.dataset_identity == _dataset()
    assert canonical.canonical_subject_id == canonical_subject_id


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("dataset_family", ""),
        ("record_id", " 3275625"),
        ("persistent_identifier", "10.5281/zenodo.3275625 "),
        ("schema_version", ""),
    ],
)
def test_dataset_identity_rejects_invalid_text(field_name: str, value: str) -> None:
    values = {
        "dataset_family": "PWDB",
        "record_id": "3275625",
        "persistent_identifier": "10.5281/zenodo.3275625",
        "schema_version": "1",
    }
    values[field_name] = value

    with pytest.raises(ValueError):
        DatasetIdentity(**values)


def test_dataset_identity_rejects_non_string_fields() -> None:
    with pytest.raises(TypeError):
        DatasetIdentity(
            dataset_family="PWDB",
            record_id=3275625,  # type: ignore[arg-type]
            persistent_identifier="10.5281/zenodo.3275625",
            schema_version="1",
        )


def test_subject_key_validates_dataset_and_subject_identifier() -> None:
    with pytest.raises(TypeError):
        SubjectKey("pwdb:3275625", "1")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        SubjectKey(_dataset(), " 1")


def test_identity_objects_are_immutable_and_hashable() -> None:
    dataset = _dataset()
    subject = SubjectKey(dataset, "1")

    assert {dataset}
    assert {subject}

    with pytest.raises(FrozenInstanceError):
        dataset.record_id = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        subject.canonical_subject_id = "changed"  # type: ignore[misc]
