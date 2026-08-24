"""Immutable scientific identity value objects.

Identity in VascuQuest is independent of local paths, filenames, caches, and
source-reader implementation details. A virtual subject is identifiable only
within the exact dataset identity that contains it.
"""

from __future__ import annotations

from dataclasses import dataclass


def _validate_identity_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    """Exact identity of one virtual-population dataset and canonical schema."""

    dataset_family: str
    record_id: str
    persistent_identifier: str
    schema_version: str

    def __post_init__(self) -> None:
        _validate_identity_text(self.dataset_family, "dataset_family")
        _validate_identity_text(self.record_id, "record_id")
        _validate_identity_text(self.persistent_identifier, "persistent_identifier")
        _validate_identity_text(self.schema_version, "schema_version")


@dataclass(frozen=True, slots=True)
class SubjectKey:
    """Identity of one canonical virtual subject within an exact dataset."""

    dataset_identity: DatasetIdentity
    canonical_subject_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")
        _validate_identity_text(self.canonical_subject_id, "canonical_subject_id")


__all__ = ["DatasetIdentity", "SubjectKey"]
