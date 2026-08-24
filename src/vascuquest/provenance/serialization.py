"""Deterministic provenance and scientific-result metadata serialization."""

from __future__ import annotations

import json
from typing import Any, Mapping

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation, VascularLocation
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import (
    Coordinate,
    ScientificResult,
    ValidityState,
    ValueState,
    Waveform,
)
from vascuquest.errors import ReproducibilityError

from .model import (
    CanonicalJSON,
    ComponentReference,
    ProvenanceRecord,
    SourceArtifactReference,
)


_PROVENANCE_FORMAT_VERSION = 1
_RESULT_METADATA_FORMAT_VERSION = 1


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReproducibilityError(f"{field_name} must be a mapping")
    return value


def _array(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReproducibilityError(f"{field_name} must be a JSON array")
    return value


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReproducibilityError(f"{field_name} must be a non-empty trimmed string")
    return value


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _array(value, field_name)
    result = tuple(_text(item, field_name) for item in items)
    if len(set(result)) != len(result):
        raise ReproducibilityError(f"{field_name} must not contain duplicates")
    return result


def _dataset_to_dict(identity: DatasetIdentity) -> dict[str, str]:
    return {
        "dataset_family": identity.dataset_family,
        "record_id": identity.record_id,
        "persistent_identifier": identity.persistent_identifier,
        "schema_version": identity.schema_version,
    }


def _dataset_from_dict(payload: object) -> DatasetIdentity:
    item = _mapping(payload, "dataset_identity")
    try:
        return DatasetIdentity(
            dataset_family=_text(item.get("dataset_family"), "dataset_family"),
            record_id=_text(item.get("record_id"), "record_id"),
            persistent_identifier=_text(
                item.get("persistent_identifier"), "persistent_identifier"
            ),
            schema_version=_text(item.get("schema_version"), "schema_version"),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid dataset identity in serialized metadata") from exc


def _subject_to_dict(subject: SubjectKey | None) -> dict[str, str] | None:
    if subject is None:
        return None
    return {"canonical_subject_id": subject.canonical_subject_id}


def _subject_from_dict(payload: object, dataset_identity: DatasetIdentity) -> SubjectKey | None:
    if payload is None:
        return None
    item = _mapping(payload, "subject")
    try:
        return SubjectKey(
            dataset_identity,
            _text(item.get("canonical_subject_id"), "canonical_subject_id"),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid subject context in serialized metadata") from exc


def _cohort_to_dict(cohort: Cohort | None) -> dict[str, object] | None:
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


def _cohort_from_dict(payload: object, dataset_identity: DatasetIdentity) -> Cohort | None:
    if payload is None:
        return None
    item = _mapping(payload, "cohort")
    try:
        return Cohort(
            dataset_identity=dataset_identity,
            canonical_subject_ids=_text_tuple(
                item.get("canonical_subject_ids"), "canonical_subject_ids"
            ),
            ordering_rule=_text(item.get("ordering_rule"), "ordering_rule"),
            selection_specification=_text_tuple(
                item.get("selection_specification"), "selection_specification"
            ),
            inclusion_filters=_text_tuple(
                item.get("inclusion_filters"), "inclusion_filters"
            ),
            exclusion_filters=_text_tuple(
                item.get("exclusion_filters"), "exclusion_filters"
            ),
            plausibility_filter=_optional_text(
                item.get("plausibility_filter"), "plausibility_filter"
            ),
            creation_provenance_ref=_optional_text(
                item.get("creation_provenance_ref"), "creation_provenance_ref"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid cohort context in serialized metadata") from exc


def _location_to_dict(location: VascularLocation | None) -> dict[str, object] | None:
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
    raise TypeError("unsupported VascularLocation")


def _location_from_dict(payload: object) -> VascularLocation | None:
    if payload is None:
        return None
    item = _mapping(payload, "location")
    kind = _text(item.get("kind"), "location.kind")
    try:
        if kind == "segment":
            return SegmentLocation(_text(item.get("canonical_segment_id"), "canonical_segment_id"))
        if kind == "measurement_site":
            return MeasurementSite(_text(item.get("canonical_site_id"), "canonical_site_id"))
        if kind == "path_position":
            position_index = item.get("position_index")
            if isinstance(position_index, bool) or not isinstance(position_index, int):
                raise ReproducibilityError("position_index must be an integer")
            return PathPosition(
                _text(item.get("canonical_path_id"), "canonical_path_id"),
                position_index,
            )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid vascular location in serialized metadata") from exc
    raise ReproducibilityError(f"unknown vascular location kind {kind!r}")


def _artifact_to_dict(reference: SourceArtifactReference) -> dict[str, str]:
    return {
        "artifact_id": reference.artifact_id,
        "checksum_algorithm": reference.checksum_algorithm,
        "checksum_value": reference.checksum_value,
    }


def _artifact_from_dict(payload: object) -> SourceArtifactReference:
    item = _mapping(payload, "source_artifact")
    try:
        return SourceArtifactReference(
            artifact_id=_text(item.get("artifact_id"), "artifact_id"),
            checksum_algorithm=_text(item.get("checksum_algorithm"), "checksum_algorithm"),
            checksum_value=_text(item.get("checksum_value"), "checksum_value"),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid source artifact reference") from exc


def _component_to_dict(reference: ComponentReference | None) -> dict[str, object] | None:
    if reference is None:
        return None
    return {
        "qualified_id": reference.qualified_id,
        "implementation_version": reference.implementation_version,
        "protocol_version": reference.protocol_version,
        "distribution_name": reference.distribution_name,
        "distribution_version": reference.distribution_version,
    }


def _component_from_dict(payload: object) -> ComponentReference | None:
    if payload is None:
        return None
    item = _mapping(payload, "component")
    protocol_version = item.get("protocol_version")
    if protocol_version is not None and (
        isinstance(protocol_version, bool) or not isinstance(protocol_version, int)
    ):
        raise ReproducibilityError("component protocol_version must be an integer or null")
    try:
        return ComponentReference(
            qualified_id=_text(item.get("qualified_id"), "qualified_id"),
            implementation_version=_text(
                item.get("implementation_version"), "implementation_version"
            ),
            protocol_version=protocol_version,
            distribution_name=_optional_text(
                item.get("distribution_name"), "distribution_name"
            ),
            distribution_version=_optional_text(
                item.get("distribution_version"), "distribution_version"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid component reference") from exc


def _record_to_node(record: ProvenanceRecord) -> dict[str, object]:
    return {
        "record_id": record.record_id,
        "dataset_identity": _dataset_to_dict(record.dataset_identity),
        "schema_version": record.schema_version,
        "evidence": record.evidence.value,
        "validity": record.validity.value,
        "value_state": record.value_state.value,
        "source_artifacts": [_artifact_to_dict(item) for item in record.source_artifacts],
        "subject": _subject_to_dict(record.subject),
        "cohort": _cohort_to_dict(record.cohort),
        "location": _location_to_dict(record.location),
        "source_fields": list(record.source_fields),
        "input_record_ids": [item.record_id for item in record.inputs],
        "method_id": record.method_id,
        "component": _component_to_dict(record.component),
        "parameters": record.parameters.value(),
        "assumptions": list(record.assumptions),
        "citations": list(record.citations),
        "random_state": None if record.random_state is None else record.random_state.value(),
        "environment": record.environment.value(),
        "warnings": list(record.warnings),
        "output_identity": record.output_identity,
    }


def _collect_records(root: ProvenanceRecord) -> dict[str, ProvenanceRecord]:
    records: dict[str, ProvenanceRecord] = {}
    active: set[str] = set()

    def visit(record: ProvenanceRecord) -> None:
        if record.record_id in active:
            raise ReproducibilityError("completed provenance lineage must be acyclic")
        previous = records.get(record.record_id)
        if previous is not None:
            if previous is not record and previous != record:
                raise ReproducibilityError(
                    "one provenance record ID cannot identify different records"
                )
            return
        records[record.record_id] = record
        active.add(record.record_id)
        for input_record in record.inputs:
            visit(input_record)
        active.remove(record.record_id)

    visit(root)
    return records


def provenance_to_dict(record: ProvenanceRecord) -> dict[str, object]:
    """Flatten one completed provenance DAG into deterministic structured data."""

    if not isinstance(record, ProvenanceRecord):
        raise TypeError("record must be a ProvenanceRecord")
    records = _collect_records(record)
    return {
        "format_version": _PROVENANCE_FORMAT_VERSION,
        "root_record_id": record.record_id,
        "records": [_record_to_node(records[key]) for key in sorted(records)],
    }


def provenance_to_json(record: ProvenanceRecord) -> str:
    """Serialize provenance using deterministic JSON ordering and encoding."""

    return json.dumps(
        provenance_to_dict(record),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _enum_value(enum_type: type[EvidenceClass] | type[ValidityState] | type[ValueState], value: object, field_name: str) -> Any:
    text = _text(value, field_name)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise ReproducibilityError(f"unknown {field_name} value {text!r}") from exc


def provenance_from_dict(payload: object) -> ProvenanceRecord:
    """Deserialize and validate a flattened completed provenance DAG."""

    document = _mapping(payload, "provenance")
    if document.get("format_version") != _PROVENANCE_FORMAT_VERSION:
        raise ReproducibilityError("unsupported provenance format_version")
    root_record_id = _text(document.get("root_record_id"), "root_record_id")
    raw_records = _array(document.get("records"), "records")

    nodes: dict[str, Mapping[str, Any]] = {}
    for raw_node in raw_records:
        node = _mapping(raw_node, "record")
        record_id = _text(node.get("record_id"), "record_id")
        if record_id in nodes:
            raise ReproducibilityError("serialized provenance contains duplicate record IDs")
        nodes[record_id] = node
    if root_record_id not in nodes:
        raise ReproducibilityError("root_record_id does not identify a serialized record")

    active: set[str] = set()
    validated: set[str] = set()

    def validate_graph(record_id: str) -> None:
        if record_id in active:
            raise ReproducibilityError("serialized completed provenance lineage is cyclic")
        if record_id in validated:
            return
        active.add(record_id)
        node = nodes[record_id]
        for input_id in _text_tuple(node.get("input_record_ids"), "input_record_ids"):
            if input_id not in nodes:
                raise ReproducibilityError(
                    f"provenance input {input_id!r} is missing from serialized lineage"
                )
            validate_graph(input_id)
        active.remove(record_id)
        validated.add(record_id)

    validate_graph(root_record_id)

    built: dict[str, ProvenanceRecord] = {}

    def build(record_id: str) -> ProvenanceRecord:
        existing = built.get(record_id)
        if existing is not None:
            return existing
        node = nodes[record_id]
        dataset_identity = _dataset_from_dict(node.get("dataset_identity"))
        input_records = tuple(
            build(input_id)
            for input_id in _text_tuple(node.get("input_record_ids"), "input_record_ids")
        )
        try:
            record = ProvenanceRecord(
                record_id=record_id,
                dataset_identity=dataset_identity,
                schema_version=_text(node.get("schema_version"), "schema_version"),
                evidence=_enum_value(EvidenceClass, node.get("evidence"), "evidence"),
                validity=_enum_value(ValidityState, node.get("validity"), "validity"),
                value_state=_enum_value(ValueState, node.get("value_state"), "value_state"),
                source_artifacts=tuple(
                    _artifact_from_dict(item)
                    for item in _array(node.get("source_artifacts"), "source_artifacts")
                ),
                subject=_subject_from_dict(node.get("subject"), dataset_identity),
                cohort=_cohort_from_dict(node.get("cohort"), dataset_identity),
                location=_location_from_dict(node.get("location")),
                source_fields=_text_tuple(node.get("source_fields"), "source_fields"),
                inputs=input_records,
                method_id=_optional_text(node.get("method_id"), "method_id"),
                component=_component_from_dict(node.get("component")),
                parameters=CanonicalJSON.from_value(
                    _mapping(node.get("parameters"), "parameters")
                ),
                assumptions=_text_tuple(node.get("assumptions"), "assumptions"),
                citations=_text_tuple(node.get("citations"), "citations"),
                random_state=(
                    None
                    if node.get("random_state") is None
                    else CanonicalJSON.from_value(node.get("random_state"))
                ),
                environment=CanonicalJSON.from_value(
                    _mapping(node.get("environment"), "environment")
                ),
                warnings=_text_tuple(node.get("warnings"), "warnings"),
                output_identity=_optional_text(
                    node.get("output_identity"), "output_identity"
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ReproducibilityError(
                f"invalid serialized provenance record {record_id!r}"
            ) from exc
        built[record_id] = record
        return record

    return build(root_record_id)


def provenance_from_json(payload: str) -> ProvenanceRecord:
    """Deserialize provenance from JSON text."""

    if not isinstance(payload, str):
        raise TypeError("payload must be a string")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReproducibilityError("invalid provenance JSON") from exc
    return provenance_from_dict(document)


def _quantity_to_dict(quantity: QuantityDefinition) -> dict[str, object]:
    return {
        "canonical_name": quantity.canonical_name,
        "label": quantity.label,
        "description": quantity.description,
        "value_kind": quantity.value_kind,
        "schema_version": quantity.schema_version,
        "physical_dimension": quantity.physical_dimension,
        "canonical_unit": quantity.canonical_unit,
        "allowed_source_units": list(quantity.allowed_source_units),
        "applicable_contexts": list(quantity.applicable_contexts),
        "source_aliases": list(quantity.source_aliases),
        "default_evidence": quantity.default_evidence.value,
        "known_source_issues": list(quantity.known_source_issues),
        "citations": list(quantity.citations),
    }


def _quantity_from_dict(payload: object) -> QuantityDefinition:
    item = _mapping(payload, "quantity")
    try:
        return QuantityDefinition(
            canonical_name=_text(item.get("canonical_name"), "canonical_name"),
            label=_text(item.get("label"), "label"),
            description=_text(item.get("description"), "description"),
            value_kind=_text(item.get("value_kind"), "value_kind"),
            schema_version=_text(item.get("schema_version"), "schema_version"),
            physical_dimension=_optional_text(
                item.get("physical_dimension"), "physical_dimension"
            ),
            canonical_unit=_optional_text(item.get("canonical_unit"), "canonical_unit"),
            allowed_source_units=_text_tuple(
                item.get("allowed_source_units"), "allowed_source_units"
            ),
            applicable_contexts=_text_tuple(
                item.get("applicable_contexts"), "applicable_contexts"
            ),
            source_aliases=_text_tuple(item.get("source_aliases"), "source_aliases"),
            default_evidence=_enum_value(
                EvidenceClass, item.get("default_evidence"), "default_evidence"
            ),
            known_source_issues=_text_tuple(
                item.get("known_source_issues"), "known_source_issues"
            ),
            citations=_text_tuple(item.get("citations"), "citations"),
        )
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid serialized quantity definition") from exc


def result_metadata_to_dict(result: ScientificResult) -> dict[str, object]:
    """Serialize scientific result metadata without copying values or coordinates."""

    if not isinstance(result, ScientificResult):
        raise TypeError("result must be a ScientificResult")
    payload: dict[str, object] = {
        "format_version": _RESULT_METADATA_FORMAT_VERSION,
        "result_kind": "waveform" if isinstance(result, Waveform) else "scientific_result",
        "dataset_identity": _dataset_to_dict(result.dataset_identity),
        "quantity": _quantity_to_dict(result.quantity),
        "provenance_ref": result.provenance_ref,
        "dimensions": list(result.dimensions),
        "coordinates": [
            {"name": coordinate.name, "unit": coordinate.unit}
            for coordinate in result.coordinates
        ],
        "source_unit": result.source_unit,
        "source_label": result.source_label,
        "subject": _subject_to_dict(result.subject),
        "cohort": _cohort_to_dict(result.cohort),
        "location": _location_to_dict(result.location),
        "evidence": result.evidence.value,
        "value_state": result.value_state.value,
        "validity": result.validity.value,
        "warnings": list(result.warnings),
        "method_id": result.method_id,
    }
    if isinstance(result, Waveform):
        payload["missing_mask_present"] = result.missing_mask is not None
        payload["padding_mask_present"] = result.padding_mask is not None
    return payload


def result_metadata_to_json(result: ScientificResult) -> str:
    """Serialize scientific result metadata deterministically, excluding arrays."""

    return json.dumps(
        result_metadata_to_dict(result),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def result_metadata_from_dict(
    payload: object,
    *,
    values: object,
    coordinate_values: Mapping[str, object],
    missing_mask: object | None = None,
    padding_mask: object | None = None,
) -> ScientificResult:
    """Rebuild a result from metadata plus caller-supplied value containers."""

    item = _mapping(payload, "result_metadata")
    if item.get("format_version") != _RESULT_METADATA_FORMAT_VERSION:
        raise ReproducibilityError("unsupported result metadata format_version")
    result_kind = _text(item.get("result_kind"), "result_kind")
    if result_kind not in {"scientific_result", "waveform"}:
        raise ReproducibilityError(f"unknown result_kind {result_kind!r}")
    if not isinstance(coordinate_values, Mapping):
        raise TypeError("coordinate_values must be a mapping")

    dataset_identity = _dataset_from_dict(item.get("dataset_identity"))
    quantity = _quantity_from_dict(item.get("quantity"))
    coordinate_payloads = _array(item.get("coordinates"), "coordinates")
    coordinates: list[Coordinate] = []
    coordinate_names: list[str] = []
    for raw_coordinate in coordinate_payloads:
        coordinate_item = _mapping(raw_coordinate, "coordinate")
        name = _text(coordinate_item.get("name"), "coordinate.name")
        coordinate_names.append(name)
        if name not in coordinate_values:
            raise ReproducibilityError(
                f"coordinate_values is missing values for coordinate {name!r}"
            )
        try:
            coordinates.append(
                Coordinate(
                    name=name,
                    values=coordinate_values[name],
                    unit=_optional_text(coordinate_item.get("unit"), "coordinate.unit"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise ReproducibilityError("invalid coordinate metadata") from exc
    if set(coordinate_values) != set(coordinate_names):
        raise ReproducibilityError("coordinate_values keys must exactly match serialized coordinates")

    common: dict[str, object] = {
        "dataset_identity": dataset_identity,
        "quantity": quantity,
        "values": values,
        "provenance_ref": _text(item.get("provenance_ref"), "provenance_ref"),
        "dimensions": _text_tuple(item.get("dimensions"), "dimensions"),
        "coordinates": tuple(coordinates),
        "source_unit": _optional_text(item.get("source_unit"), "source_unit"),
        "source_label": _optional_text(item.get("source_label"), "source_label"),
        "subject": _subject_from_dict(item.get("subject"), dataset_identity),
        "cohort": _cohort_from_dict(item.get("cohort"), dataset_identity),
        "location": _location_from_dict(item.get("location")),
        "evidence": _enum_value(EvidenceClass, item.get("evidence"), "evidence"),
        "value_state": _enum_value(ValueState, item.get("value_state"), "value_state"),
        "validity": _enum_value(ValidityState, item.get("validity"), "validity"),
        "warnings": _text_tuple(item.get("warnings"), "warnings"),
        "method_id": _optional_text(item.get("method_id"), "method_id"),
    }

    try:
        if result_kind == "waveform":
            expects_missing = item.get("missing_mask_present")
            expects_padding = item.get("padding_mask_present")
            if not isinstance(expects_missing, bool) or not isinstance(expects_padding, bool):
                raise ReproducibilityError(
                    "waveform metadata must declare mask-presence booleans"
                )
            if expects_missing != (missing_mask is not None):
                raise ReproducibilityError("missing-mask presence does not match metadata")
            if expects_padding != (padding_mask is not None):
                raise ReproducibilityError("padding-mask presence does not match metadata")
            return Waveform(
                **common,
                missing_mask=missing_mask,
                padding_mask=padding_mask,
            )
        if missing_mask is not None or padding_mask is not None:
            raise ReproducibilityError("mask values are only valid for waveform metadata")
        return ScientificResult(**common)
    except ReproducibilityError:
        raise
    except (TypeError, ValueError) as exc:
        raise ReproducibilityError("invalid serialized scientific-result metadata") from exc


def result_metadata_from_json(
    payload: str,
    *,
    values: object,
    coordinate_values: Mapping[str, object],
    missing_mask: object | None = None,
    padding_mask: object | None = None,
) -> ScientificResult:
    """Rebuild a scientific result from JSON metadata and external values."""

    if not isinstance(payload, str):
        raise TypeError("payload must be a string")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReproducibilityError("invalid result metadata JSON") from exc
    return result_metadata_from_dict(
        document,
        values=values,
        coordinate_values=coordinate_values,
        missing_mask=missing_mask,
        padding_mask=padding_mask,
    )


__all__ = [
    "provenance_from_dict",
    "provenance_from_json",
    "provenance_to_dict",
    "provenance_to_json",
    "result_metadata_from_dict",
    "result_metadata_from_json",
    "result_metadata_to_dict",
    "result_metadata_to_json",
]
