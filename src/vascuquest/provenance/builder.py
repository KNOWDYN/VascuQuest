"""Deterministic construction of immutable provenance records."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation, VascularLocation
from vascuquest.domain.result import ValidityState, ValueState

from .model import (
    CanonicalJSON,
    ComponentReference,
    ProvenanceRecord,
    SourceArtifactReference,
)


def _dataset_payload(identity: DatasetIdentity) -> dict[str, str]:
    return {
        "dataset_family": identity.dataset_family,
        "record_id": identity.record_id,
        "persistent_identifier": identity.persistent_identifier,
        "schema_version": identity.schema_version,
    }


def _subject_payload(subject: SubjectKey | None) -> dict[str, object] | None:
    if subject is None:
        return None
    return {"canonical_subject_id": subject.canonical_subject_id}


def _cohort_payload(cohort: Cohort | None) -> dict[str, object] | None:
    if cohort is None:
        return None
    return {
        "canonical_subject_ids": list(cohort.canonical_subject_ids),
        "ordering_rule": cohort.ordering_rule,
        "selection_specification": list(cohort.selection_specification),
        "inclusion_filters": list(cohort.inclusion_filters),
        "exclusion_filters": list(cohort.exclusion_filters),
        "plausibility_filter": cohort.plausibility_filter,
        "creation_provenance_ref": cohort.creation_provenance_ref,
    }


def _location_payload(location: VascularLocation | None) -> dict[str, object] | None:
    if location is None:
        return None
    if isinstance(location, SegmentLocation):
        return {"kind": "segment", "canonical_segment_id": location.canonical_segment_id}
    if isinstance(location, MeasurementSite):
        return {"kind": "measurement_site", "canonical_site_id": location.canonical_site_id}
    if isinstance(location, PathPosition):
        return {
            "kind": "path_position",
            "canonical_path_id": location.canonical_path_id,
            "position_index": location.position_index,
        }
    raise TypeError("location must be a supported VascularLocation")


def _artifact_payload(reference: SourceArtifactReference) -> dict[str, str]:
    return {
        "artifact_id": reference.artifact_id,
        "checksum_algorithm": reference.checksum_algorithm,
        "checksum_value": reference.checksum_value,
    }


def _component_payload(reference: ComponentReference | None) -> dict[str, object] | None:
    if reference is None:
        return None
    return {
        "qualified_id": reference.qualified_id,
        "implementation_version": reference.implementation_version,
        "protocol_version": reference.protocol_version,
        "distribution_name": reference.distribution_name,
        "distribution_version": reference.distribution_version,
    }


def _sorted_text(values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, str) for value in normalized):
        raise TypeError("provenance text collections must contain only strings")
    return tuple(sorted(normalized))


def _record_fingerprint(
    *,
    dataset_identity: DatasetIdentity,
    evidence: EvidenceClass,
    validity: ValidityState,
    value_state: ValueState,
    source_artifacts: tuple[SourceArtifactReference, ...],
    subject: SubjectKey | None,
    cohort: Cohort | None,
    location: VascularLocation | None,
    source_fields: tuple[str, ...],
    inputs: tuple[ProvenanceRecord, ...],
    method_id: str | None,
    component: ComponentReference | None,
    parameters: CanonicalJSON,
    assumptions: tuple[str, ...],
    citations: tuple[str, ...],
    random_state: CanonicalJSON | None,
    environment: CanonicalJSON,
    warnings: tuple[str, ...],
    output_identity: str | None,
) -> str:
    payload = {
        "dataset_identity": _dataset_payload(dataset_identity),
        "schema_version": dataset_identity.schema_version,
        "evidence": evidence.value,
        "validity": validity.value,
        "value_state": value_state.value,
        "source_artifacts": [_artifact_payload(item) for item in source_artifacts],
        "subject": _subject_payload(subject),
        "cohort": _cohort_payload(cohort),
        "location": _location_payload(location),
        "source_fields": list(source_fields),
        "input_record_ids": [item.record_id for item in inputs],
        "method_id": method_id,
        "component": _component_payload(component),
        "parameters": parameters.value(),
        "assumptions": list(assumptions),
        "citations": list(citations),
        "random_state": None if random_state is None else random_state.value(),
        "environment": environment.value(),
        "warnings": list(warnings),
        "output_identity": output_identity,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ProvenanceBuilder:
    """Build deterministic provenance for one exact dataset identity."""

    __slots__ = ("_dataset_identity", "_environment")

    def __init__(
        self,
        dataset_identity: DatasetIdentity,
        *,
        environment: Mapping[str, object] | None = None,
    ) -> None:
        if not isinstance(dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")
        self._dataset_identity = dataset_identity
        self._environment = CanonicalJSON.from_mapping(environment or {})

    @property
    def dataset_identity(self) -> DatasetIdentity:
        """Exact dataset identity used by records created by this builder."""

        return self._dataset_identity

    def build(
        self,
        *,
        evidence: EvidenceClass,
        validity: ValidityState = ValidityState.NOT_EVALUATED,
        value_state: ValueState = ValueState.PRESENT,
        source_artifacts: Iterable[SourceArtifactReference] = (),
        subject: SubjectKey | None = None,
        cohort: Cohort | None = None,
        location: VascularLocation | None = None,
        source_fields: Iterable[str] = (),
        inputs: Iterable[ProvenanceRecord] = (),
        method_id: str | None = None,
        component: ComponentReference | None = None,
        parameters: Mapping[str, object] | None = None,
        assumptions: Iterable[str] = (),
        citations: Iterable[str] = (),
        random_state: object | None = None,
        warnings: Iterable[str] = (),
        output_identity: str | None = None,
    ) -> ProvenanceRecord:
        """Normalize facts and construct one content-addressed provenance record."""

        if not isinstance(evidence, EvidenceClass):
            raise TypeError("evidence must be an EvidenceClass")
        if not isinstance(validity, ValidityState):
            raise TypeError("validity must be a ValidityState")
        if not isinstance(value_state, ValueState):
            raise TypeError("value_state must be a ValueState")

        artifacts = tuple(sorted(tuple(source_artifacts), key=lambda item: item.artifact_id))
        input_records = tuple(sorted(tuple(inputs), key=lambda item: item.record_id))
        normalized_source_fields = _sorted_text(source_fields)
        normalized_assumptions = _sorted_text(assumptions)
        normalized_citations = _sorted_text(citations)
        normalized_warnings = _sorted_text(warnings)
        normalized_parameters = CanonicalJSON.from_mapping(parameters or {})
        normalized_random_state = (
            None if random_state is None else CanonicalJSON.from_value(random_state)
        )

        record_id = _record_fingerprint(
            dataset_identity=self._dataset_identity,
            evidence=evidence,
            validity=validity,
            value_state=value_state,
            source_artifacts=artifacts,
            subject=subject,
            cohort=cohort,
            location=location,
            source_fields=normalized_source_fields,
            inputs=input_records,
            method_id=method_id,
            component=component,
            parameters=normalized_parameters,
            assumptions=normalized_assumptions,
            citations=normalized_citations,
            random_state=normalized_random_state,
            environment=self._environment,
            warnings=normalized_warnings,
            output_identity=output_identity,
        )

        return ProvenanceRecord(
            record_id=record_id,
            dataset_identity=self._dataset_identity,
            schema_version=self._dataset_identity.schema_version,
            evidence=evidence,
            validity=validity,
            value_state=value_state,
            source_artifacts=artifacts,
            subject=subject,
            cohort=cohort,
            location=location,
            source_fields=normalized_source_fields,
            inputs=input_records,
            method_id=method_id,
            component=component,
            parameters=normalized_parameters,
            assumptions=normalized_assumptions,
            citations=normalized_citations,
            random_state=normalized_random_state,
            environment=self._environment,
            warnings=normalized_warnings,
            output_identity=output_identity,
        )


__all__ = ["ProvenanceBuilder"]
