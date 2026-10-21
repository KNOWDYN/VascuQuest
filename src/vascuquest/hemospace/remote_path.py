"""Subject-scoped remote access to canonical PWDB path-resolved HDF5 artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen

import numpy as np

from vascuquest.errors import IntegrityError, SelectionError
from vascuquest.schema.loader import load_manifest
from .path import (
    PathWaveField,
    _cells,
    _char,
    _deref_subject,
    _numeric,
    _readonly_wave,
    _subject_index,
)
from .remote_hdf5 import open_remote_hdf5


def _read_scalar_numeric(handle: Any, obj: Any) -> float:
    raw = np.asarray(obj[()])
    try:
        import h5py  # type: ignore
        is_ref = h5py.check_dtype(ref=raw.dtype) is not None
    except ImportError:
        is_ref = False
    if is_ref:
        refs = np.asarray(raw).reshape(-1, order="F")
        refs = [ref for ref in refs if ref]
        if len(refs) != 1:
            raise IntegrityError("sampling-frequency reference must contain exactly one value")
        values = _numeric(handle[refs[0]])
    else:
        values = np.asarray(raw, dtype=float).reshape(-1)
    if values.size < 1 or not np.isfinite(values[0]) or values[0] <= 0:
        raise IntegrityError("invalid path sampling frequency")
    return float(values[0])


def _sampling_frequency_hz(handle: Any, path_name: str) -> float:
    candidates: list[Any] = []
    try:
        path_waves = handle["data"]["path_waves"]
        if "fs" in path_waves:
            candidates.append(path_waves["fs"])
        if path_name in path_waves and "fs" in path_waves[path_name]:
            candidates.append(path_waves[path_name]["fs"])
    except Exception:
        pass
    try:
        data = handle["data"]
        if "fs" in data:
            candidates.append(data["fs"])
    except Exception:
        pass
    for candidate in candidates:
        try:
            return _read_scalar_numeric(handle, candidate)
        except Exception:
            continue
    raise IntegrityError(
        "canonical path artifact does not expose sampling frequency at a supported exporter location"
    )


@dataclass(frozen=True, slots=True)
class RemoteArtifactIdentity:
    artifact_id: str
    filename: str
    source_url: str
    size_bytes: int
    md5: str
    verification: str = "ZENODO_RECORD_METADATA"


@dataclass(frozen=True, slots=True)
class AlignedPathSegment:
    """One native segment proven to have exact common P/U/A sample support."""

    field: PathWaveField
    sampling_frequency_hz: float

    @property
    def time_s(self) -> np.ndarray:
        signal = next(iter(self.field.signals))
        n = self.field.matrix(signal).shape[1]
        return np.arange(n, dtype=float) / self.sampling_frequency_hz


@dataclass(frozen=True, slots=True)
class RaggedPathWaveField:
    """Lossless path waves whose point waveforms may have unequal lengths."""

    subject_id: str
    path_name: str
    source_artifacts: tuple[str, ...]
    sampling_frequency_hz: float
    distance_m: tuple[float, ...]
    artery: tuple[str, ...]
    segment_no: tuple[int, ...]
    artery_distance_m: tuple[float, ...]
    onset_time_s: tuple[float, ...]
    signals: Mapping[str, tuple[np.ndarray, ...]]

    def point_lengths(self, signal: str) -> tuple[int, ...]:
        try:
            waves = self.signals[signal]
        except KeyError as exc:
            raise SelectionError(f"ragged field does not contain signal {signal!r}") from exc
        return tuple(int(np.asarray(wave).size) for wave in waves)

    def segment_indices(self, segment_no: int) -> tuple[int, ...]:
        return tuple(i for i, value in enumerate(self.segment_no) if int(value) == int(segment_no))

    def aligned_segment(
        self,
        segment_no: int,
        *,
        signals: tuple[str, ...] = ("P", "U", "A"),
    ) -> AlignedPathSegment:
        indices = self.segment_indices(segment_no)
        if not indices:
            raise SelectionError(f"segment {segment_no} is absent from path {self.path_name!r}")
        lengths: set[int] = set()
        selected: dict[str, tuple[np.ndarray, ...]] = {}
        for signal in signals:
            if signal not in self.signals:
                raise SelectionError(f"signal {signal!r} is absent from ragged path field")
            waves = tuple(_readonly_wave(self.signals[signal][i]) for i in indices)
            selected[signal] = waves
            lengths.update(int(wave.size) for wave in waves)
        if len(lengths) != 1:
            detail = {name: tuple(int(w.size) for w in waves) for name, waves in selected.items()}
            raise IntegrityError(
                f"segment {segment_no} lacks exact common time support across requested signals: {detail!r}"
            )
        field = PathWaveField(
            subject_id=self.subject_id,
            path_name=self.path_name,
            source_artifacts=self.source_artifacts,
            distance_m=tuple(self.distance_m[i] for i in indices),
            artery=tuple(self.artery[i] for i in indices),
            segment_no=tuple(self.segment_no[i] for i in indices),
            artery_distance_m=tuple(self.artery_distance_m[i] for i in indices),
            onset_time_s=tuple(self.onset_time_s[i] for i in indices),
            signals=selected,
        )
        for signal in signals:
            field.matrix(signal)
        return AlignedPathSegment(field=field, sampling_frequency_hz=self.sampling_frequency_hz)

    def metadata(self) -> dict[str, object]:
        return {
            "kind": "vascuquest.hemospace.ragged_path_waves",
            "schema_version": "hemospace-remote-1",
            "subject_id": self.subject_id,
            "path_name": self.path_name,
            "source_artifacts": list(self.source_artifacts),
            "sampling_frequency_hz": self.sampling_frequency_hz,
            "path_points": len(self.distance_m),
            "signal_lengths": {
                name: list(self.point_lengths(name)) for name in sorted(self.signals)
            },
            "evidence": "SOURCE",
        }


def _metadata_for_subject(handle: Any, group: Any, subject_id: str) -> dict[str, object]:
    index = _subject_index(subject_id)
    distance = _numeric(_deref_subject(handle, group, "dist", index))
    artery_distance = _numeric(_deref_subject(handle, group, "artery_dist", index))
    onset = _numeric(_deref_subject(handle, group, "onset_time", index))
    arteries = tuple(
        _char(item) for item in _cells(handle, _deref_subject(handle, group, "artery", index))
    )
    segments = tuple(
        int(round(float(_numeric(item)[0])))
        for item in _cells(handle, _deref_subject(handle, group, "segment_no", index))
    )
    lengths = {len(distance), len(artery_distance), len(onset), len(arteries), len(segments)}
    if len(lengths) != 1:
        raise IntegrityError("path metadata arrays do not have identical point counts")
    return {
        "distance_m": tuple(map(float, distance)),
        "artery_distance_m": tuple(map(float, artery_distance)),
        "onset_time_s": tuple(map(float, onset)),
        "artery": arteries,
        "segment_no": segments,
    }


def _subject_from_open_artifact(
    handle: Any,
    path_name: str,
    subject_id: str,
    *,
    signals: tuple[str, ...],
    source_artifact: str,
) -> RaggedPathWaveField:
    try:
        group = handle["data"]["path_waves"][path_name]
    except Exception as exc:
        raise IntegrityError(f"remote artifact lacks data/path_waves/{path_name}") from exc
    metadata = _metadata_for_subject(handle, group, subject_id)
    index = _subject_index(subject_id)
    collected: dict[str, tuple[np.ndarray, ...]] = {}
    for signal in signals:
        waves = tuple(
            _readonly_wave(_numeric(item))
            for item in _cells(handle, _deref_subject(handle, group, signal, index))
        )
        if len(waves) != len(metadata["distance_m"]):
            raise IntegrityError(f"path signal {signal!r} point count does not match metadata")
        collected[signal] = waves
    return RaggedPathWaveField(
        subject_id=subject_id,
        path_name=path_name,
        source_artifacts=(source_artifact,),
        sampling_frequency_hz=_sampling_frequency_hz(handle, path_name),
        distance_m=metadata["distance_m"],
        artery=metadata["artery"],
        segment_no=metadata["segment_no"],
        artery_distance_m=metadata["artery_distance_m"],
        onset_time_s=metadata["onset_time_s"],
        signals=collected,
    )


def merge_ragged_path_fields(fields: Iterable[RaggedPathWaveField]) -> RaggedPathWaveField:
    items = tuple(fields)
    if not items:
        raise ValueError("at least one ragged field is required")
    first = items[0]
    signals: dict[str, tuple[np.ndarray, ...]] = {}
    artifacts: list[str] = []
    for item in items:
        if (
            item.subject_id != first.subject_id
            or item.path_name != first.path_name
            or item.distance_m != first.distance_m
            or item.artery != first.artery
            or item.segment_no != first.segment_no
            or item.artery_distance_m != first.artery_distance_m
            or item.onset_time_s != first.onset_time_s
            or not np.isclose(item.sampling_frequency_hz, first.sampling_frequency_hz, rtol=0, atol=1e-12)
        ):
            raise IntegrityError("split path artifacts do not preserve identical subject/path metadata")
        artifacts.extend(item.source_artifacts)
        overlap = set(signals).intersection(item.signals)
        if overlap:
            raise IntegrityError(f"duplicate signals while merging ragged path fields: {sorted(overlap)!r}")
        signals.update(item.signals)
    return RaggedPathWaveField(
        subject_id=first.subject_id,
        path_name=first.path_name,
        source_artifacts=tuple(artifacts),
        sampling_frequency_hz=first.sampling_frequency_hz,
        distance_m=first.distance_m,
        artery=first.artery,
        segment_no=first.segment_no,
        artery_distance_m=first.artery_distance_m,
        onset_time_s=first.onset_time_s,
        signals=signals,
    )


class PWDBRemotePathClient:
    """Canonical PWDB remote path client with manifest and Zenodo identity checks."""

    def __init__(
        self,
        *,
        block_size: int = 1 << 20,
        max_cache_blocks: int = 64,
        timeout_s: float = 60.0,
        opener: Any | None = None,
    ) -> None:
        self.manifest = load_manifest()
        self.block_size = int(block_size)
        self.max_cache_blocks = int(max_cache_blocks)
        self.timeout_s = float(timeout_s)
        self.opener = opener or urlopen
        self._identities: dict[str, RemoteArtifactIdentity] | None = None

    def _json_get(self, url: str) -> dict[str, Any]:
        request = Request(url, headers={"Accept": "application/json", "Accept-Encoding": "identity"})
        try:
            response = self.opener(request, timeout=self.timeout_s)
        except TypeError:
            response = self.opener(request)
        with response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise IntegrityError("Zenodo record API did not return a JSON object")
        return payload

    def verify_remote_identity(self, *, refresh: bool = False) -> Mapping[str, RemoteArtifactIdentity]:
        if self._identities is not None and not refresh:
            return dict(self._identities)
        payload = self._json_get(
            f"https://zenodo.org/api/records/{self.manifest.canonical_record_id}"
        )
        files = payload.get("files")
        if not isinstance(files, list):
            raise IntegrityError("Zenodo record metadata lacks files list")
        by_name: dict[str, dict[str, Any]] = {}
        for item in files:
            if isinstance(item, dict) and isinstance(item.get("key"), str):
                by_name[item["key"]] = item
        identities: dict[str, RemoteArtifactIdentity] = {}
        for artifact in self.manifest.artifacts:
            if not artifact.artifact_id.startswith("path_"):
                continue
            item = by_name.get(artifact.filename)
            if item is None:
                raise IntegrityError(f"Zenodo record lacks canonical artifact {artifact.filename!r}")
            checksum = str(item.get("checksum", ""))
            md5 = checksum.split(":", 1)[1] if checksum.startswith("md5:") else checksum
            if md5 != artifact.checksum_value:
                raise IntegrityError(
                    f"Zenodo checksum mismatch for {artifact.filename}: {md5!r} != {artifact.checksum_value!r}"
                )
            size = int(item.get("size") or 0)
            if size <= 0:
                raise IntegrityError(f"Zenodo metadata lacks positive size for {artifact.filename}")
            links = item.get("links") if isinstance(item.get("links"), dict) else {}
            url = str(links.get("self") or links.get("content") or artifact.source_locator)
            identities[artifact.artifact_id] = RemoteArtifactIdentity(
                artifact_id=artifact.artifact_id,
                filename=artifact.filename,
                source_url=url,
                size_bytes=size,
                md5=md5,
            )
        self._identities = identities
        return dict(identities)

    def artifact_identity(self, artifact_id: str) -> RemoteArtifactIdentity:
        identities = self.verify_remote_identity()
        try:
            return identities[artifact_id]
        except KeyError as exc:
            raise SelectionError(f"remote path artifact {artifact_id!r} is not available") from exc

    def iter_artifact_subjects(
        self,
        artifact_id: str,
        path_name: str,
        subject_ids: Iterable[str],
        *,
        signals: tuple[str, ...],
    ):
        identity = self.artifact_identity(artifact_id)
        handle, reader = open_remote_hdf5(
            identity.source_url,
            block_size=self.block_size,
            max_cache_blocks=self.max_cache_blocks,
            timeout_s=self.timeout_s,
            opener=self.opener,
        )
        try:
            if int(reader.size) != int(identity.size_bytes):
                raise IntegrityError(
                    f"remote size mismatch for {identity.filename}: {reader.size} != {identity.size_bytes}"
                )
            for subject_id in subject_ids:
                yield _subject_from_open_artifact(
                    handle,
                    path_name,
                    str(subject_id),
                    signals=signals,
                    source_artifact=artifact_id,
                )
        finally:
            handle.close()
            reader.close()


__all__ = [
    "AlignedPathSegment",
    "PWDBRemotePathClient",
    "RaggedPathWaveField",
    "RemoteArtifactIdentity",
    "merge_ragged_path_fields",
]
