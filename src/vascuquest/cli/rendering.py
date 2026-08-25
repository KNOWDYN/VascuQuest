"""Deterministic CLI presentation without scientific computation.

The renderer converts already-constructed application/domain results into
terminal or machine-readable text. Scientific JSON reuses the canonical result
document assembled by the built-in JSON exporter so the CLI does not maintain a
second scientific-result schema.
"""

from __future__ import annotations

import csv
from dataclasses import fields, is_dataclass
from enum import Enum
import io
import json
from pathlib import Path
from collections.abc import Mapping, Sequence

import numpy as np

from vascuquest.domain.result import ScientificResult
from vascuquest.exporters.json_exporter import _document as _scientific_document


SUPPORTED_FORMATS = ("text", "json", "jsonl", "csv")


class RenderingError(ValueError):
    """Raised when a requested CLI presentation would be ambiguous or lossy."""


def _portable(value: object) -> object:
    if isinstance(value, ScientificResult):
        return _scientific_document(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _portable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _portable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_portable(item) for item in value]
    if isinstance(value, list):
        return [_portable(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, "__dict__"):
        return {
            key: _portable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def _json_text(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        _portable(value),
        sort_keys=True,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def _jsonl_text(value: object) -> str:
    if isinstance(value, (str, bytes, Mapping, ScientificResult)) or not isinstance(value, Sequence):
        raise RenderingError("jsonl output requires an ordered collection of records")
    lines = [
        json.dumps(
            _portable(item),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        for item in value
    ]
    return ("\n".join(lines) + "\n") if lines else ""


def _record_mapping(value: object) -> dict[str, object]:
    portable = _portable(value)
    if not isinstance(portable, Mapping):
        raise RenderingError("csv output requires row-oriented record mappings")
    result: dict[str, object] = {}
    for key, item in portable.items():
        if item is None or isinstance(item, (str, bool, int, float)):
            result[str(key)] = item
        elif isinstance(item, list) and all(
            element is None or isinstance(element, (str, bool, int, float))
            for element in item
        ):
            result[str(key)] = json.dumps(item, separators=(",", ":"), ensure_ascii=False)
        else:
            raise RenderingError(
                f"csv output cannot faithfully flatten structured field {key!r}"
            )
    return result


def _csv_text(value: object) -> str:
    if isinstance(value, ScientificResult):
        raise RenderingError(
            "scientific-result CSV presentation is not implicit; use the explicit vascuquest:csv exporter"
        )
    if isinstance(value, (str, bytes, Mapping)):
        rows_source = [value]
    elif isinstance(value, Sequence):
        rows_source = list(value)
    else:
        rows_source = [value]
    rows = [_record_mapping(item) for item in rows_source]
    if not rows:
        return ""
    headers = tuple(rows[0])
    if any(tuple(row) != headers for row in rows):
        raise RenderingError("csv rows must have identical ordered fields")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def serialize_primary(value: object, output_format: str) -> str:
    """Serialize one primary CLI result according to the frozen presentation modes."""

    if output_format not in SUPPORTED_FORMATS:
        raise RenderingError(
            f"unsupported output format {output_format!r}; choose one of {SUPPORTED_FORMATS!r}"
        )
    if output_format == "json":
        return _json_text(value)
    if output_format == "jsonl":
        return _jsonl_text(value)
    if output_format == "csv":
        return _csv_text(value)
    return _json_text(value, indent=2)


def write_primary(text: str, output: str | Path | None) -> Path | None:
    """Write UTF-8 primary output to a file, or return None for stdout dispatch."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if output is None:
        return None
    path = Path(output).expanduser()
    if path.exists() and path.is_dir():
        raise RenderingError(f"output path is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


__all__ = [
    "RenderingError",
    "SUPPORTED_FORMATS",
    "serialize_primary",
    "write_primary",
]
