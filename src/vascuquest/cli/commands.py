"""Frozen VascuQuest v1 command tree and API/data-service dispatch.

This module parses command-line values, constructs domain/application requests,
and renders returned results. It contains no scientific equations and does not
open PWDB source formats directly.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from collections.abc import Iterable, Mapping

import typer

import vascuquest as vq
from vascuquest.data import (
    ArtifactAcquirer,
    ArtifactState,
    DataPaths,
    SourceRegistry,
    probe_artifact,
    verify_artifact,
)
from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import DatasetUnavailableError, IntegrityError, SelectionError
from vascuquest.exporters import load_result_csv, load_result_json
from vascuquest.plugins import ComponentKind
from vascuquest.provenance import provenance_from_json
from vascuquest.schema import load_canonical_schema, load_manifest

from .rendering import RenderingError, serialize_primary, write_primary


CANONICAL_DATASET = "pwdb:3275625"
_LARGE_DOWNLOAD_BYTES = 1024**3


dataset_app = typer.Typer(help="Inspect and manage canonical dataset sources.")
plugins_app = typer.Typer(help="Inspect built-in and installed components.")


def _parse_literal(text: str) -> object:
    if not isinstance(text, str) or not text:
        raise typer.BadParameter("assignment values must not be empty")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(value, (dict, list)):
        return value
    return value


def _parse_assignments(values: Iterable[str], option_name: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for raw in values:
        if not isinstance(raw, str) or raw.count("=") != 1:
            raise typer.BadParameter(
                f"{option_name} values must use exactly name=value syntax"
            )
        name, text = raw.split("=", 1)
        if not name or name != name.strip() or not text:
            raise typer.BadParameter(
                f"{option_name} values must use non-empty trimmed name=value syntax"
            )
        if name in parsed:
            raise typer.BadParameter(f"duplicate {option_name} name {name!r}")
        parsed[name] = _parse_literal(text)
    return parsed


def _open_session(
    dataset: str,
    *,
    source: str | None = None,
    offline: bool = False,
):
    source_path = None if source is None else Path(source).expanduser()
    return vq.open_dataset(dataset, source=source_path, offline=offline)


def _emit(value: object, output_format: str, output: str | None = None) -> None:
    try:
        text = serialize_primary(value, output_format)
        path = write_primary(text, output)
    except RenderingError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if path is None:
        typer.echo(text, nl=False)


def _identity_dict(identity: object) -> dict[str, object]:
    return {
        "dataset_family": getattr(identity, "dataset_family"),
        "record_id": getattr(identity, "record_id"),
        "persistent_identifier": getattr(identity, "persistent_identifier"),
        "schema_version": getattr(identity, "schema_version"),
    }


def _subject_row(subject: object) -> dict[str, object]:
    return {
        "canonical_subject_id": getattr(subject, "canonical_subject_id"),
        "dataset_identity": _identity_dict(getattr(subject, "dataset_identity")),
        "subject_kind": "virtual_subject",
    }


def _quantity_row(quantity_schema: object) -> dict[str, object]:
    definition = getattr(quantity_schema, "definition")
    return {
        "canonical_name": definition.canonical_name,
        "label": definition.label,
        "description": definition.description,
        "category": getattr(quantity_schema, "category"),
        "canonical_unit": definition.canonical_unit,
        "physical_dimension": definition.physical_dimension,
        "applicable_contexts": list(definition.applicable_contexts),
        "default_evidence": definition.default_evidence.value,
        "known_source_issues": list(definition.known_source_issues),
    }


def _location_row(location: object) -> dict[str, object]:
    if isinstance(location, MeasurementSite):
        return {"kind": "site", "canonical_site_id": location.canonical_site_id}
    if isinstance(location, SegmentLocation):
        return {"kind": "segment", "canonical_segment_id": location.canonical_segment_id}
    if isinstance(location, PathPosition):
        return {
            "kind": "path-position",
            "canonical_path_id": location.canonical_path_id,
            "position_index": location.position_index,
        }
    raise SelectionError("unsupported vascular location returned by dataset backend")


def _data_context() -> tuple[DataPaths, SourceRegistry, object]:
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    manifest = load_manifest()
    return paths, registry, manifest


def _resolve_artifact(token: str, manifest: object):
    matches = [
        artifact
        for artifact in manifest.artifacts
        if token in {artifact.artifact_id, artifact.filename}
    ]
    if len(matches) != 1:
        raise DatasetUnavailableError(f"unknown or ambiguous canonical artifact {token!r}")
    return matches[0]


def _planned_artifacts(
    *, artifact: str | None, capability: str | None, manifest: object
) -> tuple[object, ...]:
    if (artifact is None) == (capability is None):
        raise typer.BadParameter("choose exactly one of --artifact or --capability")
    if artifact is not None:
        return (_resolve_artifact(artifact, manifest),)
    assert capability is not None
    matches = tuple(
        item for item in manifest.artifacts if capability in item.capabilities_provided
    )
    if not matches:
        raise DatasetUnavailableError(f"unknown canonical capability {capability!r}")
    return matches


def _requires_confirmation(artifacts: tuple[object, ...]) -> bool:
    sizes = [item.reported_size_bytes for item in artifacts]
    if any(size is None for size in sizes):
        # The canonical manifest currently omits byte counts for some artifacts.
        # Unknown size is treated conservatively so a potentially multi-GB transfer
        # is never silently started.
        return True
    known_sizes = [int(size) for size in sizes if size is not None]
    return any(size >= _LARGE_DOWNLOAD_BYTES for size in known_sizes) or sum(
        known_sizes
    ) >= _LARGE_DOWNLOAD_BYTES


def _size_summary(artifacts: tuple[object, ...]) -> str:
    sizes = [item.reported_size_bytes for item in artifacts]
    if any(size is None for size in sizes):
        return "unknown (confirmation required conservatively)"
    total = sum(int(size) for size in sizes)
    return f"{total} bytes"


def _confirm_destructive_or_large(message: str, *, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise typer.BadParameter(f"{message}; non-interactive execution requires --yes")
    if not typer.confirm(f"{message}. Continue?", default=False, abort=False, err=True):
        raise typer.Abort()


def _first_local_probe(artifact: object, paths: DataPaths, registry: SourceRegistry):
    for candidate in registry.candidates(artifact, paths, offline=True):
        if candidate.local_path is None:
            continue
        inspection = probe_artifact(candidate.local_path, artifact)
        if inspection.state is not ArtifactState.MISSING:
            return candidate.kind.value, inspection
    inspection = probe_artifact(paths.source_artifact(artifact.filename), artifact)
    return "managed_cache", inspection


def _result_file(path: str) -> ScientificResult:
    source = Path(path).expanduser()
    if source.suffix.lower() == ".json":
        return load_result_json(source)
    if source.suffix.lower() == ".csv":
        return load_result_csv(source)
    raise typer.BadParameter("result-file must be a VascuQuest .json or .csv export")


@dataset_app.command("info")
def dataset_info(
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Report static canonical dataset identity and manifest inventory."""

    manifest = load_manifest()
    schema = load_canonical_schema()
    payload = {
        "dataset_family": schema.dataset_family,
        "record_id": manifest.canonical_record_id,
        "doi": manifest.canonical_doi,
        "schema_version": schema.schema_version,
        "manifest_version": manifest.manifest_version,
        "artifact_count": len(manifest.artifacts),
        "artifacts": [
            {
                "artifact_id": item.artifact_id,
                "filename": item.filename,
                "role": item.role,
                "reported_size_bytes": item.reported_size_bytes,
                "capabilities_provided": list(item.capabilities_provided),
            }
            for item in manifest.artifacts
        ],
    }
    _emit(payload, output_format, output)


@dataset_app.command("status")
def dataset_status(
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Report read-only local source presence and supported core capabilities."""

    session = _open_session(dataset, offline=True)
    paths, registry, manifest = _data_context()
    artifact_rows: list[dict[str, object]] = []
    for artifact in manifest.artifacts:
        source_kind, inspection = _first_local_probe(artifact, paths, registry)
        artifact_rows.append(
            {
                "artifact_id": artifact.artifact_id,
                "filename": artifact.filename,
                "state": inspection.state.value,
                "source_kind": source_kind,
                "size_bytes": inspection.size_bytes,
                "capabilities_provided": list(artifact.capabilities_provided),
            }
        )
    status = session.status()
    payload = {
        "dataset_identity": _identity_dict(status.identity),
        "registered_local_sources": [str(path) for path in registry.local_roots],
        "supported_capabilities": sorted(status.capabilities),
        "path_resolved_supported": status.path_resolved_supported,
        "path_validation_state": status.path_validation_state,
        "artifacts": artifact_rows,
        "managed_paths": {
            "source": str(paths.source),
            "work": str(paths.work),
            "derived": str(paths.derived),
            "results": str(paths.results),
        },
    }
    _emit(payload, output_format, output)


@dataset_app.command("register")
def dataset_register(
    directory: str = typer.Argument(...),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Verify and register an existing canonical-source directory without copying it."""

    path = Path(directory).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise DatasetUnavailableError(f"registered source directory is unavailable: {path}")
    manifest = load_manifest()
    recognized = tuple(item for item in manifest.artifacts if (path / item.filename).is_file())
    if not recognized:
        raise DatasetUnavailableError(
            f"source directory contains no recognized PWDB 3275625 artifacts: {path}"
        )
    verified: list[dict[str, object]] = []
    failures: list[str] = []
    for artifact in recognized:
        inspection = verify_artifact(path / artifact.filename, artifact)
        if inspection.state is not ArtifactState.VERIFIED:
            failures.append(f"{artifact.artifact_id}:{inspection.state.value}")
        verified.append(
            {
                "artifact_id": artifact.artifact_id,
                "filename": artifact.filename,
                "state": inspection.state.value,
            }
        )
    if failures:
        raise IntegrityError(
            "registered source contains artifacts that failed canonical verification: "
            + ", ".join(failures)
        )
    registered = vq.register_source(path)
    capabilities = sorted(
        {cap for artifact in recognized for cap in artifact.capabilities_provided}
    )
    _emit(
        {
            "registered_source": str(registered),
            "verified_artifacts": verified,
            "capabilities_present": capabilities,
        },
        output_format,
        output,
    )


@dataset_app.command("acquire")
def dataset_acquire(
    artifact: str | None = typer.Option(None, "--artifact"),
    capability: str | None = typer.Option(None, "--capability"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    yes: bool = typer.Option(False, "--yes"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Acquire explicitly requested canonical artifacts after safety planning."""

    if dataset not in {"pwdb", CANONICAL_DATASET}:
        raise DatasetUnavailableError(f"unsupported dataset {dataset!r}")
    paths, registry, manifest = _data_context()
    if source is not None:
        registry.register_local(Path(source).expanduser())
    planned = _planned_artifacts(artifact=artifact, capability=capability, manifest=manifest)
    typer.echo(
        "Acquisition plan: "
        + ", ".join(f"{item.artifact_id} ({item.filename})" for item in planned)
        + f"; expected total size: {_size_summary(planned)}; managed source cache: {paths.source}",
        err=True,
    )
    if _requires_confirmation(planned):
        _confirm_destructive_or_large("Acquisition size is large or unknown", yes=yes)
    acquirer = ArtifactAcquirer(paths, registry, manifest=manifest)
    acquired = [
        {
            "artifact_id": item.artifact_id,
            "filename": item.filename,
            "path": str(acquirer.acquire(item.artifact_id, offline=offline)),
            "state": "verified",
        }
        for item in planned
    ]
    _emit(acquired, output_format, output)


@dataset_app.command("verify")
def dataset_verify(
    artifact: str | None = typer.Option(None, "--artifact"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Verify registered/cached artifacts against the canonical manifest."""

    paths, registry, manifest = _data_context()
    selected = (
        (_resolve_artifact(artifact, manifest),)
        if artifact is not None
        else tuple(manifest.artifacts)
    )
    rows: list[dict[str, object]] = []
    failures: list[str] = []
    for item in selected:
        candidates = [
            candidate
            for candidate in registry.candidates(item, paths, offline=True)
            if candidate.local_path is not None and candidate.local_path.exists()
        ]
        if not candidates:
            rows.append(
                {
                    "artifact_id": item.artifact_id,
                    "filename": item.filename,
                    "state": ArtifactState.MISSING.value,
                }
            )
            continue
        for candidate in candidates:
            inspection = verify_artifact(candidate.local_path, item)
            rows.append(
                {
                    "artifact_id": item.artifact_id,
                    "filename": item.filename,
                    "source_kind": candidate.kind.value,
                    "path": str(candidate.local_path),
                    "state": inspection.state.value,
                    "expected_checksum": inspection.expected_checksum,
                    "observed_checksum": inspection.observed_checksum,
                    "size_bytes": inspection.size_bytes,
                }
            )
            if inspection.state in {ArtifactState.CHECKSUM_FAILED, ArtifactState.UNREADABLE}:
                failures.append(f"{item.artifact_id}:{inspection.state.value}")
    if artifact is not None and all(row["state"] == ArtifactState.MISSING.value for row in rows):
        raise DatasetUnavailableError(f"canonical artifact {artifact!r} is not available locally")
    if failures:
        raise IntegrityError("canonical verification failed: " + ", ".join(failures))
    _emit(rows, output_format, output)


@dataset_app.command("clean")
def dataset_clean(
    derived: bool = typer.Option(False, "--derived"),
    temporary: bool = typer.Option(False, "--temporary"),
    source_cache: bool = typer.Option(False, "--source-cache"),
    yes: bool = typer.Option(False, "--yes"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Delete only explicitly selected VascuQuest-managed cache namespaces."""

    paths = DataPaths.default()
    selected: list[tuple[str, Path]] = []
    if derived:
        selected.append(("derived", paths.derived))
    if temporary:
        selected.append(("temporary", paths.work))
    if source_cache:
        selected.append(("source_cache", paths.source))
    if not selected:
        raise typer.BadParameter(
            "select at least one of --derived, --temporary, or --source-cache"
        )
    plan = ", ".join(f"{name}:{path}" for name, path in selected)
    typer.echo(f"Deletion plan: {plan}", err=True)
    _confirm_destructive_or_large("Delete the selected VascuQuest-managed material", yes=yes)
    deleted: list[dict[str, object]] = []
    for name, path in selected:
        existed = path.exists()
        if existed:
            shutil.rmtree(path)
        deleted.append({"kind": name, "path": str(path), "existed": existed})
    _emit(deleted, output_format, output)


def subjects_command(
    where: list[str] = typer.Option([], "--where"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """List virtual subjects using exact-match AND filters only."""

    filters = _parse_assignments(where, "--where")
    session = _open_session(dataset, source=source, offline=offline)
    rows = [_subject_row(item) for item in session.subjects(where=filters or None)]
    _emit(rows, output_format, output)


def quantities_command(
    category: str | None = typer.Option(None, "--category"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """List canonical quantity definitions without acquiring source artifacts."""

    _open_session(dataset, offline=True)
    schema = load_canonical_schema()
    rows = [
        _quantity_row(item)
        for item in schema.quantities
        if category is None or item.category == category
    ]
    _emit(rows, output_format, output)


def locations_command(
    kind: str | None = typer.Option(None, "--kind"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """List vascular locations currently exposed by the opened backend."""

    session = _open_session(dataset, offline=True)
    rows = [_location_row(item) for item in session.locations()]
    if kind is not None:
        aliases = {"measurement-site": "site", "measurement_site": "site"}
        normalized = aliases.get(kind, kind)
        rows = [row for row in rows if row["kind"] == normalized]
    _emit(rows, output_format, output)


def get_command(
    quantity: str = typer.Argument(...),
    subject: str | None = typer.Option(None, "--subject"),
    where: list[str] = typer.Option([], "--where"),
    location: str | None = typer.Option(None, "--location"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Retrieve one canonical non-waveform scientific quantity."""

    if subject is not None and where:
        raise typer.BadParameter("--subject and --where are mutually exclusive")
    session = _open_session(dataset, source=source, offline=offline)
    filters = _parse_assignments(where, "--where")
    selection: object = subject
    if filters:
        selection = session.select(where=filters)
    if quantity == "vascular_geometry":
        if subject is None or filters:
            raise typer.BadParameter("vascular_geometry requires exactly one --subject")
        result = session.geometry(
            subject=subject,
            location=None if location is None else SegmentLocation(location),
        )
    else:
        resolved_location = None if location is None else MeasurementSite(location)
        result = session.get(quantity, subjects=selection, location=resolved_location)
    _emit(result, output_format, output)


def waveform_command(
    signal: str = typer.Argument(...),
    subject: str = typer.Option(..., "--subject"),
    location: str = typer.Option(..., "--location"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Retrieve one common-site waveform through the public session API."""

    session = _open_session(dataset, source=source, offline=offline)
    result = session.waveform(
        signal,
        subject=subject,
        location=MeasurementSite(location),
    )
    _emit(result, output_format, output)


def derive_command(
    method: str = typer.Argument(...),
    subject: str | None = typer.Option(None, "--subject"),
    where: list[str] = typer.Option([], "--where"),
    location: str | None = typer.Option(None, "--location"),
    param: list[str] = typer.Option([], "--param"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Run a registered deterministic derivation through DatasetSession."""

    if subject is not None and where:
        raise typer.BadParameter("--subject and --where are mutually exclusive")
    session = _open_session(dataset, source=source, offline=offline)
    filters = _parse_assignments(where, "--where")
    selection: object = subject
    if filters:
        selection = session.select(where=filters)
    result = session.derive(
        method,
        subjects=selection,
        location=None if location is None else MeasurementSite(location),
        parameters=_parse_assignments(param, "--param") or None,
    )
    _emit(result, output_format, output)


def model_command(
    operator: str = typer.Argument(...),
    subject: str | None = typer.Option(None, "--subject"),
    where: list[str] = typer.Option([], "--where"),
    location: str | None = typer.Option(None, "--location"),
    param: list[str] = typer.Option([], "--param"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Run a registered research operator through DatasetSession."""

    if subject is not None and where:
        raise typer.BadParameter("--subject and --where are mutually exclusive")
    session = _open_session(dataset, source=source, offline=offline)
    filters = _parse_assignments(where, "--where")
    selection: object = subject
    if filters:
        selection = session.select(where=filters)
    result = session.model(
        operator,
        subjects=selection,
        location=None if location is None else MeasurementSite(location),
        parameters=_parse_assignments(param, "--param") or None,
    )
    _emit(result, output_format, output)


def discover_command(
    method: str = typer.Argument(...),
    where: list[str] = typer.Option([], "--where"),
    param: list[str] = typer.Option([], "--param"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Run a registered discovery method on an explicit reproducible cohort."""

    session = _open_session(dataset, source=source, offline=offline)
    cohort = session.select(where=_parse_assignments(where, "--where") or None)
    result = session.discover(
        method,
        cohort=cohort,
        parameters=_parse_assignments(param, "--param") or None,
    )
    _emit(result, output_format, output)


@plugins_app.command("list")
def plugins_list(
    kind: str | None = typer.Option(None, "--kind"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """List available extension-component descriptors without data acquisition."""

    resolved_kind = None
    if kind is not None:
        try:
            resolved_kind = ComponentKind(kind)
        except ValueError as exc:
            raise typer.BadParameter(
                f"unknown plugin kind {kind!r}; choose {[item.value for item in ComponentKind]!r}"
            ) from exc
    rows = [
        {
            "kind": item.kind.value,
            "qualified_id": item.qualified_id,
            "name": item.name,
            "implementation_version": item.implementation_version,
            "protocol_version": item.protocol_version,
            "distribution_name": item.distribution_name,
            "distribution_version": item.distribution_version,
            "summary": item.summary,
        }
        for item in vq.plugins.list(resolved_kind)
    ]
    _emit(rows, output_format, output)


@plugins_app.command("describe")
def plugins_describe(
    qualified_id: str = typer.Argument(...),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Describe one component through the public plugin inspection API."""

    item = vq.plugins.describe(qualified_id)
    payload = {
        "kind": item.kind.value,
        "qualified_id": item.qualified_id,
        "name": item.name,
        "implementation_version": item.implementation_version,
        "protocol_version": item.protocol_version,
        "distribution_name": item.distribution_name,
        "distribution_version": item.distribution_version,
        "summary": item.summary,
        "citations": list(item.citations),
    }
    _emit(payload, output_format, output)


def export_command(
    result_file: str = typer.Argument(...),
    exporter: str = typer.Option(..., "--exporter"),
    output: str = typer.Option(..., "--output"),
    param: list[str] = typer.Option([], "--param"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    offline: bool = typer.Option(True, "--offline/--online"),
    output_format: str = typer.Option("text", "--format"),
) -> None:
    """Serialize a portable VascuQuest result through a registered exporter."""

    result = _result_file(result_file)
    session = _open_session(dataset, offline=offline)
    if result.dataset_identity != session.identity:
        raise SelectionError("result-file dataset identity does not match the opened dataset")
    exported = session.export(
        result,
        exporter,
        output,
        options=_parse_assignments(param, "--param") or None,
    )
    _emit(exported, output_format)


def reproduce_command(
    provenance_file: str = typer.Argument(...),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Strictly reproduce a saved declarative VascuQuest provenance document."""

    path = Path(provenance_file).expanduser()
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatasetUnavailableError(f"provenance file is unavailable: {path}") from exc
    provenance = provenance_from_json(payload)
    session = _open_session(dataset, source=source, offline=offline)
    result = session.reproduce(provenance)
    _emit(result, output_format, output)


def register_commands(app: typer.Typer) -> None:
    """Attach the exact frozen top-level command tree to one Typer application."""

    app.add_typer(dataset_app, name="dataset")
    app.command("subjects")(subjects_command)
    app.command("quantities")(quantities_command)
    app.command("locations")(locations_command)
    app.command("get")(get_command)
    app.command("waveform")(waveform_command)
    app.command("derive")(derive_command)
    app.command("model")(model_command)
    app.command("discover")(discover_command)
    app.add_typer(plugins_app, name="plugins")
    app.command("export")(export_command)
    app.command("reproduce")(reproduce_command)


__all__ = [
    "CANONICAL_DATASET",
    "dataset_app",
    "plugins_app",
    "register_commands",
]
