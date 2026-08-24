"""Bounded common-site waveform reads from the authoritative PWDB CSV archive."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import math
from pathlib import Path, PurePosixPath
import zipfile

from vascuquest.errors import IntegrityError, SchemaError, SelectionError

SAMPLE_RATE_HZ = 500.0


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
class WaveformSeries:
    """One source row with explicit time, missing, and padding semantics."""
    values: tuple[float, ...]
    time_seconds: tuple[float, ...]
    missing_mask: tuple[bool, ...]
    padding_mask: tuple[bool, ...]
    source_member: str
    source_signal: str
    sample_rate_hz: float = SAMPLE_RATE_HZ


class WaveformCSVArchiveReader:
    """Read one subject/site/signal row without extracting the full archive."""
    __slots__ = ("_archive_path",)

    def __init__(self, archive_path: Path) -> None:
        if not isinstance(archive_path, Path):
            raise TypeError("archive_path must be a pathlib.Path")
        self._archive_path = archive_path

    def read(self, *, subject_id: str, site_id: str, source_signal: str) -> WaveformSeries:
        subject_number = _subject_number(subject_id)
        if not isinstance(site_id, str) or not site_id or site_id != site_id.strip():
            raise SelectionError("site_id must be a non-empty trimmed string")
        if source_signal not in {"P", "U", "A", "PPG"}:
            raise SelectionError(f"unsupported PWDB common-site signal {source_signal!r}")

        basename = f"PWs_{site_id}_{source_signal}.csv"
        target_subject = str(subject_number)
        try:
            with zipfile.ZipFile(self._archive_path, "r") as archive:
                info = _member_with_basename(archive, basename)
                with archive.open(info, "r") as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                    reader = csv.reader(text, skipinitialspace=True)
                    try:
                        header = tuple(value.strip() for value in next(reader))
                    except StopIteration as exc:
                        raise SchemaError(f"waveform source {basename!r} is empty") from exc
                    if not header or header[0] != "Subject Number":
                        raise SchemaError(f"waveform source {basename!r} lacks leading 'Subject Number'")
                    sample_fields = header[1:]
                    expected = tuple(f"pt{index}" for index in range(1, len(sample_fields) + 1))
                    if sample_fields != expected:
                        raise SchemaError(f"waveform source {basename!r} has non-canonical sample columns")

                    selected: tuple[str, ...] | None = None
                    for line_no, values in enumerate(reader, start=2):
                        if not values or all(not value.strip() for value in values):
                            continue
                        if len(values) != len(header):
                            raise SchemaError(f"waveform row {line_no} has {len(values)} fields; expected {len(header)}")
                        raw_subject = values[0].strip()
                        try:
                            canonical = str(int(raw_subject, 10))
                        except ValueError as exc:
                            raise SchemaError(f"waveform row {line_no} has invalid Subject Number {raw_subject!r}") from exc
                        if canonical != raw_subject or int(canonical) < 1:
                            raise SchemaError(f"waveform row {line_no} has invalid Subject Number {raw_subject!r}")
                        if canonical == target_subject:
                            if selected is not None:
                                raise SchemaError(f"duplicate subject {target_subject!r} in {basename!r}")
                            selected = tuple(values[1:])
        except (OSError, zipfile.BadZipFile) as exc:
            raise IntegrityError(f"unable to read verified waveform archive {self._archive_path}") from exc

        if selected is None:
            raise SelectionError(f"subject {target_subject!r} is absent from waveform source {basename!r}")

        parsed: list[float] = []
        raw_missing: list[bool] = []
        for index, raw_value in enumerate(selected, start=1):
            text = raw_value.strip()
            if not text or text.lower() == "nan":
                parsed.append(math.nan)
                raw_missing.append(True)
                continue
            try:
                value = float(text)
            except ValueError as exc:
                raise SchemaError(f"waveform sample pt{index} is not numeric: {raw_value!r}") from exc
            if not math.isfinite(value):
                if math.isnan(value):
                    parsed.append(math.nan)
                    raw_missing.append(True)
                    continue
                raise SchemaError(f"waveform sample pt{index} contains non-finite value {raw_value!r}")
            parsed.append(value)
            raw_missing.append(False)

        last_present = -1
        for index, missing in enumerate(raw_missing):
            if not missing:
                last_present = index
        padding = tuple(bool(missing and last_present >= 0 and index > last_present) for index, missing in enumerate(raw_missing))
        missing = tuple(bool(is_missing and not is_padding) for is_missing, is_padding in zip(raw_missing, padding, strict=True))
        times = tuple(index / SAMPLE_RATE_HZ for index in range(len(parsed)))
        return WaveformSeries(tuple(parsed), times, missing, padding, info.filename, source_signal)


__all__ = ["SAMPLE_RATE_HZ", "WaveformCSVArchiveReader", "WaveformSeries"]
