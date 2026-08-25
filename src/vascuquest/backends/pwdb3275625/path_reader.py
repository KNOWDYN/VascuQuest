"""Bounded path-resolved waveform reads from canonical PWDB MATLAB v7.3 files.

Canonical path files remain authoritative. Large Zenodo path artifacts may be
opened through bounded HTTP byte-range access instead of being downloaded in
full. Exact per-subject source payloads are cached only in VascuQuest's derived
namespace and are keyed to the canonical manifest checksum.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any

import numpy as np

from vascuquest.errors import CapabilityError, IntegrityError, SchemaError, SelectionError

from .http_range import (
    CanonicalRemoteFile,
    HTTPRangeReader,
    verify_zenodo_file_identity,
)

N_SUBJECTS = 4374
CACHE_VERSION = 2
_MAX_WAVEFORM_SAMPLES = 1_000_000


@dataclass(frozen=True, slots=True)
class PathArtifactSpec:
    """Canonical scientific mapping for one PWDB path artifact."""

    artifact_id: str
    canonical_path_id: str
    source_path_id: str
    signals: tuple[str, ...]
    capability: str


PATH_ARTIFACT_SPECS = MappingProxyType(
    {
        "path_aorta_brain": PathArtifactSpec(
            "path_aorta_brain", "aorta_brain", "aorta_brain", ("P", "U", "A"),
            "path_resolved_waveforms:aorta_brain",
        ),
        "path_aorta_finger": PathArtifactSpec(
            "path_aorta_finger", "aorta_finger", "aorta_finger", ("P", "U", "A"),
            "path_resolved_waveforms:aorta_finger",
        ),
        "path_aorta_foot_p": PathArtifactSpec(
            "path_aorta_foot_p", "aorta_foot", "aorta_foot", ("P",),
            "path_resolved_waveforms:aorta_foot_p",
        ),
        "path_aorta_foot_u": PathArtifactSpec(
            "path_aorta_foot_u", "aorta_foot", "aorta_foot", ("U",),
            "path_resolved_waveforms:aorta_foot_u",
        ),
        "path_aorta_foot_a": PathArtifactSpec(
            "path_aorta_foot_a", "aorta_foot", "aorta_foot", ("A",),
            "path_resolved_waveforms:aorta_foot_a",
        ),
        "path_aorta_rsubclavian": PathArtifactSpec(
            "path_aorta_rsubclavian", "aorta_r_subclavian", "aorta_r_subclavian",
            ("P", "U", "A"), "path_resolved_waveforms:aorta_rsubclavian",
        ),
    }
)

PATH_CAPABILITIES = frozenset(spec.capability for spec in PATH_ARTIFACT_SPECS.values())
_PATH_SIGNAL_TO_ARTIFACT = MappingProxyType(
    {
        (spec.canonical_path_id, signal): artifact_id
        for artifact_id, spec in PATH_ARTIFACT_SPECS.items()
        for signal in spec.signals
    }
)


def artifact_id_for_path_signal(path_id: str, source_signal: str) -> str:
    """Return the canonical artifact containing one path/signal combination."""
    if not isinstance(path_id, str) or not path_id or path_id != path_id.strip():
        raise SelectionError("path_id must be a non-empty trimmed string")
    if source_signal not in {"P", "U", "A"}:
        raise CapabilityError(f"unsupported PWDB path signal {source_signal!r}")
    try:
        return _PATH_SIGNAL_TO_ARTIFACT[(path_id, source_signal)]
    except KeyError as exc:
        supported = sorted(
            f"{known_path}:{known_signal}"
            for known_path, known_signal in _PATH_SIGNAL_TO_ARTIFACT
        )
        raise CapabilityError(
            f"PWDB path/signal combination {path_id!r}/{source_signal!r} is not available; "
            f"supported combinations are {supported!r}"
        ) from exc


def _subject_number(subject_id: str) -> int:
    if not isinstance(subject_id, str) or not subject_id:
        raise SelectionError("subject_id must be a non-empty canonical subject identifier")
    try:
        value = int(subject_id, 10)
    except ValueError as exc:
        raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}") from exc
    if value < 1 or value > N_SUBJECTS or str(value) != subject_id:
        raise SelectionError(f"invalid PWDB subject identifier {subject_id!r}")
    return value


def _h5py_module():
    try:
        import h5py  # type: ignore[import-not-found]
    except ImportError as exc:
        raise CapabilityError(
            "path-resolved PWDB access requires optional HDF5 support; "
            "install it with `pip install 'vascuquest[path]'`"
        ) from exc
    return h5py


def _is_reference_dataset(h5py: Any, dataset: Any) -> bool:
    return h5py.check_dtype(ref=dataset.dtype) is not None


def _subject_ref(h5py: Any, dataset: Any, subject_number: int):
    if not _is_reference_dataset(h5py, dataset):
        raise SchemaError(f"{dataset.name} is not a MATLAB reference dataset")
    axes = [axis for axis, size in enumerate(dataset.shape) if size == N_SUBJECTS]
    if len(axes) != 1:
        raise SchemaError(f"{dataset.name} has ambiguous PWDB subject axis {dataset.shape}")
    index = [0] * dataset.ndim
    index[axes[0]] = subject_number - 1
    ref = dataset[tuple(index)]
    if not ref:
        raise SchemaError(f"{dataset.name} contains a null reference for subject {subject_number}")
    return ref


def _bounded_numeric(h5py: Any, dataset: Any) -> np.ndarray:
    if not isinstance(dataset, h5py.Dataset):
        raise SchemaError("MATLAB reference did not resolve to an HDF5 dataset")
    if _is_reference_dataset(h5py, dataset):
        raise SchemaError(f"{dataset.name} unexpectedly remains a reference dataset")
    if dataset.size < 1 or dataset.size > _MAX_WAVEFORM_SAMPLES:
        raise SchemaError(f"unsafe bounded read size for {dataset.name}: {dataset.size}")
    return np.asarray(dataset[...], dtype=np.float64).reshape(-1)


def _numeric_scalar(h5py: Any, handle: Any, node: Any, field_name: str) -> float:
    dataset = node
    if not isinstance(dataset, h5py.Dataset):
        raise SchemaError(f"{field_name} is not an HDF5 dataset")
    if _is_reference_dataset(h5py, dataset):
        refs = np.asarray(dataset[...]).reshape(-1)
        if len(refs) != 1 or not refs[0]:
            raise SchemaError(f"{field_name} does not contain exactly one numeric reference")
        dataset = handle[refs[0]]
    values = _bounded_numeric(h5py, dataset)
    if values.size != 1 or not math.isfinite(float(values[0])):
        raise SchemaError(f"{field_name} is not one finite numeric scalar")
    return float(values[0])


def _scalar_text(array: np.ndarray) -> str:
    value = array.item()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


@dataclass(frozen=True, slots=True)
class PathWaveformSeries:
    values: tuple[float, ...]
    time_seconds: tuple[float, ...]
    missing_mask: tuple[bool, ...]
    padding_mask: tuple[bool, ...]
    path_distance_m: float
    source_dataset: str
    distance_dataset: str
    source_signal: str
    sample_rate_hz: float
    source_access_mode: str


class _CacheMismatch(RuntimeError):
    pass


class PathWaveformReader:
    """Read one subject/path/signal/position through an exact derived cache."""

    __slots__ = ("_source", "_cache_root", "_spec", "_source_checksum", "_loaded_subjects")

    def __init__(
        self,
        source: Path | CanonicalRemoteFile,
        cache_root: Path,
        spec: PathArtifactSpec,
        *,
        source_checksum: str,
    ) -> None:
        if not isinstance(source, (Path, CanonicalRemoteFile)):
            raise TypeError("source must be a pathlib.Path or CanonicalRemoteFile")
        if not isinstance(cache_root, Path):
            raise TypeError("cache_root must be a pathlib.Path")
        if not isinstance(spec, PathArtifactSpec):
            raise TypeError("spec must be a PathArtifactSpec")
        if not isinstance(source_checksum, str) or not source_checksum:
            raise ValueError("source_checksum must be a non-empty string")
        if isinstance(source, CanonicalRemoteFile) and source.checksum_value.lower() != source_checksum.lower():
            raise IntegrityError("remote path source checksum does not match the canonical manifest")
        self._source = source
        self._cache_root = cache_root
        self._spec = spec
        self._source_checksum = source_checksum.lower()
        self._loaded_subjects: dict[str, dict[str, Any]] = {}

    @property
    def spec(self) -> PathArtifactSpec:
        return self._spec

    @property
    def source_access_mode(self) -> str:
        return "verified_local_artifact" if isinstance(self._source, Path) else "zenodo_manifest_pinned_http_range"

    def read(self, *, subject_id: str, source_signal: str, position_index: int) -> PathWaveformSeries:
        _subject_number(subject_id)
        if source_signal not in self._spec.signals:
            raise CapabilityError(
                f"artifact {self._spec.artifact_id!r} does not contain path signal {source_signal!r}"
            )
        if isinstance(position_index, bool) or not isinstance(position_index, int):
            raise TypeError("position_index must be an integer")
        if position_index < 0:
            raise SelectionError("path position_index must be non-negative")

        payload = self._payload(subject_id)
        distances = payload["distances"]
        if position_index >= int(distances.size):
            raise SelectionError(
                f"path position {position_index} is outside the source-supported range "
                f"0..{int(distances.size) - 1} for {self._spec.canonical_path_id!r}"
            )
        values = payload[f"{source_signal}_values"]
        offsets = payload[f"{source_signal}_offsets"]
        start, stop = int(offsets[position_index]), int(offsets[position_index + 1])
        selected = np.asarray(values[start:stop], dtype=np.float64)
        fs = float(payload["sample_rate_hz"])
        times = tuple(index / fs for index in range(int(selected.size)))
        python_values = tuple(float(value) for value in selected)
        missing = tuple(bool(math.isnan(value)) for value in python_values)
        padding = tuple(False for _ in python_values)
        source_paths = payload[f"{source_signal}_datasets"]
        return PathWaveformSeries(
            values=python_values,
            time_seconds=times,
            missing_mask=missing,
            padding_mask=padding,
            path_distance_m=float(distances[position_index]),
            source_dataset=str(source_paths[position_index]),
            distance_dataset=str(payload["distance_dataset"]),
            source_signal=source_signal,
            sample_rate_hz=fs,
            source_access_mode=str(payload["source_access_mode"]),
        )

    def _payload(self, subject_id: str) -> dict[str, Any]:
        cached = self._loaded_subjects.get(subject_id)
        if cached is not None:
            return cached
        cache_path = self._cache_path(subject_id)
        if cache_path.is_file():
            try:
                payload = self._load_cache(cache_path, subject_id)
            except (OSError, ValueError, KeyError, _CacheMismatch):
                try:
                    cache_path.unlink()
                except OSError:
                    pass
            else:
                self._loaded_subjects[subject_id] = payload
                return payload
        payload = self._build_payload(subject_id)
        self._write_cache(cache_path, subject_id, payload)
        self._loaded_subjects[subject_id] = payload
        return payload

    def _cache_path(self, subject_id: str) -> Path:
        subject_number = _subject_number(subject_id)
        return self._cache_root / "pwdb3275625" / "path-waveforms" / self._spec.artifact_id / f"subject-{subject_number:04d}.npz"

    def _build_payload(self, subject_id: str) -> dict[str, Any]:
        subject_number = _subject_number(subject_id)
        h5py = _h5py_module()
        source = self._source
        if isinstance(source, Path):
            if not source.is_file():
                raise IntegrityError(f"verified canonical path source is unavailable: {source}")
            if not h5py.is_hdf5(source):
                raise IntegrityError(f"canonical path artifact {source.name!r} is not HDF5-backed MATLAB v7.3")
            try:
                with h5py.File(source, "r") as handle:
                    payload = self._read_handle(h5py, handle, subject_number)
            except (OSError, RuntimeError) as exc:
                raise IntegrityError(f"unable to read verified canonical path artifact {source}") from exc
            payload["source_access_mode"] = "verified_local_artifact"
        else:
            metadata = verify_zenodo_file_identity(source)
            remote = HTTPRangeReader(source.url, size_bytes=metadata.size_bytes)
            try:
                with remote:
                    with h5py.File(remote, "r") as handle:
                        payload = self._read_handle(h5py, handle, subject_number)
            except (OSError, RuntimeError) as exc:
                raise IntegrityError(f"unable to read canonical path artifact sparsely from {source.url}") from exc
            payload["source_access_mode"] = "zenodo_manifest_pinned_http_range"
        fs = float(payload["sample_rate_hz"])
        if not math.isfinite(fs) or fs <= 0:
            raise SchemaError("canonical path sample rate is not positive and finite")
        return payload

    def _read_handle(self, h5py: Any, handle: Any, subject_number: int) -> dict[str, Any]:
        if "data" not in handle or "path_waves" not in handle["data"]:
            raise SchemaError("canonical path MAT lacks /data/path_waves")
        path_waves = handle["data"]["path_waves"]
        if self._spec.source_path_id not in path_waves:
            raise SchemaError(f"canonical path MAT lacks source path {self._spec.source_path_id!r}")
        group = path_waves[self._spec.source_path_id]
        if "dist" not in group:
            raise SchemaError("canonical path group lacks spatial distance data")
        distance_ref = _subject_ref(h5py, group["dist"], subject_number)
        distance_dataset = handle[distance_ref]
        distances = _bounded_numeric(h5py, distance_dataset)
        if not bool(np.isfinite(distances).all()):
            raise SchemaError("canonical path distances contain non-finite values")
        position_count = int(distances.size)
        if position_count < 1:
            raise SchemaError("canonical path has no stored positions")
        payload: dict[str, Any] = {
            "distances": distances.copy(),
            "distance_dataset": distance_dataset.name,
            "sample_rate_hz": _numeric_scalar(h5py, handle, path_waves["fs"], "/data/path_waves/fs"),
        }
        for signal in self._spec.signals:
            if signal not in group:
                raise SchemaError(f"canonical path group {self._spec.source_path_id!r} lacks signal {signal!r}")
            subject_ref = _subject_ref(h5py, group[signal], subject_number)
            subject_cell = handle[subject_ref]
            if not isinstance(subject_cell, h5py.Dataset) or not _is_reference_dataset(h5py, subject_cell):
                raise SchemaError(f"subject {subject_number} path signal {signal!r} is not a MATLAB cell-reference dataset")
            refs = np.asarray(subject_cell[...]).reshape(-1)
            if int(refs.size) != position_count:
                raise SchemaError(f"path signal {signal!r} has {int(refs.size)} positions but distance has {position_count}")
            arrays: list[np.ndarray] = []
            offsets = [0]
            dataset_paths: list[str] = []
            for ref in refs:
                if not ref:
                    raise SchemaError(f"path signal {signal!r} contains a null waveform reference")
                dataset = handle[ref]
                values = _bounded_numeric(h5py, dataset)
                arrays.append(values)
                offsets.append(offsets[-1] + int(values.size))
                dataset_paths.append(dataset.name)
            payload[f"{signal}_values"] = np.concatenate(arrays).astype(np.float64, copy=False)
            payload[f"{signal}_offsets"] = np.asarray(offsets, dtype=np.int64)
            payload[f"{signal}_datasets"] = np.asarray(dataset_paths, dtype=np.str_)
        return payload

    def _write_cache(self, cache_path: Path, subject_id: str, payload: dict[str, Any]) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        serializable: dict[str, Any] = {
            "cache_version": np.asarray(CACHE_VERSION, dtype=np.int64),
            "artifact_id": np.asarray(self._spec.artifact_id),
            "source_checksum": np.asarray(self._source_checksum),
            "canonical_path_id": np.asarray(self._spec.canonical_path_id),
            "source_path_id": np.asarray(self._spec.source_path_id),
            "subject_id": np.asarray(subject_id),
            "signals": np.asarray(self._spec.signals, dtype=np.str_),
            "distances": np.asarray(payload["distances"], dtype=np.float64),
            "distance_dataset": np.asarray(str(payload["distance_dataset"])),
            "sample_rate_hz": np.asarray(float(payload["sample_rate_hz"]), dtype=np.float64),
            "source_access_mode": np.asarray(str(payload["source_access_mode"])),
        }
        for signal in self._spec.signals:
            serializable[f"{signal}_values"] = np.asarray(payload[f"{signal}_values"], dtype=np.float64)
            serializable[f"{signal}_offsets"] = np.asarray(payload[f"{signal}_offsets"], dtype=np.int64)
            serializable[f"{signal}_datasets"] = np.asarray(payload[f"{signal}_datasets"], dtype=np.str_)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=cache_path.parent, prefix=f"{cache_path.name}.", suffix=".tmp", delete=False) as handle:
                temporary_path = Path(handle.name)
                np.savez(handle, **serializable)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, cache_path)
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _load_cache(self, cache_path: Path, subject_id: str) -> dict[str, Any]:
        with np.load(cache_path, allow_pickle=False) as data:
            if int(data["cache_version"].item()) != CACHE_VERSION:
                raise _CacheMismatch("cache version changed")
            if _scalar_text(data["artifact_id"]) != self._spec.artifact_id:
                raise _CacheMismatch("artifact identity changed")
            if _scalar_text(data["source_checksum"]).lower() != self._source_checksum:
                raise _CacheMismatch("canonical source checksum changed")
            if _scalar_text(data["canonical_path_id"]) != self._spec.canonical_path_id:
                raise _CacheMismatch("canonical path identity changed")
            if _scalar_text(data["source_path_id"]) != self._spec.source_path_id:
                raise _CacheMismatch("source path identity changed")
            if _scalar_text(data["subject_id"]) != subject_id:
                raise _CacheMismatch("subject identity changed")
            signals = tuple(str(value) for value in np.asarray(data["signals"]).tolist())
            if signals != self._spec.signals:
                raise _CacheMismatch("cached signal set changed")
            source_access_mode = _scalar_text(data["source_access_mode"])
            if source_access_mode not in {"verified_local_artifact", "zenodo_manifest_pinned_http_range"}:
                raise _CacheMismatch("cached source-access mode is invalid")
            distances = np.asarray(data["distances"], dtype=np.float64).reshape(-1).copy()
            if distances.size < 1 or not bool(np.isfinite(distances).all()):
                raise _CacheMismatch("cached path distances are invalid")
            fs = float(data["sample_rate_hz"].item())
            if not math.isfinite(fs) or fs <= 0:
                raise _CacheMismatch("cached sample rate is invalid")
            payload: dict[str, Any] = {
                "distances": distances,
                "distance_dataset": _scalar_text(data["distance_dataset"]),
                "sample_rate_hz": fs,
                "source_access_mode": source_access_mode,
            }
            position_count = int(distances.size)
            for signal in self._spec.signals:
                values = np.asarray(data[f"{signal}_values"], dtype=np.float64).reshape(-1).copy()
                offsets = np.asarray(data[f"{signal}_offsets"], dtype=np.int64).reshape(-1).copy()
                datasets = np.asarray(data[f"{signal}_datasets"], dtype=np.str_).reshape(-1).copy()
                if offsets.size != position_count + 1:
                    raise _CacheMismatch("cached waveform offsets do not match path positions")
                if datasets.size != position_count:
                    raise _CacheMismatch("cached waveform dataset identities do not match path positions")
                if int(offsets[0]) != 0 or int(offsets[-1]) != int(values.size):
                    raise _CacheMismatch("cached waveform offsets do not span the value array")
                if bool(np.any(np.diff(offsets) < 0)):
                    raise _CacheMismatch("cached waveform offsets are not monotone")
                payload[f"{signal}_values"] = values
                payload[f"{signal}_offsets"] = offsets
                payload[f"{signal}_datasets"] = datasets
        return payload


__all__ = [
    "CACHE_VERSION", "PATH_ARTIFACT_SPECS", "PATH_CAPABILITIES", "PathArtifactSpec",
    "PathWaveformReader", "PathWaveformSeries", "artifact_id_for_path_signal",
]
