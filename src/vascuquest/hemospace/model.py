"""HEMOSPACE scientific record model.

HEMOSPACE records knowledge about one VascuQuest virtual simulation instance.
They are not patient charts and never convert a virtual subject into a human
participant. Every item states how it is known.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_ALLOWED_EVIDENCE = frozenset({"SOURCE", "RECONSTRUCTED", "DERIVED", "INFERRED", "MODELLED"})


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """One atomic HEMOSPACE statement with explicit epistemic status."""

    canonical_id: str
    label: str
    section: str
    value: Any
    unit: str | None
    evidence: str
    source_artifact: str | None = None
    source_field: str | None = None
    location: str | None = None
    method: str | None = None
    assumptions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value, name in ((self.canonical_id, "canonical_id"), (self.label, "label"), (self.section, "section")):
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a non-empty trimmed string")
        if self.evidence not in _ALLOWED_EVIDENCE:
            raise ValueError(f"unsupported HEMOSPACE evidence class {self.evidence!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "label": self.label,
            "section": self.section,
            "value": self.value,
            "unit": self.unit,
            "evidence": self.evidence,
            "source_artifact": self.source_artifact,
            "source_field": self.source_field,
            "location": self.location,
            "method": self.method,
            "assumptions": list(self.assumptions),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class UnavailableKnowledge:
    """A fact category HEMOSPACE explicitly refuses to invent."""

    canonical_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"canonical_id": self.canonical_id, "status": "NOT_KNOWABLE_FROM_PWDB", "reason": self.reason}


@dataclass(frozen=True, slots=True)
class KnowledgeCoverage:
    """Machine-auditable coverage of the source information used by a record."""

    source_fields_seen: int
    source_fields_exposed: int
    source_fields_missing: int
    source_tables: tuple[str, ...]
    derived_items: int
    geometry_included: bool
    waveform_summaries_included: bool

    @property
    def scalar_source_complete(self) -> bool:
        return self.source_fields_seen == self.source_fields_exposed + self.source_fields_missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_fields_seen": self.source_fields_seen,
            "source_fields_exposed": self.source_fields_exposed,
            "source_fields_missing": self.source_fields_missing,
            "source_tables": list(self.source_tables),
            "derived_items": self.derived_items,
            "geometry_included": self.geometry_included,
            "waveform_summaries_included": self.waveform_summaries_included,
            "scalar_source_complete": self.scalar_source_complete,
        }


@dataclass(frozen=True, slots=True)
class VirtualCardiovascularRecord:
    """Comprehensive, provenance-aware cardiovascular record for one virtual subject."""

    dataset_family: str
    dataset_record_id: str
    dataset_identifier: str
    subject_id: str
    depth: str
    items: tuple[KnowledgeItem, ...]
    unavailable: tuple[UnavailableKnowledge, ...]
    coverage: KnowledgeCoverage
    warnings: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "hemospace-1"

    def sections(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in self.items:
            grouped.setdefault(item.section, []).append(item.to_dict())
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "vascuquest.hemospace.virtual_cardiovascular_record",
            "schema_version": self.schema_version,
            "dataset": {
                "family": self.dataset_family,
                "record_id": self.dataset_record_id,
                "persistent_identifier": self.dataset_identifier,
            },
            "subject_id": self.subject_id,
            "depth": self.depth,
            "sections": self.sections(),
            "coverage": self.coverage.to_dict(),
            "unavailable_information": [entry.to_dict() for entry in self.unavailable],
            "warnings": list(self.warnings),
        }


__all__ = [
    "KnowledgeCoverage",
    "KnowledgeItem",
    "UnavailableKnowledge",
    "VirtualCardiovascularRecord",
]
