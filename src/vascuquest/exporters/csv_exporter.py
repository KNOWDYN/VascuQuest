"""CSV export for scalar, one-dimensional, and two-dimensional tabular results.

CSV cannot carry the complete VascuQuest scientific result contract by itself.
This exporter therefore writes a companion ``.meta.json`` sidecar containing
scientific metadata and exact coordinate values. Unsupported structured or
higher-dimensional values fail explicitly rather than being flattened silently.
"""

from __future__ import annotations

from collections.abc import Mapping
import csv
from dataclasses import is_dataclass
import io
import json
import os
from pathlib import Path

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

from .json_exporter import (
    _atomic_write_text,
    _decode_portable,
    _destination_path,
    _encode_portable,
)


CSV_EXPORTER_ID = "vascuquest:csv"
_CSV_SIDECAR_FORMAT = "vascuquest-result-csv-sidecar"
_CSV_SIDECAR_VERSION = 1
_CELL_ENCODING = "vascuquest-json-scalar-v1"


def _sidecar_path(data_path: Path) -> Path:
    return data_path.with_suffix(data_path.suffix + ".meta.json")


def _cell_text(value: object) -> str:
    return json.dumps(
        _encode_portable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _cell_value(text: str) -> object:
    try:
        return _decode_portable(json.loads(text))
    except (json.JSONDecodeError, ReproducibilityError) as exc:
        raise ReproducibilityError("invalid VascuQuest CSV cell encoding") from exc


def _is_tabular_cell(value: object) -> bool:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if is_dataclass(value) and not isinstance(value, type):
        return False
    return not isinstance(value, (Mapping, tuple, list, np.ndarray))


def _tabular_layout(
    result: ScientificResult,
) -> tuple[np.ndarray, tuple[np.ndarray, ...]]:
    values = np.asarray(result.values, dtype=object)
    if values.ndim > 2:
        raise CapabilityError(
            "CSV export is limited to scalar, one-dimensional, or two-dimensional tabular values"
        )
    if len(result.dimensions) != values.ndim:
        raise CapabilityError(
            "CSV export requires result dimensions to match the tabular value rank exactly"
        )

    flat_values = values.reshape(-1) if values.ndim else np.asarray([values.item()], dtype=object)
    if any(not _is_tabular_cell(item) for item in flat_values):
        raise CapabilityError(
            "CSV export does not flatten structured records, mappings, or nested cell values"
        )

    if values.ndim == 0:
        if result.coordinates:
            raise CapabilityError("scalar CSV export does not accept auxiliary coordinates")
        return values, ()

    coordinate_by_name = {coordinate.name: coordinate for coordinate in result.coordinates}
    if set(coordinate_by_name) != set(result.dimensions):
        raise CapabilityError(
            "CSV export requires exactly one coordinate for each tabular dimension"
        )
    coordinates: list[np.ndarray] = []
    for axis, dimension in enumerate(result.dimensions):
        coordinate = np.asarray(coordinate_by_name[dimension].values, dtype=object)
        if coordinate.ndim != 1 or coordinate.shape[0] != values.shape[axis]:
            raise CapabilityError(
                f"coordinate {dimension!r} does not match its CSV table dimension"
            )
        if any(not _is_tabular_cell(item) for item in coordinate):
            raise CapabilityError("CSV coordinate values must be scalar portable cells")
        coordinates.append(coordinate)
    return values, tuple(coordinates)


def _mask_array(mask: object | None, shape: tuple[int, ...], name: str) -> np.ndarray | None:
    if mask is None:
        return None
    array = np.asarray(mask, dtype=bool)
    if array.shape != shape:
        raise CapabilityError(f"{name} shape does not match CSV-exported waveform values")
    return array


def _render_csv(
    result: ScientificResult,
    values: np.ndarray,
    coordinates: tuple[np.ndarray, ...],
) -> tuple[str, tuple[str, ...]]:
    coordinate_headers = tuple(f"coord:{name}" for name in result.dimensions)
    headers = list(coordinate_headers) + ["value"]

    missing: np.ndarray | None = None
    padding: np.ndarray | None = None
    if isinstance(result, Waveform):
        missing = _mask_array(result.missing_mask, values.shape, "missing_mask")
        padding = _mask_array(result.padding_mask, values.shape, "padding_mask")
        if missing is not None:
            headers.append("missing_mask")
        if padding is not None:
            headers.append("padding_mask")

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)

    if values.ndim == 0:
        row = [_cell_text(values.item())]
        if missing is not None:
            row.append(_cell_text(bool(missing.item())))
        if padding is not None:
            row.append(_cell_text(bool(padding.item())))
        writer.writerow(row)
        return output.getvalue(), tuple(headers)

    for index in np.ndindex(values.shape):
        row = [
            _cell_text(coordinates[axis][index[axis]])
            for axis in range(values.ndim)
        ]
        row.append(_cell_text(values[index]))
        if missing is not None:
            row.append(_cell_text(bool(missing[index])))
        if padding is not None:
            row.append(_cell_text(bool(padding[index])))
        writer.writerow(row)
    return output.getvalue(), tuple(headers)


def _sidecar_document(
    result: ScientificResult,
    *,
    data_path: Path,
    values: np.ndarray,
    coordinates: tuple[np.ndarray, ...],
    columns: tuple[str, ...],
) -> dict[str, object]:
    coordinate_values = {
        dimension: _encode_portable(coordinates[axis])
        for axis, dimension in enumerate(result.dimensions)
    }
    return {
        "format": _CSV_SIDECAR_FORMAT,
        "format_version": _CSV_SIDECAR_VERSION,
        "data_file": data_path.name,
        "cell_encoding": _CELL_ENCODING,
        "metadata": result_metadata_to_dict(result),
        "table": {
            "dimensions": list(result.dimensions),
            "shape": list(values.shape),
            "columns": list(columns),
            "coordinate_values": coordinate_values,
        },
    }


class CSVResultExporter:
    """Serialize naturally tabular scientific values plus a metadata sidecar."""

    @property
    def descriptor(self) -> ComponentDescriptor:
        return ComponentDescriptor(
            kind=ComponentKind.EXPORTER,
            name="VascuQuest CSV result exporter",
            qualified_id=CSV_EXPORTER_ID,
            implementation_version=__version__,
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="vascuquest",
            distribution_version=__version__,
            summary="CSV export for bounded tabular results with scientific metadata sidecars.",
        )

    @property
    def supported_result_kinds(self) -> tuple[str, ...]:
        return ("scientific_result", "waveform")

    @property
    def supported_output_formats(self) -> tuple[str, ...]:
        return ("csv",)

    @property
    def provenance_retention(self) -> str:
        return (
            "Retains the result provenance reference and complete ScientificResult metadata "
            "in a mandatory JSON sidecar; CSV values are never emitted without that sidecar."
        )

    def export(
        self,
        result: ScientificResult,
        destination: object,
        options: Mapping[str, object],
    ) -> dict[str, Path]:
        if not isinstance(result, ScientificResult):
            raise TypeError("result must be a ScientificResult")
        if not isinstance(options, Mapping):
            raise TypeError("options must be a mapping")
        if options:
            raise ValueError("the v1 CSV exporter defines no export options")

        data_path = _destination_path(destination)
        metadata_path = _sidecar_path(data_path)
        if metadata_path == data_path:
            raise CapabilityError("CSV metadata sidecar must be distinct from the data destination")

        values, coordinates = _tabular_layout(result)
        csv_text, columns = _render_csv(result, values, coordinates)
        sidecar = _sidecar_document(
            result,
            data_path=data_path,
            values=values,
            coordinates=coordinates,
            columns=columns,
        )
        metadata_text = json.dumps(
            sidecar,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"

        _atomic_write_text(data_path, csv_text)
        try:
            _atomic_write_text(metadata_path, metadata_text)
        except Exception:
            try:
                data_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return {"data_path": data_path, "metadata_path": metadata_path}


def _coerce_values(items: list[object], shape: tuple[int, ...]) -> object:
    if not shape:
        if len(items) != 1:
            raise ReproducibilityError("scalar CSV result must contain exactly one data row")
        return items[0]
    if len(items) != int(np.prod(shape, dtype=int)):
        raise ReproducibilityError("CSV row count does not match sidecar table shape")
    if all(isinstance(item, bool) for item in items):
        array = np.asarray(items, dtype=bool)
    elif all(isinstance(item, int) and not isinstance(item, bool) for item in items):
        array = np.asarray(items, dtype=np.int64)
    elif all(
        isinstance(item, (int, float)) and not isinstance(item, bool)
        for item in items
    ):
        array = np.asarray(items, dtype=float)
    elif all(isinstance(item, str) for item in items):
        array = np.asarray(items, dtype=object)
    else:
        array = np.asarray(items, dtype=object)
    array = array.reshape(shape)
    array.setflags(write=False)
    return array


def load_result_csv(source: str | os.PathLike[str]) -> ScientificResult:
    """Rebuild a result from a CSV export and its mandatory JSON sidecar."""

    data_path = _destination_path(source)
    metadata_path = _sidecar_path(data_path)
    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            sidecar = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproducibilityError(
            f"unable to read VascuQuest CSV metadata sidecar {metadata_path}"
        ) from exc
    if not isinstance(sidecar, Mapping):
        raise ReproducibilityError("CSV metadata sidecar must be a JSON object")
    if sidecar.get("format") != _CSV_SIDECAR_FORMAT:
        raise ReproducibilityError("unknown VascuQuest CSV sidecar format")
    if sidecar.get("format_version") != _CSV_SIDECAR_VERSION:
        raise ReproducibilityError("unsupported VascuQuest CSV sidecar format_version")
    if sidecar.get("data_file") != data_path.name:
        raise ReproducibilityError("CSV sidecar data_file does not match the selected CSV")
    if sidecar.get("cell_encoding") != _CELL_ENCODING:
        raise ReproducibilityError("unsupported VascuQuest CSV cell encoding")

    table = sidecar.get("table")
    if not isinstance(table, Mapping):
        raise ReproducibilityError("CSV sidecar table metadata must be a mapping")
    raw_dimensions = table.get("dimensions")
    raw_shape = table.get("shape")
    raw_columns = table.get("columns")
    raw_coordinates = table.get("coordinate_values")
    if not isinstance(raw_dimensions, list) or any(
        not isinstance(item, str) for item in raw_dimensions
    ):
        raise ReproducibilityError("CSV sidecar dimensions must be a string array")
    if not isinstance(raw_shape, list) or any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in raw_shape
    ):
        raise ReproducibilityError("CSV sidecar shape must be a non-negative integer array")
    if len(raw_shape) != len(raw_dimensions) or len(raw_shape) > 2:
        raise ReproducibilityError("CSV sidecar contains an invalid tabular rank")
    if not isinstance(raw_columns, list) or any(
        not isinstance(item, str) for item in raw_columns
    ):
        raise ReproducibilityError("CSV sidecar columns must be a string array")
    if not isinstance(raw_coordinates, Mapping):
        raise ReproducibilityError("CSV sidecar coordinate_values must be a mapping")

    dimensions = tuple(raw_dimensions)
    shape = tuple(raw_shape)
    expected_coordinate_names = set(dimensions)
    if set(raw_coordinates) != expected_coordinate_names:
        raise ReproducibilityError(
            "CSV sidecar coordinate values must exactly match table dimensions"
        )
    coordinate_values = {
        dimension: _decode_portable(raw_coordinates[dimension])
        for dimension in dimensions
    }

    try:
        with data_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != raw_columns:
                raise ReproducibilityError("CSV header does not match its metadata sidecar")
            rows = list(reader)
    except OSError as exc:
        raise ReproducibilityError(f"unable to read VascuQuest CSV result {data_path}") from exc

    values: list[object] = []
    missing_values: list[bool] | None = [] if "missing_mask" in raw_columns else None
    padding_values: list[bool] | None = [] if "padding_mask" in raw_columns else None
    expected_count = 1 if not shape else int(np.prod(shape, dtype=int))
    if len(rows) != expected_count:
        raise ReproducibilityError("CSV row count does not match its metadata sidecar")

    coordinate_arrays = {
        name: np.asarray(coordinate_values[name], dtype=object) for name in dimensions
    }
    for row_number, row in enumerate(rows):
        if set(row) != set(raw_columns):
            raise ReproducibilityError("CSV row columns do not match the header")
        if shape:
            index = np.unravel_index(row_number, shape)
            for axis, dimension in enumerate(dimensions):
                expected_text = _cell_text(coordinate_arrays[dimension][index[axis]])
                if row[f"coord:{dimension}"] != expected_text:
                    raise ReproducibilityError(
                        f"CSV coordinate column {dimension!r} disagrees with its sidecar"
                    )
        values.append(_cell_value(row["value"]))
        if missing_values is not None:
            decoded = _cell_value(row["missing_mask"])
            if not isinstance(decoded, bool):
                raise ReproducibilityError("CSV missing_mask cells must be boolean")
            missing_values.append(decoded)
        if padding_values is not None:
            decoded = _cell_value(row["padding_mask"])
            if not isinstance(decoded, bool):
                raise ReproducibilityError("CSV padding_mask cells must be boolean")
            padding_values.append(decoded)

    rebuilt_values = _coerce_values(values, shape)
    missing_mask: object | None = None
    padding_mask: object | None = None
    if missing_values is not None:
        missing_mask = np.asarray(missing_values, dtype=bool).reshape(shape)
        missing_mask.setflags(write=False)
    if padding_values is not None:
        padding_mask = np.asarray(padding_values, dtype=bool).reshape(shape)
        padding_mask.setflags(write=False)

    return result_metadata_from_dict(
        sidecar.get("metadata"),
        values=rebuilt_values,
        coordinate_values=coordinate_values,
        missing_mask=missing_mask,
        padding_mask=padding_mask,
    )


__all__ = [
    "CSV_EXPORTER_ID",
    "CSVResultExporter",
    "load_result_csv",
]
