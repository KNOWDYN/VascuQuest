"""Direct, bounded readers for verified PWDB geometry ZIP archives."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import math
from pathlib import Path, PurePosixPath
import zipfile

from vascuquest.errors import IntegrityError, SchemaError, SelectionError

_REQUIRED_FIELDS = (
    "seg_no", "inlet_node", "outlet_node", "length", "inlet_radius",
    "outlet_radius", "peripheral_c", "peripheral_r",
)


def _canonical_positive_integer(raw: str, field_name: str) -> int:
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise SchemaError(f"{field_name} must be numeric: {raw!r}") from exc
    if not math.isfinite(value) or value < 1 or not value.is_integer():
        raise SchemaError(f"{field_name} must be a positive integer: {raw!r}")
    return int(value)


def _finite_float(raw: str, field_name: str) -> float:
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise SchemaError(f"{field_name} must be numeric: {raw!r}") from exc
    if not math.isfinite(value):
        raise SchemaError(f"{field_name} must be finite: {raw!r}")
    return value


def _subject_number(subject_id: str) -> int:
    if not isinstance(subject_id, str) or not subject_id:
        raise SelectionError("subject_id must be a non-empty canonical subject identifier")
    try:
        value = int(subject_id, 10)
    except ValueError as exc:
        raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}") from exc
    if value < 1 or str(value) != subject_id:
        raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}")
    return value


def _member_with_basename(archive: zipfile.ZipFile, basename: str) -> zipfile.ZipInfo:
    matches = [info for info in archive.infolist() if not info.is_dir() and PurePosixPath(info.filename).name == basename]
    if not matches:
        raise SelectionError(f"source archive does not contain {basename!r}")
    if len(matches) != 1:
        raise IntegrityError(f"source archive contains ambiguous members named {basename!r}")
    return matches[0]


@dataclass(frozen=True, slots=True)
class GeometrySegment:
    """One source-provided network segment without invented spatial geometry."""
    segment_id: str
    inlet_node: int
    outlet_node: int
    length_m: float
    inlet_radius_m: float
    outlet_radius_m: float
    peripheral_c: float
    peripheral_r: float


@dataclass(frozen=True, slots=True)
class GeometrySource:
    """Bounded geometry read plus exact source member identity."""
    segments: tuple[GeometrySegment, ...]
    source_member: str


class GeometryCSVArchiveReader:
    """Read one subject-specific geometry CSV directly from the verified ZIP."""
    __slots__ = ("_archive_path",)

    def __init__(self, archive_path: Path) -> None:
        if not isinstance(archive_path, Path):
            raise TypeError("archive_path must be a pathlib.Path")
        self._archive_path = archive_path

    def read_subject(self, subject_id: str) -> GeometrySource:
        subject_number = _subject_number(subject_id)
        basename = f"pwdb_geo_{subject_number:04d}.csv"
        try:
            with zipfile.ZipFile(self._archive_path, "r") as archive:
                info = _member_with_basename(archive, basename)
                with archive.open(info, "r") as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                    reader = csv.DictReader(text, skipinitialspace=True)
                    if reader.fieldnames is None:
                        raise SchemaError(f"geometry source {basename!r} has no header")
                    fieldnames = tuple(name.strip() for name in reader.fieldnames)
                    missing = set(_REQUIRED_FIELDS) - set(fieldnames)
                    if missing:
                        raise SchemaError(f"geometry source {basename!r} lacks fields {sorted(missing)!r}")
                    segments: list[GeometrySegment] = []
                    seen: set[str] = set()
                    for line_no, raw_row in enumerate(reader, start=2):
                        row = {key.strip(): (value or "").strip() for key, value in raw_row.items() if key is not None}
                        segment_no = _canonical_positive_integer(row["seg_no"], "seg_no")
                        segment_id = str(segment_no)
                        if segment_id in seen:
                            raise SchemaError(f"duplicate geometry segment {segment_id!r} in {basename!r}")
                        seen.add(segment_id)
                        inlet_node = _canonical_positive_integer(row["inlet_node"], "inlet_node")
                        outlet_node = _canonical_positive_integer(row["outlet_node"], "outlet_node")
                        length_m = _finite_float(row["length"], "length")
                        inlet_radius_m = _finite_float(row["inlet_radius"], "inlet_radius")
                        outlet_radius_m = _finite_float(row["outlet_radius"], "outlet_radius")
                        peripheral_c = _finite_float(row["peripheral_c"], "peripheral_c")
                        peripheral_r = _finite_float(row["peripheral_r"], "peripheral_r")
                        if length_m <= 0 or inlet_radius_m <= 0 or outlet_radius_m <= 0:
                            raise SchemaError(f"geometry row {line_no} has non-positive length/radius")
                        segments.append(GeometrySegment(segment_id, inlet_node, outlet_node, length_m, inlet_radius_m, outlet_radius_m, peripheral_c, peripheral_r))
        except (OSError, zipfile.BadZipFile) as exc:
            raise IntegrityError(f"unable to read verified geometry archive {self._archive_path}") from exc
        if not segments:
            raise SchemaError(f"geometry source {basename!r} contains no segment rows")
        return GeometrySource(tuple(segments), info.filename)


__all__ = ["GeometryCSVArchiveReader", "GeometrySegment", "GeometrySource"]
