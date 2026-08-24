"""Unit tests for canonical scientific quantity definitions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.quantity import QuantityDefinition


def _quantity(**overrides: object) -> QuantityDefinition:
    values: dict[str, object] = {
        "canonical_name": "pressure",
        "label": "Pressure",
        "description": "Arterial pressure.",
        "value_kind": "numeric",
        "schema_version": "1",
        "physical_dimension": "pressure",
        "canonical_unit": "mmHg",
        "allowed_source_units": ("Pa", "mmHg"),
        "applicable_contexts": ("measurement_site", "path_position"),
        "source_aliases": ("P",),
        "default_evidence": EvidenceClass.SOURCE,
        "known_source_issues": (),
        "citations": ("authoritative-definition",),
    }
    values.update(overrides)
    return QuantityDefinition(**values)  # type: ignore[arg-type]


def test_quantity_definition_has_value_semantics() -> None:
    left = _quantity()
    right = _quantity()
    other = _quantity(canonical_name="flow_velocity", label="Flow velocity")

    assert left == right
    assert hash(left) == hash(right)
    assert left != other


def test_quantity_definition_preserves_schema_metadata() -> None:
    quantity = _quantity()

    assert quantity.canonical_name == "pressure"
    assert quantity.physical_dimension == "pressure"
    assert quantity.canonical_unit == "mmHg"
    assert quantity.allowed_source_units == ("Pa", "mmHg")
    assert quantity.applicable_contexts == ("measurement_site", "path_position")
    assert quantity.source_aliases == ("P",)
    assert quantity.default_evidence is EvidenceClass.SOURCE
    assert quantity.citations == ("authoritative-definition",)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("canonical_name", ""),
        ("label", " Pressure"),
        ("description", "Arterial pressure. "),
        ("value_kind", ""),
        ("schema_version", " 1"),
    ],
)
def test_required_text_fields_reject_empty_or_padded_values(field_name: str, value: str) -> None:
    with pytest.raises(ValueError):
        _quantity(**{field_name: value})


def test_required_text_fields_reject_non_string_values() -> None:
    with pytest.raises(TypeError):
        _quantity(canonical_name=1)


def test_optional_dimension_and_unit_distinguish_absence_from_dimensionless() -> None:
    categorical = _quantity(
        canonical_name="plausibility_state",
        label="Plausibility state",
        value_kind="categorical",
        physical_dimension=None,
        canonical_unit=None,
        allowed_source_units=(),
    )
    dimensionless = _quantity(
        canonical_name="dimensionless_index",
        label="Dimensionless index",
        physical_dimension="dimensionless",
        canonical_unit="1",
        allowed_source_units=("1",),
    )

    assert categorical.physical_dimension is None
    assert categorical.canonical_unit is None
    assert dimensionless.physical_dimension == "dimensionless"
    assert dimensionless.canonical_unit == "1"


@pytest.mark.parametrize(
    "field_name",
    [
        "allowed_source_units",
        "applicable_contexts",
        "source_aliases",
        "known_source_issues",
        "citations",
    ],
)
def test_collection_metadata_requires_immutable_tuples(field_name: str) -> None:
    with pytest.raises(TypeError):
        _quantity(**{field_name: ["value"]})


@pytest.mark.parametrize(
    "field_name",
    [
        "allowed_source_units",
        "applicable_contexts",
        "source_aliases",
        "known_source_issues",
        "citations",
    ],
)
def test_collection_metadata_rejects_duplicates(field_name: str) -> None:
    with pytest.raises(ValueError):
        _quantity(**{field_name: ("value", "value")})


def test_default_evidence_must_be_evidence_class() -> None:
    with pytest.raises(TypeError):
        _quantity(default_evidence="SOURCE")


def test_quantity_definition_is_immutable_and_hashable() -> None:
    quantity = _quantity()

    assert {quantity}
    with pytest.raises(FrozenInstanceError):
        quantity.canonical_unit = "Pa"  # type: ignore[misc]
