"""Unit tests for the stable scientific-domain package surface."""

from __future__ import annotations

import vascuquest.domain as domain
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation, VascularLocation
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, ValueState, Waveform
from vascuquest.domain.subject import VirtualSubject


EXPECTED_EXPORTS = {
    "Cohort": Cohort,
    "Coordinate": Coordinate,
    "DatasetIdentity": DatasetIdentity,
    "EvidenceClass": EvidenceClass,
    "MeasurementSite": MeasurementSite,
    "PathPosition": PathPosition,
    "QuantityDefinition": QuantityDefinition,
    "ScientificResult": ScientificResult,
    "SegmentLocation": SegmentLocation,
    "SubjectKey": SubjectKey,
    "ValidityState": ValidityState,
    "ValueState": ValueState,
    "VascularLocation": VascularLocation,
    "VirtualSubject": VirtualSubject,
    "Waveform": Waveform,
}


def test_domain_all_is_exact_and_deterministic() -> None:
    assert domain.__all__ == sorted(EXPECTED_EXPORTS)


def test_domain_exports_resolve_to_their_defining_types() -> None:
    for name, expected in EXPECTED_EXPORTS.items():
        assert getattr(domain, name) is expected


def test_domain_surface_does_not_expose_later_layers() -> None:
    forbidden = {
        "DatasetBackend",
        "DatasetSession",
        "ProvenanceRecord",
        "ResearchOperator",
        "SchemaProvider",
        "Typer",
        "open_dataset",
    }
    assert forbidden.isdisjoint(domain.__all__)
