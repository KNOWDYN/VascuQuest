"""Load and mechanically validate packaged VascuQuest scientific resources.

This module validates resource structure and source-to-canonical metadata.  It
performs no data acquisition, source parsing, unit conversion, or scientific
calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
import re
from typing import Any
from urllib.parse import urlparse

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.errors import SchemaError


_MANIFEST_RESOURCE = "pwdb3275625_manifest.json"
_SCHEMA_RESOURCE = "canonical_schema.json"
_CANONICAL_RECORD_ID = "3275625"
_CANONICAL_DOI = "10.5281/zenodo.3275625"
_MD5_RE = re.compile(r"^[0-9a-f]{32}$")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise SchemaError(f"{field_name} must be a string")
    if not value:
        raise SchemaError(f"{field_name} must not be empty")
    if value != value.strip():
        raise SchemaError(f"{field_name} must not contain leading or trailing whitespace")
    return value


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _text_tuple(value: object, field_name: str, *, unique: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SchemaError(f"{field_name} must be a JSON array")
    result = tuple(_required_text(item, field_name) for item in value)
    if unique and len(set(result)) != len(result):
        raise SchemaError(f"{field_name} must not contain duplicate values")
    return result


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{field_name} must be a JSON object")
    return value


def _array(value: object, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"{field_name} must be a JSON array")
    return value


def _read_resource(name: str) -> dict[str, Any]:
    try:
        resource = files("vascuquest.schema").joinpath("resources", name)
        with resource.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaError(f"unable to load packaged schema resource {name!r}") from exc

    if not isinstance(payload, dict):
        raise SchemaError(f"packaged schema resource {name!r} must contain a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class ArtifactManifestEntry:
    """One immutable canonical-source artifact declaration."""

    artifact_id: str
    filename: str
    canonical_record_id: str
    canonical_doi: str
    role: str
    reported_size_bytes: int | None
    checksum_algorithm: str
    checksum_value: str
    source_locator: str
    container_format: str
    compression: str | None
    capabilities_provided: tuple[str, ...]
    required_for: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalManifest:
    """Validated canonical artifact manifest for one exact dataset record."""

    manifest_version: int
    canonical_record_id: str
    canonical_doi: str
    canonical_record_url: str
    artifacts: tuple[ArtifactManifestEntry, ...]

    def artifact(self, artifact_id: str) -> ArtifactManifestEntry:
        """Return one artifact by canonical manifest ID."""

        for artifact in self.artifacts:
            if artifact.artifact_id == artifact_id:
                return artifact
        raise KeyError(artifact_id)


@dataclass(frozen=True, slots=True)
class SourceFieldMapping:
    """One declared source-field/unit to canonical-unit mapping."""

    source_scope: str
    source_field: str
    source_unit: str
    canonical_unit: str


@dataclass(frozen=True, slots=True)
class SourceDefect:
    """Traceable upstream metadata defect retained by the canonical schema."""

    issue_id: str
    source_scope: str
    source_field: str
    reported_value: str
    canonical_interpretation: str
    status: str


@dataclass(frozen=True, slots=True)
class CanonicalQuantitySchema:
    """Domain quantity definition plus backend-facing source metadata."""

    definition: QuantityDefinition
    category: str
    source_mappings: tuple[SourceFieldMapping, ...]
    source_defects: tuple[SourceDefect, ...]


@dataclass(frozen=True, slots=True)
class CanonicalSchema:
    """Validated versioned scientific schema for the canonical dataset."""

    schema_version: str
    dataset_family: str
    canonical_record_id: str
    canonical_doi: str
    allowed_categories: tuple[str, ...]
    allowed_location_contexts: tuple[str, ...]
    quantities: tuple[CanonicalQuantitySchema, ...]

    def quantity_schema(self, canonical_name: str) -> CanonicalQuantitySchema:
        """Return one canonical quantity record by semantic identity."""

        for quantity in self.quantities:
            if quantity.definition.canonical_name == canonical_name:
                return quantity
        raise KeyError(canonical_name)

    def quantity(self, canonical_name: str) -> QuantityDefinition:
        """Return one canonical domain quantity definition."""

        return self.quantity_schema(canonical_name).definition


def _validate_https_locator(value: object, field_name: str) -> str:
    locator = _required_text(value, field_name)
    parsed = urlparse(locator)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SchemaError(f"{field_name} must be an absolute https URL")
    return locator


def _load_manifest_entry(payload: object, index: int) -> ArtifactManifestEntry:
    item = _mapping(payload, f"artifacts[{index}]")

    size_value = item.get("reported_size_bytes")
    if size_value is not None:
        if isinstance(size_value, bool) or not isinstance(size_value, int) or size_value < 0:
            raise SchemaError("reported_size_bytes must be a non-negative integer or null")

    checksum_algorithm = _required_text(item.get("checksum_algorithm"), "checksum_algorithm")
    checksum_value = _required_text(item.get("checksum_value"), "checksum_value")
    if checksum_algorithm != "md5":
        raise SchemaError("canonical PWDB manifest checksum_algorithm must be 'md5'")
    if not _MD5_RE.fullmatch(checksum_value):
        raise SchemaError("checksum_value must be a lowercase 32-character MD5 value")

    record_id = _required_text(item.get("canonical_record_id"), "canonical_record_id")
    doi = _required_text(item.get("canonical_doi"), "canonical_doi")
    if record_id != _CANONICAL_RECORD_ID or doi != _CANONICAL_DOI:
        raise SchemaError("artifact canonical identity does not match PWDB 3275625")

    capabilities = _text_tuple(item.get("capabilities_provided"), "capabilities_provided")
    if not capabilities:
        raise SchemaError("capabilities_provided must contain at least one capability")

    required_for_value = item.get("required_for", [])
    required_for = _text_tuple(required_for_value, "required_for")

    return ArtifactManifestEntry(
        artifact_id=_required_text(item.get("artifact_id"), "artifact_id"),
        filename=_required_text(item.get("filename"), "filename"),
        canonical_record_id=record_id,
        canonical_doi=doi,
        role=_required_text(item.get("role"), "role"),
        reported_size_bytes=size_value,
        checksum_algorithm=checksum_algorithm,
        checksum_value=checksum_value,
        source_locator=_validate_https_locator(item.get("source_locator"), "source_locator"),
        container_format=_required_text(item.get("container_format"), "container_format"),
        compression=_optional_text(item.get("compression"), "compression"),
        capabilities_provided=capabilities,
        required_for=required_for,
    )


def load_manifest() -> CanonicalManifest:
    """Load and mechanically validate the packaged canonical artifact manifest."""

    payload = _read_resource(_MANIFEST_RESOURCE)
    version = payload.get("manifest_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise SchemaError("manifest_version must be a positive integer")

    record_id = _required_text(payload.get("canonical_record_id"), "canonical_record_id")
    doi = _required_text(payload.get("canonical_doi"), "canonical_doi")
    if record_id != _CANONICAL_RECORD_ID or doi != _CANONICAL_DOI:
        raise SchemaError("manifest canonical identity must be PWDB Zenodo record 3275625")

    artifacts_payload = _array(payload.get("artifacts"), "artifacts")
    artifacts = tuple(
        _load_manifest_entry(item, index) for index, item in enumerate(artifacts_payload)
    )

    artifact_ids = tuple(item.artifact_id for item in artifacts)
    filenames = tuple(item.filename for item in artifacts)
    locators = tuple(item.source_locator for item in artifacts)
    if len(set(artifact_ids)) != len(artifact_ids):
        raise SchemaError("artifact IDs must be unique")
    if len(set(filenames)) != len(filenames):
        raise SchemaError("artifact filenames must be unique")
    if len(set(locators)) != len(locators):
        raise SchemaError("artifact source locators must be unique")

    return CanonicalManifest(
        manifest_version=version,
        canonical_record_id=record_id,
        canonical_doi=doi,
        canonical_record_url=_validate_https_locator(
            payload.get("canonical_record_url"), "canonical_record_url"
        ),
        artifacts=artifacts,
    )


def _load_source_mapping(
    payload: object,
    *,
    quantity_name: str,
    allowed_source_units: tuple[str, ...],
    canonical_unit: str | None,
) -> SourceFieldMapping:
    item = _mapping(payload, f"{quantity_name}.source_mappings")
    source_unit = _required_text(item.get("source_unit"), "source_unit")
    mapping_canonical_unit = _required_text(item.get("canonical_unit"), "canonical_unit")

    if source_unit not in allowed_source_units:
        raise SchemaError(
            f"source unit {source_unit!r} for {quantity_name!r} is not an allowed source unit"
        )
    if canonical_unit is None or mapping_canonical_unit != canonical_unit:
        raise SchemaError(
            f"source mapping canonical unit for {quantity_name!r} does not match its definition"
        )

    return SourceFieldMapping(
        source_scope=_required_text(item.get("source_scope"), "source_scope"),
        source_field=_required_text(item.get("source_field"), "source_field"),
        source_unit=source_unit,
        canonical_unit=mapping_canonical_unit,
    )


def _load_source_defect(payload: object, quantity_name: str) -> SourceDefect:
    item = _mapping(payload, f"{quantity_name}.source_defects")
    status = _required_text(item.get("status"), "status")
    if status != "upstream_metadata_defect":
        raise SchemaError("source defect status must be 'upstream_metadata_defect'")

    return SourceDefect(
        issue_id=_required_text(item.get("issue_id"), "issue_id"),
        source_scope=_required_text(item.get("source_scope"), "source_scope"),
        source_field=_required_text(item.get("source_field"), "source_field"),
        reported_value=_required_text(item.get("reported_value"), "reported_value"),
        canonical_interpretation=_required_text(
            item.get("canonical_interpretation"), "canonical_interpretation"
        ),
        status=status,
    )


def _load_quantity(
    payload: object,
    *,
    schema_version: str,
    allowed_categories: tuple[str, ...],
    allowed_location_contexts: tuple[str, ...],
) -> CanonicalQuantitySchema:
    item = _mapping(payload, "quantity")
    canonical_name = _required_text(item.get("canonical_name"), "canonical_name")
    value_kind = _required_text(item.get("value_kind"), "value_kind")
    physical_dimension = _optional_text(item.get("physical_dimension"), "physical_dimension")
    canonical_unit = _optional_text(item.get("canonical_unit"), "canonical_unit")
    allowed_source_units = _text_tuple(item.get("allowed_source_units"), "allowed_source_units")
    applicable_contexts = _text_tuple(item.get("applicable_contexts"), "applicable_contexts")
    source_aliases = _text_tuple(item.get("source_aliases"), "source_aliases")
    known_source_issues = _text_tuple(item.get("known_source_issues"), "known_source_issues")
    citations = _text_tuple(item.get("citations"), "citations")

    if value_kind == "numeric" and (physical_dimension is None or canonical_unit is None):
        raise SchemaError(
            f"numeric quantity {canonical_name!r} must declare physical_dimension and canonical_unit"
        )
    if physical_dimension == "dimensionless" and canonical_unit is None:
        raise SchemaError(
            f"dimensionless quantity {canonical_name!r} must explicitly declare a canonical unit"
        )

    unknown_contexts = set(applicable_contexts) - set(allowed_location_contexts)
    if unknown_contexts:
        raise SchemaError(
            f"quantity {canonical_name!r} uses unknown location contexts: {sorted(unknown_contexts)!r}"
        )

    category = _required_text(item.get("category"), "category")
    if category not in allowed_categories:
        raise SchemaError(f"quantity {canonical_name!r} uses unknown category {category!r}")

    evidence_value = _required_text(item.get("default_evidence"), "default_evidence")
    try:
        default_evidence = EvidenceClass(evidence_value)
    except ValueError as exc:
        raise SchemaError(
            f"quantity {canonical_name!r} uses unknown evidence class {evidence_value!r}"
        ) from exc

    mappings_payload = _array(item.get("source_mappings"), "source_mappings")
    source_mappings = tuple(
        _load_source_mapping(
            mapping,
            quantity_name=canonical_name,
            allowed_source_units=allowed_source_units,
            canonical_unit=canonical_unit,
        )
        for mapping in mappings_payload
    )
    mapping_keys = tuple((mapping.source_scope, mapping.source_field) for mapping in source_mappings)
    if len(set(mapping_keys)) != len(mapping_keys):
        raise SchemaError(f"quantity {canonical_name!r} has duplicate source mappings")

    defects_payload = _array(item.get("source_defects", []), "source_defects")
    source_defects = tuple(
        _load_source_defect(defect, canonical_name) for defect in defects_payload
    )
    defect_ids = tuple(defect.issue_id for defect in source_defects)
    if len(set(defect_ids)) != len(defect_ids):
        raise SchemaError(f"quantity {canonical_name!r} has duplicate source defect IDs")
    if set(defect_ids) != set(known_source_issues):
        raise SchemaError(
            f"quantity {canonical_name!r} known_source_issues must match declared source defects"
        )

    definition = QuantityDefinition(
        canonical_name=canonical_name,
        label=_required_text(item.get("label"), "label"),
        description=_required_text(item.get("description"), "description"),
        value_kind=value_kind,
        schema_version=schema_version,
        physical_dimension=physical_dimension,
        canonical_unit=canonical_unit,
        allowed_source_units=allowed_source_units,
        applicable_contexts=applicable_contexts,
        source_aliases=source_aliases,
        default_evidence=default_evidence,
        known_source_issues=known_source_issues,
        citations=citations,
    )

    return CanonicalQuantitySchema(
        definition=definition,
        category=category,
        source_mappings=source_mappings,
        source_defects=source_defects,
    )


def load_canonical_schema() -> CanonicalSchema:
    """Load and mechanically validate the packaged canonical scientific schema."""

    payload = _read_resource(_SCHEMA_RESOURCE)
    schema_version = _required_text(payload.get("schema_version"), "schema_version")
    dataset_family = _required_text(payload.get("dataset_family"), "dataset_family")
    record_id = _required_text(payload.get("canonical_record_id"), "canonical_record_id")
    doi = _required_text(payload.get("canonical_doi"), "canonical_doi")

    if dataset_family != "PWDB" or record_id != _CANONICAL_RECORD_ID or doi != _CANONICAL_DOI:
        raise SchemaError("canonical schema identity must be PWDB Zenodo record 3275625")

    allowed_categories = _text_tuple(payload.get("allowed_categories"), "allowed_categories")
    allowed_location_contexts = _text_tuple(
        payload.get("allowed_location_contexts"), "allowed_location_contexts"
    )
    quantities_payload = _array(payload.get("quantities"), "quantities")
    quantities = tuple(
        _load_quantity(
            quantity,
            schema_version=schema_version,
            allowed_categories=allowed_categories,
            allowed_location_contexts=allowed_location_contexts,
        )
        for quantity in quantities_payload
    )

    names = tuple(quantity.definition.canonical_name for quantity in quantities)
    if len(set(names)) != len(names):
        raise SchemaError("canonical quantity identities must be unique")

    alias_owner: dict[str, str] = {}
    for quantity in quantities:
        for alias in quantity.definition.source_aliases:
            previous = alias_owner.setdefault(alias, quantity.definition.canonical_name)
            if previous != quantity.definition.canonical_name:
                raise SchemaError(
                    f"source alias {alias!r} collides between {previous!r} and "
                    f"{quantity.definition.canonical_name!r}"
                )

    return CanonicalSchema(
        schema_version=schema_version,
        dataset_family=dataset_family,
        canonical_record_id=record_id,
        canonical_doi=doi,
        allowed_categories=allowed_categories,
        allowed_location_contexts=allowed_location_contexts,
        quantities=quantities,
    )


__all__ = [
    "ArtifactManifestEntry",
    "CanonicalManifest",
    "CanonicalQuantitySchema",
    "CanonicalSchema",
    "SourceDefect",
    "SourceFieldMapping",
    "load_canonical_schema",
    "load_manifest",
]
