"""Hybrid path reader with position-lazy canonical Zenodo access.

Verified local PWDB path artifacts retain the existing eager per-subject cache.
Remote canonical Zenodo artifacts use a small derived subject index plus exact
per-position waveform caches so one requested path position never causes all
positions/signals for the subject to be materialized.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from vascuquest.errors import CapabilityError, IntegrityError, SchemaError, SelectionError

from .http_range import CanonicalRemoteFile, HTTPRangeReader, RemoteFileMetadata, verify_zenodo_file_identity
from . import path_reader as eager

_REMOTE_BLOCK_SIZE = 64 * 1024
_REMOTE_MAX_BLOCKS = 256
_REMOTE_INDEX_VERSION = 1
_REMOTE_WAVE_VERSION = 1


@dataclass(frozen=True, slots=True)
class RemoteTransportStats:
    bytes_transferred: int
    range_requests: int
    remote_opens: int


class HybridPathWaveformReader:
    """Use the proven local reader locally and lazy exact reads remotely."""

    __slots__ = (
        "_source",
        "_cache_root",
        "_spec",
        "_source_checksum",
        "_local",
        "_metadata",
        "_loaded_indexes",
        "_bytes_transferred",
        "_range_requests",
        "_remote_opens",
    )

    def __init__(
        self,
        source: Path | CanonicalRemoteFile,
        cache_root: Path,
        spec: eager.PathArtifactSpec,
        *,
        source_checksum: str,
    ) -> None:
        if not isinstance(source, (Path, CanonicalRemoteFile)):
            raise TypeError("source must be a pathlib.Path or CanonicalRemoteFile")
        if not isinstance(cache_root, Path):
            raise TypeError("cache_root must be a pathlib.Path")
        if not isinstance(spec, eager.PathArtifactSpec):
            raise TypeError("spec must be a PathArtifactSpec")
        if not isinstance(source_checksum, str) or not source_checksum:
            raise ValueError("source_checksum must be a non-empty string")
        if isinstance(source, CanonicalRemoteFile) and source.checksum_value.lower() != source_checksum.lower():
            raise IntegrityError("remote path source checksum does not match the canonical manifest")
        self._source = source
        self._cache_root = cache_root
        self._spec = spec
        self._source_checksum = source_checksum.lower()
        self._local = (
            eager.PathWaveformReader(source, cache_root, spec, source_checksum=source_checksum)
            if isinstance(source, Path)
            else None
        )
        self._metadata: RemoteFileMetadata | None = None
        self._loaded_indexes: dict[str, dict[str, Any]] = {}
        self._bytes_transferred = 0
        self._range_requests = 0
        self._remote_opens = 0

    @property
    def spec(self) -> eager.PathArtifactSpec:
        return self._spec

    @property
    def source_access_mode(self) -> str:
        return "verified_local_artifact" if self._local is not None else "zenodo_manifest_pinned_http_range"

    @property
    def transport_stats(self) -> RemoteTransportStats:
        return RemoteTransportStats(
            bytes_transferred=self._bytes_transferred,
            range_requests=self._range_requests,
            remote_opens=self._remote_opens,
        )

    def read(self, *, subject_id: str, source_signal: str, position_index: int) -> eager.PathWaveformSeries:
        if self._local is not None:
            return self._local.read(
                subject_id=subject_id,
                source_signal=source_signal,
                position_index=position_index,
            )
        eager._subject_number(subject_id)
        if source_signal not in self._spec.signals:
            raise CapabilityError(
                f"artifact {self._spec.artifact_id!r} does not contain path signal {source_signal!r}"
            )
        if isinstance(position_index, bool) or not isinstance(position_index, int):
            raise TypeError("position_index must be an integer")
        if position_index < 0:
            raise SelectionError("path position_index must be non-negative")

        index = self._subject_index(subject_id)
        distances = np.asarray(index["distances"], dtype=np.float64)
        if position_index >= int(distances.size):
            raise SelectionError(
                f"path position {position_index} is outside the source-supported range "
                f"0..{int(distances.size) - 1} for {self._spec.canonical_path_id!r}"
            )

        wave = self._waveform_payload(subject_id, source_signal, position_index, index)
        values = np.asarray(wave["values"], dtype=np.float64)
        fs = float(index["sample_rate_hz"])
        python_values = tuple(float(value) for value in values)
        times = tuple(i / fs for i in range(int(values.size)))
        missing = tuple(bool(math.isnan(value)) for value in python_values)
        padding = tuple(False for _ in python_values)
        return eager.PathWaveformSeries(
            values=python_values,
            time_seconds=times,
            missing_mask=missing,
            padding_mask=padding,
            path_distance_m=float(distances[position_index]),
            source_dataset=str(wave["source_dataset"]),
            distance_dataset=str(index["distance_dataset"]),
            source_signal=source_signal,
            sample_rate_hz=fs,
            source_access_mode="zenodo_manifest_pinned_http_range",
        )

    def _remote_metadata(self) -> RemoteFileMetadata:
        if self._metadata is None:
            assert isinstance(self._source, CanonicalRemoteFile)
            self._metadata = verify_zenodo_file_identity(self._source)
        return self._metadata

    def _open_remote(self):
        assert isinstance(self._source, CanonicalRemoteFile)
        metadata = self._remote_metadata()
        remote = HTTPRangeReader(
            self._source.url,
            size_bytes=metadata.size_bytes,
            block_size=_REMOTE_BLOCK_SIZE,
            max_blocks=_REMOTE_MAX_BLOCKS,
        )
        self._remote_opens += 1
        return remote

    def _collect_remote_stats(self, remote: HTTPRangeReader) -> None:
        self._bytes_transferred += remote.bytes_transferred
        self._range_requests += remote.range_requests

    def _subject_dir(self, subject_id: str) -> Path:
        number = eager._subject_number(subject_id)
        return (
            self._cache_root
            / "pwdb3275625"
            / "path-waveforms"
            / self._spec.artifact_id
            / f"subject-{number:04d}"
        )

    def _index_path(self, subject_id: str) -> Path:
        return self._subject_dir(subject_id) / "index.npz"

    def _wave_path(self, subject_id: str, signal: str, position: int) -> Path:
        return self._subject_dir(subject_id) / f"{signal}-position-{position:05d}.npz"

    def _subject_index(self, subject_id: str) -> dict[str, Any]:
        cached = self._loaded_indexes.get(subject_id)
        if cached is not None:
            return cached
        path = self._index_path(subject_id)
        if path.is_file():
            try:
                payload = self._load_index(path, subject_id)
            except (OSError, ValueError, KeyError, RuntimeError):
                try:
                    path.unlink()
                except OSError:
                    pass
            else:
                self._loaded_indexes[subject_id] = payload
                return payload
        payload = self._build_index(subject_id)
        self._write_index(path, subject_id, payload)
        self._loaded_indexes[subject_id] = payload
        return payload

    def _build_index(self, subject_id: str) -> dict[str, Any]:
        subject_number = eager._subject_number(subject_id)
        h5py = eager._h5py_module()
        remote = self._open_remote()
        try:
            with remote:
                with h5py.File(remote, "r") as handle:
                    if "data" not in handle or "path_waves" not in handle["data"]:
                        raise SchemaError("canonical path MAT lacks /data/path_waves")
                    path_waves = handle["data"]["path_waves"]
                    if self._spec.source_path_id not in path_waves:
                        raise SchemaError(
                            f"canonical path MAT lacks source path {self._spec.source_path_id!r}"
                        )
                    group = path_waves[self._spec.source_path_id]
                    if "dist" not in group:
                        raise SchemaError("canonical path group lacks spatial distance data")
                    distance_ref = eager._subject_ref(h5py, group["dist"], subject_number)
                    distance_dataset = handle[distance_ref]
                    distances = eager._bounded_numeric(h5py, distance_dataset)
                    if distances.size < 1 or not bool(np.isfinite(distances).all()):
                        raise SchemaError("canonical path distances are empty or non-finite")
                    fs = eager._numeric_scalar(
                        h5py, handle, path_waves["fs"], "/data/path_waves/fs"
                    )
                    if not math.isfinite(fs) or fs <= 0:
                        raise SchemaError("canonical path sample rate is not positive and finite")
                    payload: dict[str, Any] = {
                        "distances": distances.copy(),
                        "distance_dataset": distance_dataset.name,
                        "sample_rate_hz": fs,
                    }
                    position_count = int(distances.size)
                    for signal in self._spec.signals:
                        if signal not in group:
                            raise SchemaError(
                                f"canonical path group {self._spec.source_path_id!r} lacks signal {signal!r}"
                            )
                        subject_ref = eager._subject_ref(h5py, group[signal], subject_number)
                        subject_cell = handle[subject_ref]
                        if not isinstance(subject_cell, h5py.Dataset) or not eager._is_reference_dataset(h5py, subject_cell):
                            raise SchemaError(
                                f"subject {subject_number} path signal {signal!r} is not a MATLAB cell-reference dataset"
                            )
                        if int(subject_cell.size) != position_count:
                            raise SchemaError(
                                f"path signal {signal!r} has {int(subject_cell.size)} positions but distance has {position_count}"
                            )
                        payload[f"{signal}_subject_cell"] = subject_cell.name
        except (OSError, RuntimeError) as exc:
            raise IntegrityError(
                f"unable to build sparse path index from canonical artifact {self._source.url}"
            ) from exc
        finally:
            self._collect_remote_stats(remote)
        return payload

    def _position_ref(self, dataset: Any, position: int, position_count: int):
        h5py = eager._h5py_module()
        if not isinstance(dataset, h5py.Dataset) or not eager._is_reference_dataset(h5py, dataset):
            raise SchemaError("cached subject-cell path no longer resolves to a reference dataset")
        axes = [axis for axis, size in enumerate(dataset.shape) if size == position_count]
        if len(axes) != 1:
            raise SchemaError(
                f"{dataset.name} has ambiguous path-position axis {dataset.shape}"
            )
        index = [0] * dataset.ndim
        index[axes[0]] = position
        ref = dataset[tuple(index)]
        if not ref:
            raise SchemaError(
                f"{dataset.name} contains a null waveform reference at position {position}"
            )
        return ref

    def _waveform_payload(
        self,
        subject_id: str,
        signal: str,
        position: int,
        index: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._wave_path(subject_id, signal, position)
        if path.is_file():
            try:
                return self._load_wave(path, subject_id, signal, position)
            except (OSError, ValueError, KeyError, RuntimeError):
                try:
                    path.unlink()
                except OSError:
                    pass

        h5py = eager._h5py_module()
        remote = self._open_remote()
        try:
            with remote:
                with h5py.File(remote, "r") as handle:
                    subject_cell_path = str(index[f"{signal}_subject_cell"])
                    if subject_cell_path not in handle:
                        raise SchemaError(
                            f"cached subject-cell dataset {subject_cell_path!r} is absent"
                        )
                    subject_cell = handle[subject_cell_path]
                    position_count = int(np.asarray(index["distances"]).size)
                    ref = self._position_ref(subject_cell, position, position_count)
                    dataset = handle[ref]
                    values = eager._bounded_numeric(h5py, dataset)
                    payload = {
                        "values": values.copy(),
                        "source_dataset": dataset.name,
                    }
        except (OSError, RuntimeError) as exc:
            raise IntegrityError(
                f"unable to read sparse canonical waveform from {self._source.url}"
            ) from exc
        finally:
            self._collect_remote_stats(remote)
        self._write_wave(path, subject_id, signal, position, payload)
        return payload

    def _atomic_npz(self, path: Path, fields: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                np.savez(handle, **fields)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _write_index(self, path: Path, subject_id: str, payload: dict[str, Any]) -> None:
        fields: dict[str, Any] = {
            "cache_version": np.asarray(_REMOTE_INDEX_VERSION, dtype=np.int64),
            "artifact_id": np.asarray(self._spec.artifact_id),
            "source_checksum": np.asarray(self._source_checksum),
            "canonical_path_id": np.asarray(self._spec.canonical_path_id),
            "subject_id": np.asarray(subject_id),
            "distances": np.asarray(payload["distances"], dtype=np.float64),
            "distance_dataset": np.asarray(str(payload["distance_dataset"])),
            "sample_rate_hz": np.asarray(float(payload["sample_rate_hz"]), dtype=np.float64),
        }
        for signal in self._spec.signals:
            fields[f"{signal}_subject_cell"] = np.asarray(str(payload[f"{signal}_subject_cell"]))
        self._atomic_npz(path, fields)

    def _load_index(self, path: Path, subject_id: str) -> dict[str, Any]:
        with np.load(path, allow_pickle=False) as data:
            if int(data["cache_version"].item()) != _REMOTE_INDEX_VERSION:
                raise RuntimeError("remote index version changed")
            if eager._scalar_text(data["artifact_id"]) != self._spec.artifact_id:
                raise RuntimeError("remote index artifact changed")
            if eager._scalar_text(data["source_checksum"]).lower() != self._source_checksum:
                raise RuntimeError("remote index canonical checksum changed")
            if eager._scalar_text(data["canonical_path_id"]) != self._spec.canonical_path_id:
                raise RuntimeError("remote index path changed")
            if eager._scalar_text(data["subject_id"]) != subject_id:
                raise RuntimeError("remote index subject changed")
            payload: dict[str, Any] = {
                "distances": np.asarray(data["distances"], dtype=np.float64).copy(),
                "distance_dataset": eager._scalar_text(data["distance_dataset"]),
                "sample_rate_hz": float(data["sample_rate_hz"].item()),
            }
            for signal in self._spec.signals:
                payload[f"{signal}_subject_cell"] = eager._scalar_text(data[f"{signal}_subject_cell"])
        if payload["distances"].size < 1 or not bool(np.isfinite(payload["distances"]).all()):
            raise RuntimeError("remote index distances invalid")
        if not math.isfinite(payload["sample_rate_hz"]) or payload["sample_rate_hz"] <= 0:
            raise RuntimeError("remote index sample rate invalid")
        return payload

    def _write_wave(
        self,
        path: Path,
        subject_id: str,
        signal: str,
        position: int,
        payload: dict[str, Any],
    ) -> None:
        self._atomic_npz(
            path,
            {
                "cache_version": np.asarray(_REMOTE_WAVE_VERSION, dtype=np.int64),
                "artifact_id": np.asarray(self._spec.artifact_id),
                "source_checksum": np.asarray(self._source_checksum),
                "subject_id": np.asarray(subject_id),
                "signal": np.asarray(signal),
                "position": np.asarray(position, dtype=np.int64),
                "values": np.asarray(payload["values"], dtype=np.float64),
                "source_dataset": np.asarray(str(payload["source_dataset"])),
            },
        )

    def _load_wave(
        self,
        path: Path,
        subject_id: str,
        signal: str,
        position: int,
    ) -> dict[str, Any]:
        with np.load(path, allow_pickle=False) as data:
            if int(data["cache_version"].item()) != _REMOTE_WAVE_VERSION:
                raise RuntimeError("remote waveform cache version changed")
            if eager._scalar_text(data["artifact_id"]) != self._spec.artifact_id:
                raise RuntimeError("remote waveform artifact changed")
            if eager._scalar_text(data["source_checksum"]).lower() != self._source_checksum:
                raise RuntimeError("remote waveform canonical checksum changed")
            if eager._scalar_text(data["subject_id"]) != subject_id:
                raise RuntimeError("remote waveform subject changed")
            if eager._scalar_text(data["signal"]) != signal:
                raise RuntimeError("remote waveform signal changed")
            if int(data["position"].item()) != position:
                raise RuntimeError("remote waveform position changed")
            values = np.asarray(data["values"], dtype=np.float64).copy()
            source_dataset = eager._scalar_text(data["source_dataset"])
        if values.size < 1 or values.size > eager._MAX_WAVEFORM_SAMPLES:
            raise RuntimeError("remote waveform cache size invalid")
        return {"values": values, "source_dataset": source_dataset}


__all__ = ["HybridPathWaveformReader", "RemoteTransportStats"]
