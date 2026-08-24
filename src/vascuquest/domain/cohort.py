"""Immutable cohort definition for virtual-subject selections.

A cohort records a reproducible selection from one exact dataset identity. It
contains subject identities and normalized selection metadata only; it does
not copy subject data or interpret a virtual population as a real-human sample.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import DatasetIdentity


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _validate_text_tuple(values: tuple[str, ...], field_name: str, *, unique: bool = False) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple of strings")

    seen: set[str] = set()
    for value in values:
        _validate_text(value, field_name)
        if unique and value in seen:
            raise ValueError(f"{field_name} must not contain duplicate values")
        seen.add(value)


@dataclass(frozen=True, slots=True)
class Cohort:
    """Reproducible selection of virtual subjects from one dataset.

    ``canonical_subject_ids`` preserves the deterministic order established by
    the selection layer. ``ordering_rule`` records how that order was defined;
    this value object deliberately does not invent a sorting convention.

    Selection/filter fields contain normalized, serializable descriptions whose
    grammar is owned by the application/schema layer. ``creation_provenance_ref``
    is an opaque reference only: the domain does not import the later provenance
    implementation.
    """

    dataset_identity: DatasetIdentity
    canonical_subject_ids: tuple[str, ...]
    ordering_rule: str
    selection_specification: tuple[str, ...] = ()
    inclusion_filters: tuple[str, ...] = ()
    exclusion_filters: tuple[str, ...] = ()
    plausibility_filter: str | None = None
    creation_provenance_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")

        _validate_text_tuple(
            self.canonical_subject_ids,
            "canonical_subject_ids",
            unique=True,
        )
        _validate_text(self.ordering_rule, "ordering_rule")
        _validate_text_tuple(self.selection_specification, "selection_specification")
        _validate_text_tuple(self.inclusion_filters, "inclusion_filters")
        _validate_text_tuple(self.exclusion_filters, "exclusion_filters")

        if self.plausibility_filter is not None:
            _validate_text(self.plausibility_filter, "plausibility_filter")
        if self.creation_provenance_ref is not None:
            _validate_text(self.creation_provenance_ref, "creation_provenance_ref")


__all__ = ["Cohort"]
