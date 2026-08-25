"""Deterministic portable JSON export for bounded scientific results.

The JSON exporter serializes one complete result document: scientific metadata,
values, coordinate values, and waveform masks. It does not fetch provenance,
recompute values, convert units, or alter evidence semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from vascuquest._version import __version__
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.errors import CapabilityError, ReproducibilityError
from vascuquest.plugins.descriptor import (
    ComponentDescriptor,
    ComponentKind,
    SUPPORTED_PROTOCOL_VERSION,
)
from vascuquest.provenance.serialization import (
    result_metadata_from_dict,
    result_metadata_to_dict,
)


JSON_EXPORTER_ID = "vascuquest:json"
_JSON_DOCUMENT_FORMAT = "vascuquest-result-json"
_JSON_DOCUMENT_VERSION = 1
_TYPE_MARKER = "__vascuquest_type__"


def _portable_scalar(value: object) -> object:
    if isinstance(value, np.generic):
        return _portable_scalar(value.item())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {_TYPE_MARKER: "float", "value": "nan"}
        if math.isinf(value):
            return {
                _TYPE_MARKER: "float",
                "value": "positive_infinity" if value > 0 else "negative_infinity",
            }
        return value
    return None


def _encode_portable(value: object) -> object:
    """Encode supported bounded values into strict JSON-compatible structures."""

    scalar = _portable_scalar(value)
    if scalar is not None or value is None:
        return scalar

    if isinstance(value, np.ndarray):
        return {
            _TYPE_MARKER: "ndarray",
            "dtype": value.dtype.str,
            "shape": list(value.shape),
            "data": _encode_portable(value.tolist()),
        }
    if isinstance(value, Enum):
        return {
            _TYPE_MARKER: "enum",
            "enum_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _encode_portable(value.value),
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {
            _TYPE_MARKER: "record",
            "record_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _encode_portable(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if isinstance(value, tuple):
        return {
            _TYPE_MARKER: "tuple",
            "items": [_encode_portable(item) for item in value],
        }
    if isinstance(value, list):
        return {
            _TYPE_MARKER: "list",
            "items": [_encode_portable(item) for item in value],
        }
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise CapabilityError("portable JSON result mappings require string keys")
        return {
            _TYPE_MARKER: "mapping",
            "items": [
                [key, _encode_portable(value[key])]
                for key in sorted(value)
            ],
        }
    raise CapabilityError(
        f"result contains a value of unsupported portable JSON type {type(value).__name__!r}"
    )


def _decode_portable(value: object) -> object:
    """Decode the strict portable value representation used by this exporter."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if not isinstance(value, Mapping):
        raise ReproducibilityError("portable JSON value must be a scalar or mapping")
    marker = value.get(_TYPE_MARKER)
    if marker == "float":
        label = value.get("value")
        if label == "nan":
            return float("nan")
        if label == "positive_infinity":
            return float("inf")
        if label == "negative_infinity":
            return float("-inf")
        raise ReproducibilityError("unknown portable non-finite float marker")
    if marker == "ndarray":
        dtype = value.get("dtype")
        shape = value.get("shape")
        if not isinstance(dtype, str) or not isinstance(shape, list):
            raise ReproducibilityError("invalid portable ndarray metadata")
        decoded = _decode_portable(value.get("data"))
        try:
            array = np.asarray(decoded, dtype=np.dtype(dtype))
        except (TypeError, ValueError) as exc:
            raise ReproducibilityError("unable to rebuild portable ndarray") from exc
        if list(array.shape) != shape:
            raise ReproducibilityError("portable ndarray shape does not match encoded data")
        array.setflags(write=False)
        return array
    if marker == "enum":
        return _decode_portable(value.get("value"))
    if marker == "record":
        record_type = value.get("record_type")
        raw_fields = value.get("fields")
        if not isinstance(record_type, str) or not isinstance(raw_fields, Mapping):
            raise ReproducibilityError("invalid portable record representation")
        if any(not isinstance(key, str) for key in raw_fields):
            raise ReproducibilityError("portable record field names must be strings")
        return {
            "__record_type__": record_type,
            **{key: _decode_portable(raw_fields[key]) for key in sorted(raw_fields)},
        }
    if marker in {"tuple", "list"}:
        items = value.get("items")
        if not isinstance(items, list):
            raise ReproducibilityError("portable sequence items must be a JSON array")
        decoded_items = [_decode_portable(item) for item in items]
        return tuple(decoded_items) if marker == "tuple" else decoded_items
    if marker == "mapping":
        items = value.get("items")
        if not isinstance(items, list):
            raise ReproducibilityError("portable mapping items must be a JSON array")
        decoded: dict[str, object] = {}
        for item in items:
            if (
                not isinstance(item, list)
                or len(item) != 2
                or not isinstance(item[0], str)
                or item[0] in decoded
            ):
                raise ReproducibilityError("invalid portable mapping item")
            decoded[item[0]] = _decode_portable(item[1])
        return decoded
    raise ReproducibilityError("unknown portable JSON type marker")


def _destination_path(destination: object) -> Path:
    if isinstance(destination, os.PathLike):
        path = Path(destination)
    elif isinstance(destination, str):
        if not destination or destination != destination.strip():
            raise ValueError("export destination must be a non-empty trimmed path")
        path = Path(destination)
    else:
        raise TypeError("export destination must be a filesystem path")
    path = path.expanduser()
    if path.exists() and path.is_dir():
        raise CapabilityError(f"export destination is a directory: {path}")
    return path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise CapabilityError(f"unable to write export destination {path}") from exc


def _document(result: ScientificResult) -> dict[str, object]:
    coordinates = {
        coordinate.name: _encode_portable(coordinate.values)
        for coordinate in result.coordinates
    }
    payload: dict[str, object] = {
        "format": _JSON_DOCUMENT_FORMAT,
        "format_version": _JSON_DOCUMENT_VERSION,
        "metadata": result_metadata_to_dict(result),
        "values": _encode_portable(result.values),
        "coordinate_values": coordinates,
    }
    if isinstance(result, Waveform):
        payload["missing_mask"] = (
            None if result.missing_mask is None else _encode_portable(result.missing_mask)
        )
        payload["padding_mask"] = (
            None if result.padding_mask is None else _encode_portable(result.padding_mask)
        )
    return payload


class JSONResultExporter:
    """Serialize a complete bounded scientific result as strict JSON."""

    @property
    def descriptor(self) -> ComponentDescriptor:
        return ComponentDescriptor(
            kind=ComponentKind.EXPORTER,
            name="VascuQuest JSON result exporter",
            qualified_id=JSON_EXPORTER_ID,
            implementation_version=__version__,
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="vascuquest",
            distribution_version=__version__,
            summary="Deterministic portable JSON export for bounded scientific results.",
        )

    @property
    def supported_result_kinds(self) -> tuple[str, ...]:
        return ("scientific_result", "waveform")

    @property
    def supported_output_formats(self) -> tuple[str, ...]:
        return ("json",)

    @property
    def provenance_retention(self) -> str:
        return (
            "Retains the result provenance reference and all scientific metadata "
            "owned by the ScientificResult; no provenance lookup is performed."
        )

    def export(
        self,
        result: ScientificResult,
        destination: object,
        options: Mapping[str, object],
    ) -> Path:
        if not isinstance(result, ScientificResult):
            raise TypeError("result must be a ScientificResult")
        if not isinstance(options, Mapping):
            raise TypeError("options must be a mapping")
        if options:
            raise ValueError("the v1 JSON exporter defines no export options")
        path = _destination_path(destination)
        text = json.dumps(
            _document(result),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
        _atomic_write_text(path, text)
        return path


def load_result_json(source: str | os.PathLike[str]) -> ScientificResult:
    """Rebuild a result previously written by :class:`JSONResultExporter`."""

    path = _destination_path(source)
    try:
        with path.open("r", encoding="utf-8") as handle:
            document: Any = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproducibilityError(f"unable to read VascuQuest JSON result {path}") from exc
    if not isinstance(document, Mapping):
        raise ReproducibilityError("VascuQuest JSON result must be a JSON object")
    if document.get("format") != _JSON_DOCUMENT_FORMAT:
        raise ReproducibilityError("unknown VascuQuest JSON result format")
    if document.get("format_version") != _JSON_DOCUMENT_VERSION:
        raise ReproducibilityError("unsupported VascuQuest JSON result format_version")
    metadata = document.get("metadata")
    raw_coordinates = document.get("coordinate_values")
    if not isinstance(raw_coordinates, Mapping):
        raise ReproducibilityError("JSON result coordinate_values must be a mapping")
    if any(not isinstance(name, str) for name in raw_coordinates):
        raise ReproducibilityError("JSON result coordinate names must be strings")
    coordinates = {
        name: _decode_portable(raw_coordinates[name]) for name in raw_coordinates
    }
    missing = (
        None
        if "missing_mask" not in document or document.get("missing_mask") is None
        else _decode_portable(document.get("missing_mask"))
    )
    padding = (
        None
        if "padding_mask" not in document or document.get("padding_mask") is None
        else _decode_portable(document.get("padding_mask"))
    )
    return result_metadata_from_dict(
        metadata,
        values=_decode_portable(document.get("values")),
        coordinate_values=coordinates,
        missing_mask=missing,
        padding_mask=padding,
    )


__all__ = [
    "JSON_EXPORTER_ID",
    "JSONResultExporter",
    "load_result_json",
]
