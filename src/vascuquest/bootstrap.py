"""Explicit composition root for the built-in VascuQuest runtime."""

from __future__ import annotations

from pathlib import Path

from vascuquest.api import DatasetSession
from vascuquest.backends.pwdb3275625 import PWDB3275625Backend
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry
from vascuquest.errors import DatasetUnavailableError
from vascuquest.plugins.descriptor import ComponentKind
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.backend import DatasetBackend
from vascuquest.schema import CanonicalSchema, load_canonical_schema
from vascuquest.services import (
    DatasetService,
    ExecutionService,
    ExportingService,
    ReproductionService,
    RetrievalService,
    SelectionService,
)

_CANONICAL_DATASET_IDS = frozenset({"pwdb", "pwdb:3275625"})


def _compose_session(
    backend: DatasetBackend,
    *,
    registry: PluginRegistry | None = None,
    schema: CanonicalSchema | None = None,
) -> DatasetSession:
    resolved_schema = load_canonical_schema() if schema is None else schema
    resolved_registry = PluginRegistry() if registry is None else registry
    if not isinstance(resolved_registry, PluginRegistry):
        raise TypeError("registry must be a PluginRegistry")

    datasets = DatasetService(backend, schema=resolved_schema)
    selection = SelectionService(backend)
    retrieval = RetrievalService(backend, selection)
    execution = ExecutionService(resolved_registry, retrieval)
    exporting = ExportingService(resolved_registry)
    reproduction = ReproductionService(
        retrieval,
        datasets.identity,
        schema=resolved_schema,
    )
    return DatasetSession(
        datasets=datasets,
        selection=selection,
        retrieval=retrieval,
        execution=execution,
        exporting=exporting,
        reproduction=reproduction,
    )


def open_dataset(
    dataset: str = "pwdb:3275625",
    *,
    source: str | Path | None = None,
    offline: bool = False,
) -> DatasetSession:
    """Open the canonical PWDB dataset without eagerly acquiring artifacts."""

    if not isinstance(dataset, str) or not dataset or dataset != dataset.strip():
        raise ValueError("dataset must be a non-empty trimmed identifier")
    if dataset not in _CANONICAL_DATASET_IDS:
        raise DatasetUnavailableError(
            f"unsupported dataset {dataset!r}; canonical v1 dataset is 'pwdb:3275625'"
        )
    if not isinstance(offline, bool):
        raise TypeError("offline must be a boolean")

    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    if source is not None:
        source_path = Path(source).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise DatasetUnavailableError(
                f"source must identify an existing local PWDB directory: {source_path}"
            )
        registry.register_local(source_path)

    acquirer = ArtifactAcquirer(paths, registry)
    backend = PWDB3275625Backend.from_acquirer(acquirer, offline=offline)
    plugins = PluginRegistry()
    plugins.register_factory(
        lambda: backend,
        expected_kind=ComponentKind.BACKEND,
        built_in=True,
    )
    plugins.discover_installed()
    return _compose_session(backend, registry=plugins)


def register_source(source: str | Path) -> Path:
    """Register an existing local canonical-source directory without copying it."""

    source_path = Path(source).expanduser()
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    try:
        return registry.register_local(source_path)
    except ValueError as exc:
        raise DatasetUnavailableError(str(exc)) from exc


__all__ = ["open_dataset", "register_source"]
