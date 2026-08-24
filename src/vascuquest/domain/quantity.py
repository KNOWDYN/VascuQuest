"""Canonical scientific quantity definitions.

A quantity definition describes scientific meaning independently of any one
subject, numerical value, source file, or storage representation. Definitions
are populated from the versioned scientific schema rather than represented by
one Python class per haemodynamic variable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceClass


def _validate_required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _validate_optional_text(value: str | None, field_name: str) -> None:
    if value is None:
        return
    _validate_required_text(value, field_name)


def _validate_text_tuple(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple of strings")

    seen: set[str] = set()
    for value in values:
        _validate_required_text(value, field_name)
        if value in seen:
            raise ValueError(f"{field_name} must not contain duplicate values")
        seen.add(value)


@dataclass(frozen=True, slots=True)
class QuantityDefinition:
    """Immutable canonical definition of one scientific quantity.

    ``physical_dimension`` and ``canonical_unit`` may be ``None`` for
    non-dimensional categorical quantities. A dimensionless numerical
    quantity should instead use explicit schema values such as ``"dimensionless"``
    and ``"1"`` so absence is not confused with dimensionlessness.
    """

    canonical_name: str
    label: str
    description: str
    value_kind: str
    schema_version: str
    physical_dimension: str | None = None
    canonical_unit: str | None = None
    allowed_source_units: tuple[str, ...] = ()
    applicable_contexts: tuple[str, ...] = ()
    source_aliases: tuple[str, ...] = ()
    default_evidence: EvidenceClass = EvidenceClass.SOURCE
    known_source_issues: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_required_text(self.canonical_name, "canonical_name")
        _validate_required_text(self.label, "label")
        _validate_required_text(self.description, "description")
        _validate_required_text(self.value_kind, "value_kind")
        _validate_required_text(self.schema_version, "schema_version")
        _validate_optional_text(self.physical_dimension, "physical_dimension")
        _validate_optional_text(self.canonical_unit, "canonical_unit")
        _validate_text_tuple(self.allowed_source_units, "allowed_source_units")
        _validate_text_tuple(self.applicable_contexts, "applicable_contexts")
        _validate_text_tuple(self.source_aliases, "source_aliases")
        _validate_text_tuple(self.known_source_issues, "known_source_issues")
        _validate_text_tuple(self.citations, "citations")

        if not isinstance(self.default_evidence, EvidenceClass):
            raise TypeError("default_evidence must be an EvidenceClass")


__all__ = ["QuantityDefinition"]
