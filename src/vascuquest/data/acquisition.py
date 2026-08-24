"""Streaming acquisition of canonical source artifacts.

The implementation intentionally makes no claim of HTTP range/resume support.
Downloads are streamed to unique incomplete work files, verified against the
canonical manifest, and only then atomically promoted into the managed source
cache.
"""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import tempfile
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

from vascuquest.errors import DatasetUnavailableError, IntegrityError
from vascuquest.schema import ArtifactManifestEntry, CanonicalManifest, load_manifest

from .integrity import verify_artifact
from .paths import DataPaths
from .sources import SourceCandidate, SourceKind, SourceRegistry
from .state import ArtifactInspection, ArtifactState


_DEFAULT_CHUNK_SIZE = 1024 * 1024


def _default_opener(url: str):
    return urlopen(url, timeout=60)


def _validate_chunk_size(chunk_size: int) -> None:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an integer")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")


def _integrity_failure_message(
    artifact: ArtifactManifestEntry,
    inspections: list[ArtifactInspection],
) -> str:
    details: list[str] = []
    for inspection in inspections:
        observed = inspection.observed_checksum or inspection.state.value
        details.append(
            f"{inspection.path}: expected {artifact.checksum_value}, observed {observed}"
        )
    return (
        f"no usable copy of canonical artifact {artifact.artifact_id!r}; "
        + "; ".join(details)
    )


class ArtifactAcquirer:
    """Resolve, verify, and acquire only requested canonical artifacts."""

    __slots__ = ("_paths", "_registry", "_manifest", "_opener", "_chunk_size")

    def __init__(
        self,
        paths: DataPaths,
        registry: SourceRegistry,
        *,
        manifest: CanonicalManifest | None = None,
        opener: Callable[[str], object] | None = None,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> None:
        if not isinstance(paths, DataPaths):
            raise TypeError("paths must be DataPaths")
        if not isinstance(registry, SourceRegistry):
            raise TypeError("registry must be a SourceRegistry")
        resolved_manifest = load_manifest() if manifest is None else manifest
        if not isinstance(resolved_manifest, CanonicalManifest):
            raise TypeError("manifest must be a CanonicalManifest")
        if opener is not None and not callable(opener):
            raise TypeError("opener must be callable or None")
        _validate_chunk_size(chunk_size)
        self._paths = paths
        self._registry = registry
        self._manifest = resolved_manifest
        self._opener = _default_opener if opener is None else opener
        self._chunk_size = chunk_size

    def acquire(self, artifact_id: str, *, offline: bool = False) -> Path:
        """Return a verified canonical artifact using deterministic source precedence."""

        if not isinstance(artifact_id, str) or not artifact_id or artifact_id != artifact_id.strip():
            raise ValueError("artifact_id must be a non-empty trimmed string")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        try:
            artifact = self._manifest.artifact(artifact_id)
        except KeyError as exc:
            raise DatasetUnavailableError(f"unknown canonical artifact {artifact_id!r}") from exc

        self._paths.ensure()
        candidates = self._registry.candidates(artifact, self._paths, offline=offline)
        network_errors: list[str] = []
        integrity_failures: list[ArtifactInspection] = []

        for candidate in candidates:
            if candidate.local_path is not None:
                inspection = verify_artifact(
                    candidate.local_path,
                    artifact,
                    chunk_size=self._chunk_size,
                )
                if inspection.state is ArtifactState.VERIFIED:
                    return candidate.local_path
                if inspection.state in {
                    ArtifactState.CHECKSUM_FAILED,
                    ArtifactState.UNREADABLE,
                }:
                    integrity_failures.append(inspection)
                    if (
                        candidate.kind is SourceKind.VERIFIED_CACHE
                        and inspection.state is ArtifactState.CHECKSUM_FAILED
                        and candidate.local_path.is_file()
                    ):
                        candidate.local_path.unlink()
                continue

            try:
                return self._download_and_promote(candidate, artifact)
            except IntegrityError:
                raise
            except (OSError, URLError, TimeoutError) as exc:
                network_errors.append(f"{candidate.kind.value}: {exc}")
                continue

        if integrity_failures:
            raise IntegrityError(_integrity_failure_message(artifact, integrity_failures))
        if offline:
            raise DatasetUnavailableError(
                f"canonical artifact {artifact.artifact_id!r} is not available from any "
                "verified local source while offline"
            )
        detail = "; ".join(network_errors) if network_errors else "no usable source candidate"
        raise DatasetUnavailableError(
            f"unable to acquire canonical artifact {artifact.artifact_id!r}: {detail}"
        )

    def _download_and_promote(
        self,
        candidate: SourceCandidate,
        artifact: ArtifactManifestEntry,
    ) -> Path:
        if candidate.kind not in {SourceKind.MIRROR, SourceKind.CANONICAL}:
            raise ValueError("network acquisition requires a mirror or canonical candidate")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=self._paths.work,
                prefix=f"{artifact.filename}.",
                suffix=".part",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                response = self._opener(candidate.locator)
                with closing(response):
                    while True:
                        chunk = response.read(self._chunk_size)
                        if not chunk:
                            break
                        if not isinstance(chunk, (bytes, bytearray)):
                            raise OSError("network source returned non-byte content")
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            inspection = verify_artifact(
                temporary_path,
                artifact,
                chunk_size=self._chunk_size,
            )
            if inspection.state is not ArtifactState.VERIFIED:
                raise IntegrityError(
                    f"downloaded artifact {artifact.artifact_id!r} failed canonical verification: "
                    f"expected {artifact.checksum_value}, observed "
                    f"{inspection.observed_checksum or inspection.state.value}"
                )

            final_path = self._paths.source_artifact(artifact.filename)
            if final_path.exists():
                existing = verify_artifact(
                    final_path,
                    artifact,
                    chunk_size=self._chunk_size,
                )
                if existing.state is ArtifactState.VERIFIED:
                    temporary_path.unlink()
                    temporary_path = None
                    return final_path
                if not final_path.is_file():
                    raise IntegrityError(
                        f"managed source destination {final_path} is not a regular file"
                    )
                final_path.unlink()

            os.replace(temporary_path, final_path)
            temporary_path = None
            return final_path
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


__all__ = ["ArtifactAcquirer"]
