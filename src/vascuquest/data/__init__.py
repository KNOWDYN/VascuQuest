"""Local source registration, integrity, acquisition, and archive utilities."""

from .acquisition import ArtifactAcquirer
from .archive import safe_extract_zip
from .integrity import (
    compute_checksum,
    probe_artifact,
    require_verified_artifact,
    verify_artifact,
)
from .paths import DataPaths
from .sources import SourceCandidate, SourceKind, SourceRegistry
from .state import ArtifactInspection, ArtifactState

__all__ = [
    "ArtifactAcquirer",
    "ArtifactInspection",
    "ArtifactState",
    "DataPaths",
    "SourceCandidate",
    "SourceKind",
    "SourceRegistry",
    "compute_checksum",
    "probe_artifact",
    "require_verified_artifact",
    "safe_extract_zip",
    "verify_artifact",
]
