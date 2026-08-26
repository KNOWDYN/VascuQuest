"""Path-specific Tier-4 validation through sparse canonical Zenodo HDF5 reads.

Each invocation validates one canonical PWDB path artifact without downloading it
wholesale. The independent oracle and production reader both use bounded HTTP
ranges, but they traverse the HDF5 structure independently. Exact float64 bytes,
coordinates, provenance, Python/CLI parity, cache reuse, transfer volume and
access latency are all release-gated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import subprocess
import sys
import time
from typing import Any

import h5py
import numpy as np

from vascuquest.backends.pwdb3275625.csv_reader import SubjectCSVTable
from vascuquest.backends.pwdb3275625.http_range import (
    CanonicalRemoteFile,
    HTTPRangeReader,
    RemoteFileMetadata,
    verify_zenodo_file_identity,
)
from vascuquest.backends.pwdb3275625.path_backend import PWDB3275625PathBackend
from vascuquest.backends.pwdb3275625.path_reader import PATH_ARTIFACT_SPECS
from vascuquest.bootstrap import _compose_session
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.domain import PathPosition, SubjectKey
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.errors import DatasetUnavailableError, SelectionError
from vascuquest.schema import load_manifest

N_SUBJECTS = 4374
RANGE_BLOCK_BYTES = 64 * 1024
RANGE_CACHE_BLOCKS = 256
MAX_ORACLE_TRANSFER_BYTES = 256 * 1024 * 1024
MAX_PRODUCTION_TRANSFER_BYTES = 256 * 1024 * 1024
MAX_FIRST_PRODUCTION_SECONDS = 300.0
MAX_CACHE_REPEAT_SECONDS = 10.0

EXPECTED = {
    "path_aorta_brain": {"canonical_path_id": "aorta_brain", "source_path_id": "aorta_brain", "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"}, "age": 25},
    "path_aorta_finger": {"canonical_path_id": "aorta_finger", "source_path_id": "aorta_finger", "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"}, "age": 35},
    "path_aorta_foot_a": {"canonical_path_id": "aorta_foot", "source_path_id": "aorta_foot", "signals": {"A": "luminal_area"}, "age": 45},
    "path_aorta_foot_p": {"canonical_path_id": "aorta_foot", "source_path_id": "aorta_foot", "signals": {"P": "pressure"}, "age": 55},
    "path_aorta_foot_u": {"canonical_path_id": "aorta_foot", "source_path_id": "aorta_foot", "signals": {"U": "flow_velocity"}, "age": 65},
    "path_aorta_rsubclavian": {"canonical_path_id": "aorta_r_subclavian", "source_path_id": "aorta_r_subclavian", "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"}, "age": 75},
}
EXPECTED_UNITS = {"P": "mmHg", "U": "m/s", "A": "m^2"}


def _sha256_float64(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64).reshape(-1))
    return hashlib.sha256(array.tobytes()).hexdigest()


def _rss_bytes() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _is_reference_dataset(dataset: h5py.Dataset) -> bool:
    return h5py.check_dtype(ref=dataset.dtype) is not None


def _ref_at_axis(dataset: h5py.Dataset, *, cardinality: int, index_value: int):
    if not _is_reference_dataset(dataset):
        raise AssertionError(f"{dataset.name} is not a MATLAB reference dataset")
    axes = [axis for axis, size in enumerate(dataset.shape) if size == cardinality]
    if len(axes) != 1:
        raise AssertionError(f"ambiguous reference axis for {dataset.name}: {dataset.shape}")
    index = [0] * dataset.ndim
    index[axes[0]] = index_value
    ref = dataset[tuple(index)]
    assert ref, f"null reference in {dataset.name} at {index_value}"
    return ref


def _subject_ref(dataset: h5py.Dataset, subject_number: int):
    return _ref_at_axis(dataset, cardinality=N_SUBJECTS, index_value=subject_number - 1)


def _numeric(dataset: h5py.Dataset) -> np.ndarray:
    assert not _is_reference_dataset(dataset), dataset.name
    values = np.asarray(dataset[...], dtype=np.float64).reshape(-1)
    assert 0 < values.size <= 1_000_000
    return values


def _numeric_scalar(handle: h5py.File, dataset: h5py.Dataset) -> float:
    node: h5py.Dataset = dataset
    if _is_reference_dataset(node):
        assert node.size == 1
        ref = node[tuple(0 for _ in node.shape)]
        assert ref
        node = handle[ref]
    values = _numeric(node)
    assert values.size == 1
    value = float(values[0])
    assert math.isfinite(value)
    return value


def _remote_source(artifact: Any) -> CanonicalRemoteFile:
    return CanonicalRemoteFile(
        url=artifact.source_locator,
        record_id=artifact.canonical_record_id,
        filename=artifact.filename,
        checksum_algorithm=artifact.checksum_algorithm,
        checksum_value=artifact.checksum_value,
    )


def _oracle(
    source: CanonicalRemoteFile,
    metadata: RemoteFileMetadata,
    expected: dict[str, Any],
    *,
    subject_number: int,
) -> tuple[dict[str, Any], dict[str, int]]:
    remote = HTTPRangeReader(
        source.url,
        size_bytes=metadata.size_bytes,
        block_size=RANGE_BLOCK_BYTES,
        max_blocks=RANGE_CACHE_BLOCKS,
    )
    with remote:
        with h5py.File(remote, "r") as handle:
            path_waves = handle["data"]["path_waves"]
            source_path_id = expected["source_path_id"]
            assert source_path_id in path_waves
            group = path_waves[source_path_id]
            distance_dataset = handle[_subject_ref(group["dist"], subject_number)]
            distances = _numeric(distance_dataset)
            assert bool(np.isfinite(distances).all())
            position_count = int(distances.size)
            positions = tuple(dict.fromkeys((0, position_count // 2, position_count - 1)))
            fs = _numeric_scalar(handle, path_waves["fs"])
            assert fs > 0
            signals: dict[str, Any] = {}
            for source_signal in expected["signals"]:
                subject_cell = handle[_subject_ref(group[source_signal], subject_number)]
                assert isinstance(subject_cell, h5py.Dataset) and _is_reference_dataset(subject_cell)
                assert int(subject_cell.size) == position_count
                selected: dict[str, Any] = {}
                for position in positions:
                    ref = _ref_at_axis(
                        subject_cell,
                        cardinality=position_count,
                        index_value=int(position),
                    )
                    dataset = handle[ref]
                    values = _numeric(dataset)
                    selected[str(position)] = {
                        "dataset": dataset.name,
                        "values": values.copy(),
                        "sha256_float64": _sha256_float64(values),
                        "sample_count": int(values.size),
                    }
                signals[source_signal] = selected
            oracle = {
                "distance_dataset": distance_dataset.name,
                "distances": distances.copy(),
                "distance_sha256_float64": _sha256_float64(distances),
                "position_count": position_count,
                "positions": positions,
                "sample_rate_hz": fs,
                "signals": signals,
            }
    transfer = {
        "bytes_transferred": remote.bytes_transferred,
        "range_requests": remote.range_requests,
    }
    assert transfer["bytes_transferred"] < metadata.size_bytes
    assert transfer["bytes_transferred"] <= MAX_ORACLE_TRANSFER_BYTES
    return oracle, transfer


def _acquire_with_retry(acquirer: ArtifactAcquirer, artifact_id: str, attempts: int = 3) -> Path:
    for attempt in range(1, attempts + 1):
        try:
            return acquirer.acquire(artifact_id, offline=False)
        except DatasetUnavailableError:
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def _subject_for_age(model_config_path: Path, age: int) -> str:
    table = SubjectCSVTable(model_config_path)
    matches = [
        subject_id
        for subject_id in table.subject_ids()
        if table.numeric(subject_id, "age [years]").value == float(age)
    ]
    assert matches, f"no canonical PWDB subject found for age {age}"
    return matches[0]


def _portable_tuple(document_value: object) -> tuple[float, ...]:
    assert isinstance(document_value, dict) and document_value.get("__vascuquest_type__") == "tuple"
    items = document_value.get("items")
    assert isinstance(items, list)
    return tuple(float(value) for value in items)


def _path_distance(result: object) -> float:
    matches = [item for item in getattr(result, "coordinates") if getattr(item, "name") == "path_distance"]
    assert len(matches) == 1 and matches[0].unit == "m"
    return float(matches[0].values)


def _assert_result(
    result: object,
    *,
    canonical_name: str,
    source_signal: str,
    path_id: str,
    position: int,
    distance: float,
    oracle_values: np.ndarray,
    fs: float,
) -> None:
    assert getattr(result, "quantity").canonical_name == canonical_name
    assert getattr(result, "canonical_unit") == EXPECTED_UNITS[source_signal]
    assert getattr(result, "source_unit") == EXPECTED_UNITS[source_signal]
    assert getattr(result, "source_label") == source_signal
    assert getattr(result, "evidence") is EvidenceClass.SOURCE
    assert getattr(result, "location") == PathPosition(path_id, position)
    values = np.asarray(getattr(result, "values"), dtype=np.float64)
    assert values.tobytes() == np.asarray(oracle_values, dtype=np.float64).tobytes()
    assert _path_distance(result) == float(distance)
    assert getattr(result, "time_coordinate").values == tuple(index / fs for index in range(int(values.size)))
    assert getattr(result, "time_coordinate").unit == "s"


def run(artifact_id: str, report_path: Path) -> dict[str, Any]:
    if artifact_id not in EXPECTED:
        raise ValueError(f"unsupported Tier-4 path artifact {artifact_id!r}")
    expected = EXPECTED[artifact_id]
    manifest = load_manifest()
    artifact = manifest.artifact(artifact_id)
    production_spec = PATH_ARTIFACT_SPECS[artifact_id]
    assert artifact.role == "path_resolved_waveform_data"
    assert production_spec.canonical_path_id == expected["canonical_path_id"]
    assert production_spec.source_path_id == expected["source_path_id"]
    assert set(production_spec.signals) == set(expected["signals"])
    assert production_spec.capability in artifact.capabilities_provided

    print(f"[{artifact_id}] resolve canonical subject", flush=True)
    paths = DataPaths.default()
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry, manifest=manifest)
    model_config_path = _acquire_with_retry(acquirer, "model_configurations")
    inspection = verify_artifact(model_config_path, manifest.artifact("model_configurations"))
    assert inspection.state.value == "verified"
    subject_id = _subject_for_age(model_config_path, int(expected["age"]))
    subject_number = int(subject_id)

    source = _remote_source(artifact)
    identity_started = time.perf_counter()
    remote_metadata = verify_zenodo_file_identity(source)
    remote_identity_seconds = time.perf_counter() - identity_started
    assert acquirer.resolve_local(artifact_id) is None
    assert not paths.source_artifact(artifact.filename).exists()

    print(f"[{artifact_id}] independent sparse oracle", flush=True)
    oracle_started = time.perf_counter()
    oracle, oracle_transfer = _oracle(
        source,
        remote_metadata,
        expected,
        subject_number=subject_number,
    )
    oracle_seconds = time.perf_counter() - oracle_started
    print(
        f"[{artifact_id}] oracle {oracle_seconds:.3f}s, "
        f"{oracle_transfer['bytes_transferred']} bytes / {oracle_transfer['range_requests']} ranges",
        flush=True,
    )

    backend = PWDB3275625PathBackend.from_acquirer(acquirer, offline=False, manifest=manifest)
    session = _compose_session(backend)
    subject = SubjectKey(session.identity, subject_id)
    assert session.status().path_resolved_supported is True
    path_id = expected["canonical_path_id"]
    positions = tuple(int(value) for value in oracle["positions"])
    first_signal = next(iter(expected["signals"]))
    first_name = expected["signals"][first_signal]
    first_position = positions[0]

    print(f"[{artifact_id}] first production read", flush=True)
    rss_before = _rss_bytes()
    first_started = time.perf_counter()
    first = session.waveform(
        first_name,
        subject=subject,
        location=PathPosition(path_id, first_position),
    )
    first_seconds = time.perf_counter() - first_started
    rss_after = _rss_bytes()
    assert first_seconds <= MAX_FIRST_PRODUCTION_SECONDS, first_seconds
    _assert_result(
        first,
        canonical_name=first_name,
        source_signal=first_signal,
        path_id=path_id,
        position=first_position,
        distance=float(oracle["distances"][first_position]),
        oracle_values=oracle["signals"][first_signal][str(first_position)]["values"],
        fs=float(oracle["sample_rate_hz"]),
    )

    validated_reads: list[dict[str, Any]] = []
    for source_signal, canonical_name in expected["signals"].items():
        for position in positions:
            print(f"[{artifact_id}] production {source_signal}@{position}", flush=True)
            result = session.waveform(
                canonical_name,
                subject=subject,
                location=PathPosition(path_id, position),
            )
            oracle_entry = oracle["signals"][source_signal][str(position)]
            _assert_result(
                result,
                canonical_name=canonical_name,
                source_signal=source_signal,
                path_id=path_id,
                position=position,
                distance=float(oracle["distances"][position]),
                oracle_values=oracle_entry["values"],
                fs=float(oracle["sample_rate_hz"]),
            )
            provenance = backend.provenance(result.provenance_ref)
            assert provenance.evidence is EvidenceClass.SOURCE
            assert provenance.location == PathPosition(path_id, position)
            assert tuple(item.artifact_id for item in provenance.source_artifacts) == (artifact_id,)
            assert provenance.source_artifacts[0].checksum_value == artifact.checksum_value
            assert any("derived cache" in item for item in provenance.assumptions)
            assert any("HTTP byte ranges" in item for item in provenance.assumptions)
            reproduced = session.reproduce(provenance)
            assert np.asarray(reproduced.values, dtype=np.float64).tobytes() == np.asarray(result.values, dtype=np.float64).tobytes()
            validated_reads.append(
                {
                    "source_signal": source_signal,
                    "canonical_name": canonical_name,
                    "position": position,
                    "distance_m": float(oracle["distances"][position]),
                    "sample_count": oracle_entry["sample_count"],
                    "sha256_float64": oracle_entry["sha256_float64"],
                    "provenance_ref": result.provenance_ref,
                }
            )

    reader = backend._path_reader(artifact_id)
    production_stats = reader.transport_stats
    assert production_stats.bytes_transferred < remote_metadata.size_bytes
    assert production_stats.bytes_transferred <= MAX_PRODUCTION_TRANSFER_BYTES
    assert not paths.source_artifact(artifact.filename).exists()

    try:
        session.waveform(
            first_name,
            subject=subject,
            location=PathPosition(path_id, int(oracle["position_count"])),
        )
    except SelectionError:
        pass
    else:
        raise AssertionError("out-of-range path position did not fail explicitly")

    print(f"[{artifact_id}] fresh-backend exact cache read", flush=True)
    repeat_backend = PWDB3275625PathBackend.from_acquirer(acquirer, offline=False, manifest=manifest)
    repeat_session = _compose_session(repeat_backend)
    repeat_started = time.perf_counter()
    repeated = repeat_session.waveform(
        first_name,
        subject=SubjectKey(repeat_session.identity, subject_id),
        location=PathPosition(path_id, first_position),
    )
    repeat_seconds = time.perf_counter() - repeat_started
    assert repeat_seconds <= MAX_CACHE_REPEAT_SECONDS, repeat_seconds
    _assert_result(
        repeated,
        canonical_name=first_name,
        source_signal=first_signal,
        path_id=path_id,
        position=first_position,
        distance=float(oracle["distances"][first_position]),
        oracle_values=oracle["signals"][first_signal][str(first_position)]["values"],
        fs=float(oracle["sample_rate_hz"]),
    )
    repeat_stats = repeat_backend._path_reader(artifact_id).transport_stats
    assert repeat_stats.bytes_transferred == 0
    assert repeat_stats.range_requests == 0

    subject_cache_dir = (
        paths.derived
        / "pwdb3275625"
        / "path-waveforms"
        / artifact_id
        / f"subject-{subject_number:04d}"
    )
    assert subject_cache_dir.is_dir()
    assert (subject_cache_dir / "index.npz").is_file()
    assert paths.derived in subject_cache_dir.parents and paths.source not in subject_cache_dir.parents

    cli_position = positions[-1]
    cli_signal = first_signal
    cli_name = expected["signals"][cli_signal]
    cli_started = time.perf_counter()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "waveform",
            cli_name,
            "--subject",
            subject_id,
            "--path",
            path_id,
            "--position",
            str(cli_position),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    cli_seconds = time.perf_counter() - cli_started
    assert completed.returncode == 0, completed.stderr
    cli_doc = json.loads(completed.stdout)
    cli_values = _portable_tuple(cli_doc["values"])
    oracle_cli = oracle["signals"][cli_signal][str(cli_position)]["values"]
    assert np.asarray(cli_values, dtype=np.float64).tobytes() == np.asarray(oracle_cli, dtype=np.float64).tobytes()
    metadata = cli_doc["metadata"]
    assert metadata["quantity"]["canonical_name"] == cli_name
    assert metadata["evidence"] == "SOURCE"
    assert metadata["location"] == {
        "kind": "path_position",
        "canonical_path_id": path_id,
        "position_index": cli_position,
    }
    assert not paths.source_artifact(artifact.filename).exists()

    derived_size = sum(item.stat().st_size for item in subject_cache_dir.glob("*.npz"))
    report: dict[str, Any] = {
        "status": "passed",
        "validation_tier": 4,
        "scope": "path_resolved_artifact_sparse_remote",
        "dataset": {
            "record_id": manifest.canonical_record_id,
            "doi": manifest.canonical_doi,
            "subject_id": subject_id,
            "subject_age_years": expected["age"],
        },
        "artifact": {
            "artifact_id": artifact_id,
            "filename": artifact.filename,
            "checksum_algorithm": artifact.checksum_algorithm,
            "checksum_value": artifact.checksum_value,
            "zenodo_metadata_size_bytes": remote_metadata.size_bytes,
            "remote_identity_seconds": remote_identity_seconds,
            "full_artifact_downloaded": False,
        },
        "path": {
            "canonical_path_id": path_id,
            "source_path_id": expected["source_path_id"],
            "position_count": oracle["position_count"],
            "sample_rate_hz": oracle["sample_rate_hz"],
            "distance_dataset": oracle["distance_dataset"],
            "distance_sha256_float64": oracle["distance_sha256_float64"],
            "sampled_positions": list(positions),
            "signals": sorted(expected["signals"]),
        },
        "validated_reads": validated_reads,
        "sparse_transport": {
            "range_block_bytes": RANGE_BLOCK_BYTES,
            "oracle_bytes_transferred": oracle_transfer["bytes_transferred"],
            "oracle_range_requests": oracle_transfer["range_requests"],
            "oracle_transfer_fraction": oracle_transfer["bytes_transferred"] / remote_metadata.size_bytes,
            "production_bytes_transferred": production_stats.bytes_transferred,
            "production_range_requests": production_stats.range_requests,
            "production_remote_opens": production_stats.remote_opens,
            "production_transfer_fraction": production_stats.bytes_transferred / remote_metadata.size_bytes,
            "fresh_backend_cache_bytes_transferred": repeat_stats.bytes_transferred,
            "source_cache_contains_full_path_artifact": False,
        },
        "performance": {
            "oracle_seconds": oracle_seconds,
            "first_production_access_seconds": first_seconds,
            "fresh_backend_cache_access_seconds": repeat_seconds,
            "cli_cache_access_seconds": cli_seconds,
            "rss_peak_before_first_bytes": rss_before,
            "rss_peak_after_first_bytes": rss_after,
            "derived_subject_cache_size_bytes": derived_size,
        },
        "semantics": {
            "canonical_source_remains_authoritative": True,
            "zenodo_record_metadata_matches_manifest_checksum": True,
            "whole_remote_file_rehashed_per_sparse_read": False,
            "derived_index_rebuildable": True,
            "derived_waveform_cache_rebuildable": True,
            "interpolation_performed": False,
            "common_site_substitution_performed": False,
            "python_cli_parity_checked": True,
            "source_reproduction_checked": True,
            "age_stratified_across_six_artifact_matrix": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, allow_nan=False), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-id", required=True, choices=tuple(EXPECTED))
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    run(args.artifact_id, args.report)


if __name__ == "__main__":
    main()
