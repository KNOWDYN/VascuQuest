"""Registered local sources, institutional mirrors, and deterministic precedence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote, urlparse

from vascuquest.schema import ArtifactManifestEntry

from .paths import DataPaths


_REGISTRY_FORMAT_VERSION = 1


def _normalize_mirror(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url or base_url != base_url.strip():
        raise ValueError("base_url must be a non-empty trimmed string")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("mirror base_url must be an absolute HTTPS URL")
    return base_url.rstrip("/")


class SourceKind(str, Enum):
    """Operational source kinds, separate from canonical dataset identity."""

    REGISTERED_LOCAL = "registered_local"
    VERIFIED_CACHE = "verified_cache"
    MIRROR = "mirror"
    CANONICAL = "canonical"


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """One deterministic retrieval candidate for a canonical artifact."""

    kind: SourceKind
    locator: str
    local_path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SourceKind):
            raise TypeError("kind must be a SourceKind")
        if not isinstance(self.locator, str) or not self.locator:
            raise ValueError("locator must be a non-empty string")
        if self.locator != self.locator.strip():
            raise ValueError("locator must not contain leading or trailing whitespace")
        if self.local_path is not None and not isinstance(self.local_path, Path):
            raise TypeError("local_path must be a pathlib.Path or None")
        if self.kind in {SourceKind.REGISTERED_LOCAL, SourceKind.VERIFIED_CACHE}:
            if self.local_path is None:
                raise ValueError("local source candidates require local_path")
        elif self.local_path is not None:
            raise ValueError("network source candidates must not carry local_path")


class SourceRegistry:
    """Persist explicit local source roots and HTTPS institutional mirrors."""

    __slots__ = ("_state_file", "_local_roots", "_mirrors")

    def __init__(self, state_file: Path) -> None:
        if not isinstance(state_file, Path):
            raise TypeError("state_file must be a pathlib.Path")
        self._state_file = state_file
        self._local_roots: list[Path] = []
        self._mirrors: list[str] = []
        self._load()

    @property
    def local_roots(self) -> tuple[Path, ...]:
        """Registered external directories in deterministic registration order."""

        return tuple(self._local_roots)

    @property
    def mirrors(self) -> tuple[str, ...]:
        """Configured HTTPS mirror roots in deterministic registration order."""

        return tuple(self._mirrors)

    def register_local(self, directory: Path) -> Path:
        """Register an existing directory without copying or modifying its files."""

        if not isinstance(directory, Path):
            raise TypeError("directory must be a pathlib.Path")
        resolved = directory.expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError("registered local source must be an existing directory")
        if resolved not in self._local_roots:
            self._local_roots.append(resolved)
            self._save()
        return resolved

    def register_mirror(self, base_url: str) -> str:
        """Register an HTTPS institutional mirror root."""

        normalized = _normalize_mirror(base_url)
        if normalized not in self._mirrors:
            self._mirrors.append(normalized)
            self._save()
        return normalized

    def candidates(
        self,
        artifact: ArtifactManifestEntry,
        paths: DataPaths,
        *,
        offline: bool,
    ) -> tuple[SourceCandidate, ...]:
        """Return candidates in the frozen local/cache/mirror/canonical precedence."""

        if not isinstance(artifact, ArtifactManifestEntry):
            raise TypeError("artifact must be an ArtifactManifestEntry")
        if not isinstance(paths, DataPaths):
            raise TypeError("paths must be DataPaths")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")

        candidates: list[SourceCandidate] = []
        for root in self._local_roots:
            path = root / artifact.filename
            candidates.append(
                SourceCandidate(
                    SourceKind.REGISTERED_LOCAL,
                    str(path),
                    local_path=path,
                )
            )

        cache_path = paths.source_artifact(artifact.filename)
        candidates.append(
            SourceCandidate(
                SourceKind.VERIFIED_CACHE,
                str(cache_path),
                local_path=cache_path,
            )
        )

        if not offline:
            quoted_name = quote(artifact.filename)
            for mirror in self._mirrors:
                candidates.append(
                    SourceCandidate(
                        SourceKind.MIRROR,
                        f"{mirror}/{quoted_name}",
                    )
                )
            candidates.append(
                SourceCandidate(SourceKind.CANONICAL, artifact.source_locator)
            )

        return tuple(candidates)

    def _load(self) -> None:
        if not self._state_file.exists():
            return
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("source registry state is unreadable or invalid") from exc
        if not isinstance(payload, dict) or payload.get("format_version") != _REGISTRY_FORMAT_VERSION:
            raise ValueError("unsupported source registry state format")
        local_roots = payload.get("local_roots")
        mirrors = payload.get("mirrors")
        if not isinstance(local_roots, list) or not all(isinstance(v, str) for v in local_roots):
            raise ValueError("source registry local_roots must be a JSON string array")
        if not isinstance(mirrors, list) or not all(isinstance(v, str) for v in mirrors):
            raise ValueError("source registry mirrors must be a JSON string array")
        if len(set(local_roots)) != len(local_roots) or len(set(mirrors)) != len(mirrors):
            raise ValueError("source registry state must not contain duplicate sources")

        loaded_roots: list[Path] = []
        for value in local_roots:
            path = Path(value)
            if not path.is_absolute():
                raise ValueError("persisted local source roots must be absolute paths")
            loaded_roots.append(path)
        loaded_mirrors = [_normalize_mirror(value) for value in mirrors]

        self._local_roots = loaded_roots
        self._mirrors = loaded_mirrors

    def _save(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": _REGISTRY_FORMAT_VERSION,
            "local_roots": [str(path) for path in self._local_roots],
            "mirrors": list(self._mirrors),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self._state_file.parent,
                prefix=f".{self._state_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, self._state_file)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


__all__ = ["SourceCandidate", "SourceKind", "SourceRegistry"]
