"""Strict readers for PWDB subject-indexed CSV source tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path

from vascuquest.errors import SchemaError, SelectionError

_SUBJECT_FIELD = "Subject Number"
_MISSING_TOKENS = frozenset({"", "na", "n/a", "nan"})


def _canonical_subject_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise SchemaError("PWDB CSV row has an empty Subject Number")
    try:
        number = int(value, 10)
    except ValueError as exc:
        raise SchemaError(f"invalid PWDB Subject Number {raw!r}") from exc
    if number < 1 or str(number) != value:
        raise SchemaError(f"PWDB Subject Number must be a positive canonical integer: {raw!r}")
    return str(number)


@dataclass(frozen=True, slots=True)
class NumericCell:
    """One source cell with explicit missing-value state."""

    value: float | None
    raw: str

    @property
    def missing(self) -> bool:
        return self.value is None


class SubjectCSVTable:
    """Lazy in-memory index of one explicit-subject PWDB CSV table.

    The reader never joins by row position. The authoritative ``Subject Number``
    field is normalized to the canonical decimal subject identifier and must be
    unique.
    """

    __slots__ = ("_path", "_fieldnames", "_subject_ids", "_rows")

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise TypeError("path must be a pathlib.Path")
        self._path = path
        self._fieldnames: tuple[str, ...] | None = None
        self._subject_ids: tuple[str, ...] | None = None
        self._rows: dict[str, dict[str, str]] | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def fieldnames(self) -> tuple[str, ...]:
        self._ensure_loaded()
        assert self._fieldnames is not None
        return self._fieldnames

    def subject_ids(self) -> tuple[str, ...]:
        self._ensure_loaded()
        assert self._subject_ids is not None
        return self._subject_ids

    def has_field(self, source_field: str) -> bool:
        if not isinstance(source_field, str) or not source_field:
            return False
        return source_field in self.fieldnames

    def numeric(self, subject_id: str, source_field: str) -> NumericCell:
        """Read one finite numeric value or an explicit missing value."""

        if not isinstance(subject_id, str) or not subject_id:
            raise SelectionError("subject_id must be a non-empty string")
        if not isinstance(source_field, str) or not source_field:
            raise SchemaError("source_field must be a non-empty string")
        self._ensure_loaded()
        assert self._rows is not None
        try:
            row = self._rows[subject_id]
        except KeyError as exc:
            raise SelectionError(
                f"subject {subject_id!r} is absent from {self._path.name}"
            ) from exc
        try:
            raw = row[source_field]
        except KeyError as exc:
            raise SchemaError(
                f"source field {source_field!r} is absent from {self._path.name}"
            ) from exc

        text = raw.strip()
        if text.lower() in _MISSING_TOKENS:
            return NumericCell(None, raw)
        try:
            value = float(text)
        except ValueError as exc:
            raise SchemaError(
                f"source field {source_field!r} for subject {subject_id!r} "
                f"is not numeric in {self._path.name}: {raw!r}"
            ) from exc
        if not math.isfinite(value):
            if math.isnan(value):
                return NumericCell(None, raw)
            raise SchemaError(
                f"source field {source_field!r} contains non-finite value {raw!r}"
            )
        return NumericCell(value, raw)

    def _ensure_loaded(self) -> None:
        if self._rows is not None:
            return
        if not self._path.exists() or not self._path.is_file():
            raise SchemaError(f"PWDB CSV source is unavailable: {self._path}")

        rows: dict[str, dict[str, str]] = {}
        order: list[str] = []
        try:
            with self._path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle, skipinitialspace=True)
                try:
                    raw_header = next(reader)
                except StopIteration as exc:
                    raise SchemaError(f"PWDB CSV source is empty: {self._path}") from exc
                fieldnames = tuple(value.strip() for value in raw_header)
                if any(not name for name in fieldnames):
                    raise SchemaError(f"PWDB CSV header contains an empty field: {self._path}")
                if len(set(fieldnames)) != len(fieldnames):
                    raise SchemaError(
                        f"PWDB CSV header contains duplicate fields after normalization: {self._path}"
                    )
                if _SUBJECT_FIELD not in fieldnames:
                    raise SchemaError(
                        f"PWDB CSV source lacks authoritative {_SUBJECT_FIELD!r}: {self._path}"
                    )
                subject_index = fieldnames.index(_SUBJECT_FIELD)

                for line_no, values in enumerate(reader, start=2):
                    if not values or all(not item.strip() for item in values):
                        continue
                    if len(values) != len(fieldnames):
                        raise SchemaError(
                            f"PWDB CSV row {line_no} has {len(values)} fields; "
                            f"expected {len(fieldnames)}"
                        )
                    subject_id = _canonical_subject_id(values[subject_index])
                    if subject_id in rows:
                        raise SchemaError(
                            f"duplicate PWDB Subject Number {subject_id!r} in {self._path.name}"
                        )
                    rows[subject_id] = {
                        field: value for field, value in zip(fieldnames, values, strict=True)
                    }
                    order.append(subject_id)
        except OSError as exc:
            raise SchemaError(f"unable to read PWDB CSV source {self._path}") from exc

        if not rows:
            raise SchemaError(f"PWDB CSV source contains no subject rows: {self._path}")
        self._fieldnames = fieldnames
        self._subject_ids = tuple(order)
        self._rows = rows


__all__ = ["NumericCell", "SubjectCSVTable"]
