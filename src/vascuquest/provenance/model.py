"""Immutable provenance values for reproducible scientific lineage.

The provenance model stores scientific identity and structured facts only.  It
never stores source-file paths, backend reader objects, or result arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation, VascularLocation
from vascuquest.domain.result import ValidityState, ValueState


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _optional_text(value: str | None, field_name: str) -> None:
    if value is not None:
        _required_text(value, field_name)


def _text_tuple(values: tuple[str, ...], field_name: str, *, unique: bool = True) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple of strings")
    seen: set[str] = set()
    for value in values:
        _required_text(value, field_name)
        if unique and value in seen:
            raise ValueError(f"{field_name} must not contain duplicate values")
        seen.add(value)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is not permitted")


@dataclass(frozen=True, slots=True)
class CanonicalJSON:
    """Canonical, immutable JSON value used for portable provenance facts."""

    text: str

    def __post_init__(self) -> None:
        _required_text(self.text, "text")
        try:
            value = json.loads(self.text, parse_constant=_reject_json_constant)
            canonical = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("text must encode a finite JSON value") from exc
        object.__setattr__(self, "text", canonical)

    @classmethod
    def from_value(cls, value: object) -> CanonicalJSON:
        """Create canonical JSON from a JSON-compatible Python value."""

        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise TypeError("value must be JSON-compatible and finite") from exc
        return cls(encoded)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CanonicalJSON:
        """Create canonical JSON from a mapping with string keys."""

        if not isinstance(value, Mapping):
            raise TypeError("value must be a mapping")
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON mapping keys must be strings")
        result = cls.from_value(dict(value))
        if not isinstance(result.value(), dict):
            raise TypeError("value must encode a JSON object")
        return result

    def value(self) -> object:
        """Return a fresh Python representation of this JSON value."""

        return json.loads(self.text, parse_constant=_reject_json_constant)


_EMPTY_JSON_OBJECT = CanonicalJSON("{}")


@dataclass(frozen=True, slots=True)
class SourceArtifactReference:
    """Canonical source-artifact identity used by scientific provenance."""

    artifact_id: str
    checksum_algorithm: str
    checksum_value: str

    def __post_init__(self) -> None:
        _required_text(self.artifact_id, "artifact_id")
        _required_text(self.checksum_algorithm, "checksum_algorithm")
        _required_text(self.checksum_value, "checksum_value")


@dataclass(frozen=True, slots=True)
class ComponentReference:
    """Scientific component implementation identity retained in provenance."""

    qualified_id: str
    implementation_version: str
    protocol_version: int | None = None
    distribution_name: str | None = None
    distribution_version: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.qualified_id, "qualified_id")
        _required_text(self.implementation_version, "implementation_version")
        if self.protocol_version is not None:
            if isinstance(self.protocol_version, bool) or not isinstance(self.protocol_version, int):
                raise TypeError("protocol_version must be an integer or None")
            if self.protocol_version < 1:
                raise ValueError("protocol_version must be positive")
        _optional_text(self.distribution_name, "distribution_name")
        _optional_text(self.distribution_version, "distribution_version")


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """One immutable completed-result provenance node with input lineage."""

    record_id: str
    dataset_identity: DatasetIdentity
    schema_version: str
    evidence: EvidenceClass
    validity: ValidityState = ValidityState.NOT_EVALUATED
    value_state: ValueState = ValueState.PRESENT
    source_artifacts: tuple[SourceArtifactReference, ...] = ()
    subject: SubjectKey | None = None
    cohort: Cohort | None = None
    location: VascularLocation | None = None
    source_fields: tuple[str, ...] = ()
    inputs: tuple[ProvenanceRecord, ...] = ()
    method_id: str | None = None
    component: ComponentReference | None = None
    parameters: CanonicalJSON = _EMPTY_JSON_OBJECT
    assumptions: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    random_state: CanonicalJSON | None = None
    environment: CanonicalJSON = _EMPTY_JSON_OBJECT
    warnings: tuple[str, ...] = ()
    output_identity: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.record_id, "record_id")
        if not isinstance(self.dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")
        _required_text(self.schema_version, "schema_version")
        if self.schema_version != self.dataset_identity.schema_version:
            raise ValueError("schema_version must match dataset_identity.schema_version")
        if not isinstance(self.evidence, EvidenceClass):
            raise TypeError("evidence must be an EvidenceClass")
        if not isinstance(self.validity, ValidityState):
            raise TypeError("validity must be a ValidityState")
        if not isinstance(self.value_state, ValueState):
            raise TypeError("value_state must be a ValueState")

        if not isinstance(self.source_artifacts, tuple):
            raise TypeError("source_artifacts must be a tuple")
        artifact_ids: set[str] = set()
        for artifact in self.source_artifacts:
            if not isinstance(artifact, SourceArtifactReference):
                raise TypeError("source_artifacts must contain SourceArtifactReference values")
            if artifact.artifact_id in artifact_ids:
                raise ValueError("source_artifacts must not contain duplicate artifact IDs")
            artifact_ids.add(artifact.artifact_id)

        if self.subject is not None:
            if not isinstance(self.subject, SubjectKey):
                raise TypeError("subject must be a SubjectKey")
            if self.subject.dataset_identity != self.dataset_identity:
                raise ValueError("subject dataset_identity must match provenance dataset_identity")
        if self.cohort is not None:
            if not isinstance(self.cohort, Cohort):
                raise TypeError("cohort must be a Cohort")
            if self.cohort.dataset_identity != self.dataset_identity:
                raise ValueError("cohort dataset_identity must match provenance dataset_identity")
        if self.subject is not None and self.cohort is not None:
            if self.subject.canonical_subject_id not in self.cohort.canonical_subject_ids:
                raise ValueError("subject must belong to cohort when both contexts are supplied")

        if self.location is not None and not isinstance(
            self.location, (SegmentLocation, MeasurementSite, PathPosition)
        ):
            raise TypeError("location must be a supported VascularLocation")

        _text_tuple(self.source_fields, "source_fields")
        if not isinstance(self.inputs, tuple):
            raise TypeError("inputs must be a tuple of ProvenanceRecord values")
        direct_input_ids: set[str] = set()
        for input_record in self.inputs:
            if not isinstance(input_record, ProvenanceRecord):
                raise TypeError("inputs must contain only ProvenanceRecord values")
            if input_record.dataset_identity != self.dataset_identity:
                raise ValueError("input provenance must use the same dataset identity in v1")
            if input_record.record_id == self.record_id:
                raise ValueError("provenance record cannot directly depend on itself")
            if input_record.record_id in direct_input_ids:
                raise ValueError("inputs must not contain duplicate provenance record IDs")
            direct_input_ids.add(input_record.record_id)

        _optional_text(self.method_id, "method_id")
        if self.evidence is not EvidenceClass.SOURCE and self.method_id is None:
            raise ValueError("non-SOURCE provenance must identify the producing method")
        if self.component is not None and not isinstance(self.component, ComponentReference):
            raise TypeError("component must be a ComponentReference")
        if not isinstance(self.parameters, CanonicalJSON):
            raise TypeError("parameters must be CanonicalJSON")
        if not isinstance(self.parameters.value(), dict):
            raise ValueError("parameters must encode a JSON object")
        _text_tuple(self.assumptions, "assumptions")
        _text_tuple(self.citations, "citations")
        if self.random_state is not None and not isinstance(self.random_state, CanonicalJSON):
            raise TypeError("random_state must be CanonicalJSON or None")
        if not isinstance(self.environment, CanonicalJSON):
            raise TypeError("environment must be CanonicalJSON")
        if not isinstance(self.environment.value(), dict):
            raise ValueError("environment must encode a JSON object")
        _text_tuple(self.warnings, "warnings")
        _optional_text(self.output_identity, "output_identity")

        _validate_acyclic(self)


def _validate_acyclic(root: ProvenanceRecord) -> None:
    """Reject cycles and conflicting reuse of one provenance record ID."""

    active: set[str] = set()
    seen: dict[str, ProvenanceRecord] = {}

    def visit(record: ProvenanceRecord) -> None:
        if record.record_id in active:
            raise ValueError("completed provenance lineage must be acyclic")
        previous = seen.get(record.record_id)
        if previous is not None:
            if previous is not record and previous != record:
                raise ValueError("one provenance record ID cannot identify different records")
            return
        seen[record.record_id] = record
        active.add(record.record_id)
        for input_record in record.inputs:
            visit(input_record)
        active.remove(record.record_id)

    visit(root)


__all__ = [
    "CanonicalJSON",
    "ComponentReference",
    "ProvenanceRecord",
    "SourceArtifactReference",
]
