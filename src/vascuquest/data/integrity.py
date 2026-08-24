"""Streaming canonical-artifact integrity verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from vascuquest.errors import DatasetUnavailableError, IntegrityError
from vascuquest.schema import ArtifactManifestEntry

from .state import ArtifactInspection, ArtifactState


_DEFAULT_CHUNK_SIZE = 1024 * 1024


def _validate_chunk_size(chunk_size: int) -> None:
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an integer")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")


def probe_artifact(path: Path, artifact: ArtifactManifestEntry) -> ArtifactInspection:
    """Inspect local presence/readability without claiming checksum verification."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    if not isinstance(artifact, ArtifactManifestEntry):
        raise TypeError("artifact must be an ArtifactManifestEntry")
    if not path.exists():
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            path=path,
            state=ArtifactState.MISSING,
            expected_checksum=artifact.checksum_value,
        )
    try:
        if not path.is_file():
            raise OSError("path is not a regular file")
        size = path.stat().st_size
    except OSError as exc:
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            path=path,
            state=ArtifactState.UNREADABLE,
            expected_checksum=artifact.checksum_value,
            detail=str(exc) or "artifact is unreadable",
        )
    return ArtifactInspection(
        artifact_id=artifact.artifact_id,
        path=path,
        state=ArtifactState.PRESENT_UNVERIFIED,
        expected_checksum=artifact.checksum_value,
        size_bytes=size,
    )


def compute_checksum(
    path: Path,
    algorithm: str,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute one checksum using bounded-memory streaming reads."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    if not isinstance(algorithm, str) or not algorithm:
        raise ValueError("algorithm must be a non-empty string")
    _validate_chunk_size(chunk_size)
    try:
        digest = hashlib.new(algorithm)
    except ValueError as exc:
        raise IntegrityError(f"unsupported checksum algorithm {algorithm!r}") from exc

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def verify_artifact(
    path: Path,
    artifact: ArtifactManifestEntry,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> ArtifactInspection:
    """Verify one local artifact against authoritative manifest metadata."""

    inspection = probe_artifact(path, artifact)
    if inspection.state is not ArtifactState.PRESENT_UNVERIFIED:
        return inspection

    if (
        artifact.reported_size_bytes is not None
        and inspection.size_bytes != artifact.reported_size_bytes
    ):
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            path=path,
            state=ArtifactState.CHECKSUM_FAILED,
            expected_checksum=artifact.checksum_value,
            size_bytes=inspection.size_bytes,
            detail=(
                f"size mismatch: expected {artifact.reported_size_bytes} bytes, "
                f"observed {inspection.size_bytes}"
            ),
        )

    try:
        observed = compute_checksum(
            path,
            artifact.checksum_algorithm,
            chunk_size=chunk_size,
        )
    except OSError as exc:
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            path=path,
            state=ArtifactState.UNREADABLE,
            expected_checksum=artifact.checksum_value,
            size_bytes=inspection.size_bytes,
            detail=str(exc) or "artifact became unreadable during verification",
        )

    state = (
        ArtifactState.VERIFIED
        if observed == artifact.checksum_value.lower()
        else ArtifactState.CHECKSUM_FAILED
    )
    return ArtifactInspection(
        artifact_id=artifact.artifact_id,
        path=path,
        state=state,
        expected_checksum=artifact.checksum_value,
        observed_checksum=observed,
        size_bytes=inspection.size_bytes,
        detail=None if state is ArtifactState.VERIFIED else "checksum mismatch",
    )


def require_verified_artifact(
    path: Path,
    artifact: ArtifactManifestEntry,
    *,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> Path:
    """Return ``path`` only when it verifies as the canonical manifest artifact."""

    inspection = verify_artifact(path, artifact, chunk_size=chunk_size)
    if inspection.state is ArtifactState.VERIFIED:
        return path
    if inspection.state is ArtifactState.MISSING:
        raise DatasetUnavailableError(
            f"required canonical artifact {artifact.artifact_id!r} is missing at {path}"
        )
    raise IntegrityError(
        f"canonical artifact {artifact.artifact_id!r} failed verification: "
        f"{inspection.state.value}"
        + (f" ({inspection.detail})" if inspection.detail else "")
    )


__all__ = [
    "compute_checksum",
    "probe_artifact",
    "require_verified_artifact",
    "verify_artifact",
]
