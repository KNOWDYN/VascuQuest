"""Safe extraction helpers for source ZIP containers."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

from vascuquest.errors import IntegrityError


_INCOMPLETE_MARKER = ".vascuquest-extraction-incomplete"


def _validate_member_name(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name:
        raise IntegrityError("ZIP member names must be non-empty strings")
    if "\\" in name:
        raise IntegrityError(f"ZIP member uses unsafe backslash path syntax: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise IntegrityError(f"ZIP member escapes extraction destination: {name!r}")
    if path.parts and path.parts[0].endswith(":"):
        raise IntegrityError(f"ZIP member uses an absolute drive path: {name!r}")
    if path.name == _INCOMPLETE_MARKER:
        raise IntegrityError("ZIP member collides with VascuQuest extraction state marker")
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == stat.S_IFLNK


def safe_extract_zip(
    archive_path: Path,
    destination: Path,
    *,
    members: tuple[str, ...] | None = None,
) -> tuple[Path, ...]:
    """Extract validated ZIP members while preventing filesystem traversal.

    A marker remains when extraction fails or is interrupted, so partial output
    cannot be mistaken for a complete derived/access cache. The canonical ZIP
    itself is never modified or deleted.
    """

    if not isinstance(archive_path, Path):
        raise TypeError("archive_path must be a pathlib.Path")
    if not isinstance(destination, Path):
        raise TypeError("destination must be a pathlib.Path")
    if members is not None:
        if not isinstance(members, tuple):
            raise TypeError("members must be a tuple of member names or None")
        if len(set(members)) != len(members):
            raise ValueError("members must not contain duplicate names")
        for member in members:
            if not isinstance(member, str) or not member:
                raise ValueError("members must contain non-empty strings")

    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    marker = destination / _INCOMPLETE_MARKER
    marker.write_text("incomplete\n", encoding="utf-8")

    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(set(names)) != len(names):
                raise IntegrityError("ZIP archive contains duplicate member names")
            by_name = {info.filename: info for info in infos}

            if members is None:
                selected = infos
            else:
                missing = [name for name in members if name not in by_name]
                if missing:
                    raise IntegrityError(
                        f"requested ZIP members are absent: {', '.join(sorted(missing))}"
                    )
                selected = [by_name[name] for name in members]

            for info in selected:
                relative = _validate_member_name(info.filename)
                if _is_symlink(info):
                    raise IntegrityError(
                        f"ZIP symbolic-link members are not supported: {info.filename!r}"
                    )

                target = destination.joinpath(*relative.parts)
                resolved_target = target.resolve(strict=False)
                try:
                    resolved_target.relative_to(destination_root)
                except ValueError as exc:
                    raise IntegrityError(
                        f"ZIP member escapes extraction destination: {info.filename!r}"
                    ) from exc

                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                if target.exists() and target.is_symlink():
                    raise IntegrityError(
                        f"refusing to overwrite symbolic-link extraction target: {target}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                extracted.append(target)

        marker.unlink()
        return tuple(extracted)
    except Exception:
        # Marker intentionally remains to signal partial/incomplete extraction.
        raise


__all__ = ["safe_extract_zip"]
