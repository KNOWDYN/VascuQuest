"""Resolve Batch-8 path access strategy from the successful real-source baseline.

This script runs only after the canonical Tier-3 ingestion spike has passed.  It
compares the same bounded scientific payload through three access strategies:

* DIRECT: the measured MATLAB-reference traversal from the base Tier-3 report;
* INDEXED: direct HDF5 object-path access after that traversal has identified the
  canonical waveform and distance datasets;
* CONVERTED: an exact-fidelity representative NumPy shard derived from those
  verified canonical datasets.

The converted shard is an empirical strategy probe, not a production storage
commitment.  Batch 9 must implement only the strategy selected here and retain
canonical source identity/provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import traceback
from typing import Any

MATERIAL_IMPROVEMENT_RATIO = 0.10


class StrategyFailure(RuntimeError):
    """Hard failure of the Batch-8 path-strategy resolution gate."""


def dep(name: str):
    try:
        return __import__(name)
    except ImportError as exc:
        raise StrategyFailure(f"missing path-strategy dependency {name!r}") from exc


def rss_bytes() -> int | None:
    status = Path("/proc/self/status")
    if not status.is_file():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None


def timed(fn, *args, **kwargs):
    before = rss_bytes()
    started = time.perf_counter()
    value = fn(*args, **kwargs)
    seconds = time.perf_counter() - started
    after = rss_bytes()
    return value, seconds, {
        "method": "linux-/proc/VmRSS" if before is not None else "unavailable",
        "before_bytes": before,
        "after_bytes": after,
        "delta_bytes": None if before is None or after is None else after - before,
    }


def float64_hash(values) -> str:
    np = dep("numpy")
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return hashlib.sha256(array.tobytes()).hexdigest()


def load_indexed_payload(
    mat_path: Path,
    waveform_dataset: str,
    distance_dataset: str,
) -> dict[str, Any]:
    h5py = dep("h5py")
    np = dep("numpy")
    if not h5py.is_hdf5(mat_path):
        raise StrategyFailure("canonical path MAT is not HDF5-backed")
    with h5py.File(mat_path, "r") as handle:
        if waveform_dataset not in handle:
            raise StrategyFailure(f"indexed waveform dataset is absent: {waveform_dataset}")
        if distance_dataset not in handle:
            raise StrategyFailure(f"indexed distance dataset is absent: {distance_dataset}")
        waveform_ds = handle[waveform_dataset]
        distance_ds = handle[distance_dataset]
        if waveform_ds.size < 1 or waveform_ds.size > 1_000_000:
            raise StrategyFailure(f"unsafe indexed waveform size: {waveform_ds.size}")
        if distance_ds.size < 1 or distance_ds.size > 1_000_000:
            raise StrategyFailure(f"unsafe indexed distance size: {distance_ds.size}")
        waveform = np.asarray(waveform_ds[...], dtype=np.float64).reshape(-1)
        distances = np.asarray(distance_ds[...], dtype=np.float64).reshape(-1)
    if not bool(np.isfinite(waveform).any()):
        raise StrategyFailure("indexed waveform has no finite values")
    if not bool(np.isfinite(distances).all()):
        raise StrategyFailure("indexed distances contain non-finite values")
    return {
        "waveform": waveform,
        "distances": distances,
        "waveform_dataset": waveform_dataset,
        "distance_dataset": distance_dataset,
    }


def payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    waveform = payload["waveform"]
    distances = payload["distances"]
    return {
        "waveform_elements": int(waveform.size),
        "distance_elements": int(distances.size),
        "waveform_sha256_float64": float64_hash(waveform),
        "distance_sha256_float64": float64_hash(distances),
        "waveform_dataset": payload["waveform_dataset"],
        "distance_dataset": payload["distance_dataset"],
    }


def require_exact_payload(
    summary: dict[str, Any],
    expected_waveform_hash: str,
    expected_distance_hash: str,
) -> None:
    if summary["waveform_sha256_float64"] != expected_waveform_hash:
        raise StrategyFailure("candidate waveform bytes differ from canonical direct read")
    if summary["distance_sha256_float64"] != expected_distance_hash:
        raise StrategyFailure("candidate distance bytes differ from canonical direct read")


def write_converted_shard(
    output: Path,
    payload: dict[str, Any],
    *,
    source_filename: str,
    source_md5: str,
) -> dict[str, Any]:
    np = dep("numpy")
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        output,
        waveform=np.asarray(payload["waveform"], dtype=np.float64),
        distances=np.asarray(payload["distances"], dtype=np.float64),
        subject=np.asarray(1, dtype=np.int64),
        path_id=np.asarray("aorta_foot"),
        signal=np.asarray("P"),
        position_index=np.asarray(0, dtype=np.int64),
        source_filename=np.asarray(source_filename),
        source_md5=np.asarray(source_md5),
        waveform_dataset=np.asarray(payload["waveform_dataset"]),
        distance_dataset=np.asarray(payload["distance_dataset"]),
    )
    return {
        "format": "NumPy NPZ (uncompressed exact-fidelity representative shard)",
        "size_bytes": output.stat().st_size,
        "subject": 1,
        "path": "aorta_foot",
        "signal": "P",
        "position_index": 0,
        "source_filename": source_filename,
        "source_md5": source_md5,
    }


def read_converted_shard(
    path: Path,
    *,
    source_filename: str,
    source_md5: str,
) -> dict[str, Any]:
    np = dep("numpy")
    with np.load(path, allow_pickle=False) as data:
        subject = int(data["subject"])
        path_id = str(data["path_id"])
        signal = str(data["signal"])
        position_index = int(data["position_index"])
        observed_source_filename = str(data["source_filename"])
        observed_source_md5 = str(data["source_md5"])
        waveform_dataset = str(data["waveform_dataset"])
        distance_dataset = str(data["distance_dataset"])
        waveform = np.asarray(data["waveform"], dtype=np.float64).reshape(-1)
        distances = np.asarray(data["distances"], dtype=np.float64).reshape(-1)
    if (subject, path_id, signal, position_index) != (1, "aorta_foot", "P", 0):
        raise StrategyFailure("converted shard changed scientific identity")
    if observed_source_filename != source_filename or observed_source_md5 != source_md5:
        raise StrategyFailure("converted shard changed canonical source identity")
    return {
        "waveform": waveform,
        "distances": distances,
        "waveform_dataset": waveform_dataset,
        "distance_dataset": distance_dataset,
    }


def select_strategy(
    direct_repeated_seconds: float,
    indexed_repeated_seconds: float,
    converted_repeated_seconds: float,
) -> dict[str, Any]:
    values = {
        "DIRECT": direct_repeated_seconds,
        "INDEXED": indexed_repeated_seconds,
        "CONVERTED": converted_repeated_seconds,
    }
    for name, value in values.items():
        if not math.isfinite(value) or value <= 0:
            raise StrategyFailure(f"invalid {name} repeated-read timing: {value!r}")

    indexed_ratio = indexed_repeated_seconds / direct_repeated_seconds
    converted_ratio = converted_repeated_seconds / direct_repeated_seconds

    # Prefer the least-transforming strategy that changes the observed access
    # performance class by at least one order of magnitude.  This deliberately
    # avoids adding derivative storage for marginal timing differences.
    if indexed_ratio <= MATERIAL_IMPROVEMENT_RATIO:
        selected = "INDEXED"
        basis = (
            "direct HDF5 object-path access preserves the canonical artifact and "
            "improves repeated bounded access by at least one order of magnitude"
        )
    elif converted_ratio <= MATERIAL_IMPROVEMENT_RATIO:
        selected = "CONVERTED"
        basis = (
            "direct object-path indexing does not remove the measured access cost, "
            "while exact-fidelity converted access improves repeated bounded access "
            "by at least one order of magnitude"
        )
    else:
        raise StrategyFailure(
            "neither INDEXED nor CONVERTED access materially improves the measured "
            "DIRECT repeated-read baseline"
        )

    return {
        "selected": selected,
        "direct_repeated_seconds": direct_repeated_seconds,
        "indexed_repeated_seconds": indexed_repeated_seconds,
        "converted_repeated_seconds": converted_repeated_seconds,
        "indexed_to_direct_ratio": indexed_ratio,
        "converted_to_direct_ratio": converted_ratio,
        "material_improvement_ratio": MATERIAL_IMPROVEMENT_RATIO,
        "selection_rule": (
            "prefer INDEXED when exact direct-object-path repeated access is <=10% "
            "of DIRECT time; otherwise select CONVERTED when its exact repeated "
            "access is <=10% of DIRECT time; fail rather than choose on marginal gains"
        ),
        "basis": basis,
    }


def self_test() -> None:
    assert select_strategy(100.0, 5.0, 0.01)["selected"] == "INDEXED"
    assert select_strategy(100.0, 20.0, 0.01)["selected"] == "CONVERTED"
    try:
        select_strategy(100.0, 20.0, 15.0)
    except StrategyFailure:
        pass
    else:
        raise AssertionError("strategy selector must reject marginal candidates")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path, nargs="?")
    parser.add_argument("base_report", type=Path, nargs="?")
    parser.add_argument("--report", type=Path, default=Path("pwdb3275625-path-strategy.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("path-strategy self-test passed", flush=True)
        return 0
    if args.source_root is None or args.base_report is None:
        parser.error("source_root and base_report are required unless --self-test is used")

    source_root = args.source_root.expanduser().resolve()
    base_report_path = args.base_report.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    report: dict[str, Any] = {
        "status": "running",
        "validation_tier": 3,
        "batch": 8,
        "scope": "PWDB path-strategy resolution",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    }
    started = time.perf_counter()

    try:
        base_report = json.loads(base_report_path.read_text(encoding="utf-8"))
        if base_report.get("status") != "passed":
            raise StrategyFailure("base canonical Tier-3 ingestion report did not pass")
        report["base_code_revision"] = base_report.get("code_revision")

        large = base_report["checks"]["large_path_mat"]
        first = large["first"]
        direct_repeated_seconds = float(large["repeated_access_seconds"])
        waveform_meta = first["bounded_waveform"]
        distance_meta = first["alignment"]["distance_dataset"]
        waveform_dataset = str(waveform_meta["dataset"])
        distance_dataset = str(distance_meta["dataset"])
        expected_waveform_hash = str(waveform_meta["sha256_float64"])
        expected_distance_hash = str(distance_meta["sha256_float64"])

        source = base_report["checks"]["verified_artifacts"]["path_aorta_foot_p"]
        source_filename = str(source["filename"])
        source_md5 = str(source["checksum"])
        mat_path = source_root / source_filename
        if not mat_path.is_file():
            raise StrategyFailure(f"canonical path source is missing: {mat_path}")

        indexed_first, indexed_first_seconds, indexed_first_rss = timed(
            load_indexed_payload, mat_path, waveform_dataset, distance_dataset
        )
        indexed_first_summary = payload_summary(indexed_first)
        require_exact_payload(
            indexed_first_summary, expected_waveform_hash, expected_distance_hash
        )
        indexed_repeat, indexed_repeat_seconds, indexed_repeat_rss = timed(
            load_indexed_payload, mat_path, waveform_dataset, distance_dataset
        )
        indexed_repeat_summary = payload_summary(indexed_repeat)
        require_exact_payload(
            indexed_repeat_summary, expected_waveform_hash, expected_distance_hash
        )

        with tempfile.TemporaryDirectory(prefix="vascuquest-converted-path-") as td:
            shard = Path(td) / "subject0001_aorta_foot_P_position0000.npz"
            converted_build, converted_build_seconds, converted_build_rss = timed(
                write_converted_shard,
                shard,
                indexed_first,
                source_filename=source_filename,
                source_md5=source_md5,
            )
            converted_first, converted_first_seconds, converted_first_rss = timed(
                read_converted_shard,
                shard,
                source_filename=source_filename,
                source_md5=source_md5,
            )
            converted_first_summary = payload_summary(converted_first)
            require_exact_payload(
                converted_first_summary, expected_waveform_hash, expected_distance_hash
            )
            converted_repeat, converted_repeat_seconds, converted_repeat_rss = timed(
                read_converted_shard,
                shard,
                source_filename=source_filename,
                source_md5=source_md5,
            )
            converted_repeat_summary = payload_summary(converted_repeat)
            require_exact_payload(
                converted_repeat_summary, expected_waveform_hash, expected_distance_hash
            )

        report["direct_baseline"] = {
            "first_access_seconds": float(large["first_access_seconds"]),
            "repeated_access_seconds": direct_repeated_seconds,
            "first_access_rss": large["first_access_rss"],
            "repeated_access_rss": large["repeated_access_rss"],
            "waveform_sha256_float64": expected_waveform_hash,
            "distance_sha256_float64": expected_distance_hash,
        }
        report["indexed_candidate"] = {
            "index_semantics": (
                "canonical HDF5 object paths discovered from the MATLAB reference graph; "
                "no waveform values are copied into the index"
            ),
            "first_access_seconds": indexed_first_seconds,
            "repeated_access_seconds": indexed_repeat_seconds,
            "first_access_rss": indexed_first_rss,
            "repeated_access_rss": indexed_repeat_rss,
            "first": indexed_first_summary,
            "repeated": indexed_repeat_summary,
            "whole_file_materialized": False,
        }
        report["converted_candidate"] = {
            "build": converted_build,
            "build_seconds": converted_build_seconds,
            "build_rss": converted_build_rss,
            "first_access_seconds": converted_first_seconds,
            "repeated_access_seconds": converted_repeat_seconds,
            "first_access_rss": converted_first_rss,
            "repeated_access_rss": converted_repeat_rss,
            "first": converted_first_summary,
            "repeated": converted_repeat_summary,
            "whole_file_materialized": False,
            "qualification": (
                "representative exact-fidelity shard only; this benchmark does not "
                "freeze the eventual Batch-9 converted layout"
            ),
        }
        report["path_strategy"] = select_strategy(
            direct_repeated_seconds,
            indexed_repeat_seconds,
            converted_repeat_seconds,
        )
        report["path_strategy"]["fidelity"] = (
            "INDEXED and CONVERTED candidates reproduce the canonical waveform and "
            "distance float64 SHA-256 hashes exactly"
        )
        report["status"] = "passed"
        return_code = 0
    except Exception as exc:
        report["status"] = "failed"
        report["failure_type"] = type(exc).__name__
        report["failure"] = str(exc)
        report["traceback"] = traceback.format_exc()
        return_code = 1
    finally:
        report["elapsed_seconds"] = time.perf_counter() - started
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
