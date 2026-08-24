"""Explicit local artifact verification states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ArtifactState(str, Enum):
    """Canonical local state of a source artifact."""

    MISSING = "missing"
    PRESENT_UNVERIFIED = "present_unverified"
    VERIFIED = "verified"
    CHECKSUM_FAILED = "checksum_failed"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    """Result of inspecting one local path against one manifest artifact identity."""

    artifact_id: str
    path: Path
    state: ArtifactState
    expected_checksum: str
    observed_checksum: str | None = None
    size_bytes: int | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_id, str) or not self.artifact_id:
            raise ValueError("artifact_id must be a non-empty string")
        if self.artifact_id != self.artifact_id.strip():
            raise ValueError("artifact_id must not contain leading or trailing whitespace")
        if not isinstance(self.path, Path):
            raise TypeError("path must be a pathlib.Path")
        if not isinstance(self.state, ArtifactState):
            raise TypeError("state must be an ArtifactState")
        if not isinstance(self.expected_checksum, str) or not self.expected_checksum:
            raise ValueError("expected_checksum must be a non-empty string")
        if self.observed_checksum is not None and not isinstance(self.observed_checksum, str):
            raise TypeError("observed_checksum must be a string or None")
        if self.size_bytes is not None:
            if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
                raise TypeError("size_bytes must be an integer or None")
            if self.size_bytes < 0:
                raise ValueError("size_bytes must not be negative")
        if self.detail is not None:
            if not isinstance(self.detail, str):
                raise TypeError("detail must be a string or None")
            if not self.detail or self.detail != self.detail.strip():
                raise ValueError("detail must be a non-empty trimmed string when present")

    @property
    def usable_as_canonical_source(self) -> bool:
        """Whether canonical scientific operations may use this local artifact silently."""

        return self.state is ArtifactState.VERIFIED


__all__ = ["ArtifactInspection", "ArtifactState"]
