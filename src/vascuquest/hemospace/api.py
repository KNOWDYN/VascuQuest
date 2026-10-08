"""Public composition entrypoint for the VascuQuest HEMOSPACE operation mode."""

from __future__ import annotations

from pathlib import Path

from vascuquest.bootstrap import open_dataset
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry

from .service import HemospaceSession


def open_hemospace(
    dataset: str = "pwdb:3275625",
    *,
    source: str | Path | None = None,
    offline: bool = False,
) -> HemospaceSession:
    """Open HEMOSPACE over the same canonical dataset/acquisition state as VascuQuest."""

    session = open_dataset(dataset, source=source, offline=offline)
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry)

    def resolve(artifact_id: str) -> Path:
        return acquirer.acquire(artifact_id, offline=offline)

    return HemospaceSession(session, resolve)


__all__ = ["open_hemospace"]
