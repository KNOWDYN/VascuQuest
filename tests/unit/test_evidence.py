"""Unit tests for the scientific evidence classification."""

from __future__ import annotations

import json

import pytest

from vascuquest.domain.evidence import EvidenceClass


EXPECTED_EVIDENCE = (
    "SOURCE",
    "RECONSTRUCTED",
    "DERIVED",
    "INFERRED",
    "MODELLED",
)


def test_evidence_class_has_exactly_five_members() -> None:
    assert tuple(member.name for member in EvidenceClass) == EXPECTED_EVIDENCE
    assert tuple(member.value for member in EvidenceClass) == EXPECTED_EVIDENCE


def test_evidence_members_are_string_values() -> None:
    for member in EvidenceClass:
        assert isinstance(member, str)
        assert member.value == member.name


def test_evidence_class_round_trips_from_canonical_strings() -> None:
    for value in EXPECTED_EVIDENCE:
        assert EvidenceClass(value).value == value


def test_unknown_evidence_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        EvidenceClass("VALID")


def test_validity_and_admissibility_are_not_evidence_members() -> None:
    forbidden = {"VALID", "INVALID", "ADMISSIBLE", "INADMISSIBLE", "PLAUSIBLE"}
    assert forbidden.isdisjoint(EvidenceClass.__members__)


def test_evidence_serializes_as_its_canonical_string_value() -> None:
    encoded = json.dumps({"evidence": EvidenceClass.MODELLED})
    assert json.loads(encoded) == {"evidence": "MODELLED"}
