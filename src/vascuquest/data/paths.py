"""Cross-platform managed filesystem locations for VascuQuest data state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_data_path, user_state_path


_APP_NAME = "VascuQuest"
_APP_AUTHOR = "VascuQuest"


def _safe_leaf(name: str, field_name: str) -> str:
    if not isinstance(name, str):
        raise TypeError(f"{field_name} must be a string")
    if not name or name != name.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed string")
    if name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"{field_name} must be a single filesystem leaf name")
    return name


@dataclass(frozen=True, slots=True)
class DataPaths:
    """Separated VascuQuest persistence namespaces.

    Canonical source artifacts, incomplete download work, and user results use
    the persistent data root so verified work can be atomically promoted into
    ``source/``. Rebuildable derived products use the cache root; state metadata
    uses the platform state location. No path is inside the installed package.
    """

    source: Path
    work: Path
    derived: Path
    results: Path
    state: Path

    def __post_init__(self) -> None:
        for field_name in ("source", "work", "derived", "results", "state"):
            value = getattr(self, field_name)
            if not isinstance(value, Path):
                raise TypeError(f"{field_name} must be a pathlib.Path")

    @classmethod
    def default(cls) -> "DataPaths":
        """Return platform-appropriate managed VascuQuest paths."""

        data_root = Path(user_data_path(_APP_NAME, _APP_AUTHOR))
        cache_root = Path(user_cache_path(_APP_NAME, _APP_AUTHOR))
        state_root = Path(user_state_path(_APP_NAME, _APP_AUTHOR))
        return cls(
            source=data_root / "source",
            work=data_root / "work",
            derived=cache_root / "derived",
            results=data_root / "results",
            state=state_root,
        )

    @classmethod
    def under(cls, root: Path) -> "DataPaths":
        """Construct all namespaces below one explicit root for tests/local isolation."""

        if not isinstance(root, Path):
            raise TypeError("root must be a pathlib.Path")
        return cls(
            source=root / "source",
            work=root / "work",
            derived=root / "derived",
            results=root / "results",
            state=root / "state",
        )

    def ensure(self) -> None:
        """Create managed namespace directories if absent."""

        for path in (self.source, self.work, self.derived, self.results, self.state):
            path.mkdir(parents=True, exist_ok=True)

    def source_artifact(self, filename: str) -> Path:
        """Return the managed canonical-source cache path for one filename."""

        return self.source / _safe_leaf(filename, "filename")

    def incomplete_download(self, filename: str) -> Path:
        """Return a clearly incomplete work path for a streamed download."""

        return self.work / f"{_safe_leaf(filename, 'filename')}.part"

    def state_file(self, filename: str) -> Path:
        """Return a managed state-file path."""

        return self.state / _safe_leaf(filename, "filename")


__all__ = ["DataPaths"]
