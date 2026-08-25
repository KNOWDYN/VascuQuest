"""Path-specific Tier-4 validation against one canonical PWDB path artifact.

Each invocation validates exactly one of the six path-resolved source artifacts.
The GitHub Actions matrix runs the six invocations independently so no runner
must hold the complete ~44 GB archive at once.
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

import vascuquest as vq
from vascuquest.backends.pwdb3275625.path_backend import PWDB3275625PathBackend
from vascuquest.backends.pwdb3275625.path_reader import PATH_ARTIFACT_SPECS
from vascuquest.bootstrap import _compose_session
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.domain import PathPosition, SubjectKey
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.errors import DatasetUnavailableError
from vascuquest.schema import load_manifest

SUBJECT_ID = "1"
SUBJECT_NUMBER = 1
N_SUBJECTS = 4374
DIRECT_REPEAT_BASELINE_SECONDS = 94.519317007
CACHE_REPEAT_MAX_SECONDS = DIRECT_REPEAT_BASELINE_SECONDS * 0.10

# Independent validation contract derived from the authoritative PWDB export split.
EXPECTED = {
    "path_aorta_brain": {
        "canonical_path_id": "aorta_brain",
        "source_path_id": "aorta_brain",
        "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"},
    },
    "path_aorta_finger": {
        "canonical_path_id": "aorta_finger",
        "source_path_id": "aorta_finger",
        "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"},
    },
    "path_aorta_foot_p": {
        "canonical_path_id": "aorta_foot",
        "source_path_id": "aorta_foot",
        "signals": {"P": "pressure"},
    },
    "path_aorta_foot_u": {
        "canonical_path_id": "aorta_foot",
        "source_path_id": "aorta_foot",
        "signals": {"U": "flow_velocity"},
    },
    "path_aorta_foot_a": {
        "canonical_path_id": "aorta_foot",
        "source_path_id": "aorta_foot",
        "signals": {"A": "luminal_area"},
    },
    "path_aorta_rsubclavian": {
        "canonical_path_id": "aorta_r_subclavian",
        "source_path_id": "aorta_r_subclavian",
        "signals": {"P": "pressure", "U": "flow_velocity", "A": "luminal_area"},
    },
}

EXPECTED_UNITS = {"P": "mmHg", "U": "m/s", "A": "m^2"}


def _sha256_float64(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64).reshape(-1))
    return hashlib.sha256(array.tobytes()).hexdigest()


def _rss_bytes() -> int:
    # Linux ru_maxrss is KiB. The validation workflow intentionally runs on Linux.
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _is_reference_dataset(dataset: h5py.Dataset) -> bool:
    return h5py.check_dtype(ref=dataset.dtype) is not None


def _subject_ref(dataset: h5py.Dataset, subject_number: int):
    if not _is_reference_dataset(dataset):
        raise AssertionError(f"{dataset.name} is not a MATLAB reference dataset")
    axes = [axis for axis, size in enumerate(dataset.shape) if size == N_SUBJECTS]
    if len(axes) != 1:
        raise AssertionError(f"ambiguous subject axis for {dataset.name}: {dataset.shape}")
    index = [0] * dataset.ndim
    index[axes[0]] = subject_number - 1
    ref = dataset[tuple(index)]
    assert ref, f"null subject reference in {dataset.name}"
    return ref


def _numeric(dataset: h5py.Dataset) -> np.ndarray:
    assert not _is_reference_dataset(dataset), dataset.name
    return np.asarray(dataset[...], dtype=np.float64).reshape(-1)


def _numeric_scalar(handle: h5py.File, dataset: h5py.Dataset) -> float:
    node: h5py.Dataset = dataset
    if _is_reference_dataset(node):
        refs = np.asarray(node[...]).reshape(-1)
        assert len(refs) == 1 and refs[0]
        node = handle[refs[0]]
    values = _numeric(node)
    assert values.size == 1
    value = float(values[0])
    assert math.isfinite(value)
    return value


def _oracle(source: Path, expected: dict[str, Any]) -> dict[str, Any]:
    with h5py.File(source, "r") as handle:
        path_waves = handle["data"]["path_waves"]
        source_path_id = expected["source_path_id"]
        assert source_path_id in path_waves
        group = path_waves[source_path_id]

        distance_ref = _subject_ref(group["dist"], SUBJECT_NUMBER)
        distance_dataset = handle[distance_ref]
        distances = _numeric(distance_dataset)
        assert distances.size > 0
        assert bool(np.isfinite(distances).all())
        position_count = int(distances.size)
        positions = tuple(dict.fromkeys((0, position_count // 2, position_count - 1)))
        fs = _numeric_scalar(handle, path_waves["fs"])
        assert fs > 0

        signals: dict[str, Any] = {}
        for source_signal in expected["signals"]:
            subject_ref = _subject_ref(group[source_signal], SUBJECT_NUMBER)
            subject_cell = handle[subject_ref]
            assert isinstance(subject_cell, h5py.Dataset)
            assert _is_reference_dataset(subject_cell)
            refs = np.asarray(subject_cell[...]).reshape(-1)
            assert int(refs.size) == position_count
            selected: dict[str, Any] = {}
            for position in positions:
                ref = refs[position]
                assert ref
                dataset = handle[ref]
                values = _numeric(dataset)
                selected[str(position)] = {
                    "dataset": dataset.name,
                    "values": values.copy(),
                    "sha256_float64": _sha256_float64(values),
                    "sample_count": int(values.size),
                }
            signals[source_signal] = selected

        return {
            "distance_dataset": distance_dataset.name,
            "distances": distances.copy(),
            "distance_sha256_float64": _sha256_float64(distances),
            "position_count": position_count,
            "positions": positions,
            "sample_rate_hz": fs,
            "signals": signals,
        }


def _acquire_with_retry(acquirer: ArtifactAcquirer, artifact_id: str, attempts: int = 3) -> Path:
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return acquirer.acquire(artifact_id, offline=False)
        except DatasetUnavailableError as exc:
            errors.append(f"attempt {attempt}: {exc}")
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    raise AssertionError(errors)


def _portable_tuple(document_value: object) -> tuple[float, ...]:
    assert isinstance(document_value, dict)
    assert document_value.get("__vascuquest_type__") == "tuple"
    items = document_value.get("items")
    assert isinstance(items, list)
    return tuple(float(value) for value in items)


def _path_distance(result: object) -> float:
    coordinates = getattr(result, "coordinates")
    matches = [item for item in coordinates if getattr(item, "name") == "path_distance"]
    assert len(matches) == 1
    assert matches[0].unit == "m"
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
    expected_time = tuple(index / fs for index in range(int(values.size)))
    assert getattr(result, "time_coordinate").values == expected_time
    assert getattr(result, "time_coordinate").unit == "s"


def run(artifact_id: str, report_path: Path) -> dict[str, Any]:
    if artifact_id not in EXPECTED:
        raise ValueError(f"unsupported Tier-4 path artifact {artifact_id!r}")
    expected = EXPECTED[artifact_id]
    manifest = load_manifest()
    artifact = manifest.artifact(artifact_id)
    assert artifact.role == "path_resolved_waveform_data"

    production_spec = PATH_ARTIFACT_SPECS[artifact_id]
    assert production_spec.canonical_path_id == expected["canonical_path_id"]
    assert production_spec.source_path_id == expected["source_path_id"]
    assert set(production_spec.signals) == set(expected["signals"])
    assert production_spec.capability in artifact.capabilities_provided

    paths = DataPaths.default()
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry, manifest=manifest)

    acquired: dict[str, Path] = {}
    acquisition_seconds: dict[str, float] = {}
    for required in ("model_configurations", artifact_id):
        started = time.perf_counter()
        acquired[required] = _acquire_with_retry(acquirer, required)
        acquisition_seconds[required] = time.perf_counter() - started
        inspection = verify_artifact(acquired[required], manifest.artifact(required))
        assert inspection.state.value == "verified"

    oracle_started = time.perf_counter()
    oracle = _oracle(acquired[artifact_id], expected)
    oracle_seconds = time.perf_counter() - oracle_started

    def resolver(requested: str) -> Path:
        try:
            return acquired[requested]
        except KeyError as exc:
            raise AssertionError(f"unexpected Tier-4 artifact request {requested!r}") from exc

    backend = PWDB3275625PathBackend(resolver, derived_root=paths.derived)
    session = _compose_session(backend)
    subject = SubjectKey(session.identity, SUBJECT_ID)
    assert session.status().path_resolved_supported is True

    path_id = expected["canonical_path_id"]
    positions = oracle["positions"]
    first_signal = next(iter(expected["signals"]))
    first_name = expected["signals"][first_signal]
    first_position = int(positions[0])

    rss_before = _rss_bytes()
    first_started = time.perf_counter()
    first = session.waveform(
        first_name,
        subject=subject,
        location=PathPosition(path_id, first_position),
    )
    first_seconds = time.perf_counter() - first_started
    rss_after = _rss_bytes()
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
            result = session.waveform(
                canonical_name,
                subject=subject,
                location=PathPosition(path_id, int(position)),
            )
            oracle_entry = oracle["signals"][source_signal][str(position)]
            _assert_result(
                result,
                canonical_name=canonical_name,
                source_signal=source_signal,
                path_id=path_id,
                position=int(position),
                distance=float(oracle["distances"][position]),
                oracle_values=oracle_entry["values"],
                fs=float(oracle["sample_rate_hz"]),
            )
            provenance = backend.provenance(result.provenance_ref)
            assert provenance.evidence is EvidenceClass.SOURCE
            assert provenance.location == PathPosition(path_id, int(position))
            assert tuple(item.artifact_id for item in provenance.source_artifacts) == (
                artifact_id,
            )
            assert provenance.source_artifacts[0].checksum_value == artifact.checksum_value
            assert any("derived cache" in item for item in provenance.assumptions)
            reproduced = session.reproduce(provenance)
            assert np.asarray(reproduced.values, dtype=np.float64).tobytes() == np.asarray(
                result.values, dtype=np.float64
            ).tobytes()
            validated_reads.append(
                {
                    "source_signal": source_signal,
                    "canonical_name": canonical_name,
                    "position": int(position),
                    "distance_m": float(oracle["distances"][position]),
                    "sample_count": oracle_entry["sample_count"],
                    "sha256_float64": oracle_entry["sha256_float64"],
                    "provenance_ref": result.provenance_ref,
                }
            )

    # A fresh backend instance must hit the persistent derived cache rather than
    # repeat the MATLAB-reference traversal. The threshold is fixed at one-tenth
    # of the Batch-8 repeated DIRECT baseline (94.519317007 s).
    repeat_backend = PWDB3275625PathBackend(resolver, derived_root=paths.derived)
    repeat_session = _compose_session(repeat_backend)
    repeat_started = time.perf_counter()
    repeated = repeat_session.waveform(
        first_name,
        subject=SubjectKey(repeat_session.identity, SUBJECT_ID),
        location=PathPosition(path_id, first_position),
    )
    repeat_seconds = time.perf_counter() - repeat_started
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
    assert repeat_seconds <= CACHE_REPEAT_MAX_SECONDS, (
        repeat_seconds,
        CACHE_REPEAT_MAX_SECONDS,
    )

    cache_path = (
        paths.derived
        / "pwdb3275625"
        / "path-waveforms"
        / artifact_id
        / "subject-0001.npz"
    )
    assert cache_path.is_file()
    assert paths.derived in cache_path.parents
    assert paths.source not in cache_path.parents

    # CLI parity is checked after cache creation so the CLI is judged on adapter
    # parity, not on the one-time source traversal needed to construct the cache.
    cli_position = int(positions[-1])
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
            SUBJECT_ID,
            "--path",
            path_id,
            "--position",
            str(cli_position),
            "--offline",
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    cli_seconds = time.perf_counter() - cli_started
    assert completed.returncode == 0, completed.stderr
    cli_doc = json.loads(completed.stdout)
    cli_values = _portable_tuple(cli_doc["values"])
    oracle_cli = oracle["signals"][cli_signal][str(cli_position)]["values"]
    assert np.asarray(cli_values, dtype=np.float64).tobytes() == np.asarray(
        oracle_cli, dtype=np.float64
    ).tobytes()
    metadata = cli_doc["metadata"]
    assert metadata["quantity"]["canonical_name"] == cli_name
    assert metadata["evidence"] == "SOURCE"
    assert metadata["location"] == {
        "kind": "path_position",
        "canonical_path_id": path_id,
        "position_index": cli_position,
    }

    report: dict[str, Any] = {
        "status": "passed",
        "validation_tier": 4,
        "scope": "path_resolved_artifact",
        "dataset": {
            "record_id": manifest.canonical_record_id,
            "doi": manifest.canonical_doi,
            "subject_id": SUBJECT_ID,
        },
        "artifact": {
            "artifact_id": artifact_id,
            "filename": artifact.filename,
            "checksum_algorithm": artifact.checksum_algorithm,
            "checksum_value": artifact.checksum_value,
            "size_bytes": acquired[artifact_id].stat().st_size,
            "acquisition_seconds": acquisition_seconds[artifact_id],
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
        "performance": {
            "batch8_direct_repeat_baseline_seconds": DIRECT_REPEAT_BASELINE_SECONDS,
            "cache_repeat_max_seconds": CACHE_REPEAT_MAX_SECONDS,
            "oracle_seconds": oracle_seconds,
            "first_production_access_seconds": first_seconds,
            "fresh_backend_cache_access_seconds": repeat_seconds,
            "cli_cache_access_seconds": cli_seconds,
            "rss_peak_before_first_bytes": rss_before,
            "rss_peak_after_first_bytes": rss_after,
            "derived_cache_size_bytes": cache_path.stat().st_size,
        },
        "semantics": {
            "canonical_source_remains_authoritative": True,
            "derived_cache_rebuildable": True,
            "interpolation_performed": False,
            "common_site_substitution_performed": False,
            "python_cli_parity_checked": True,
            "source_reproduction_checked": True,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-id", required=True, choices=tuple(EXPECTED))
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = run(args.artifact_id, args.report)
    print(json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
