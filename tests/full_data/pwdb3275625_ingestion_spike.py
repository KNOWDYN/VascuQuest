"""Tier-3 empirical ingestion spike for canonical PWDB Zenodo record 3275625.

This is repository validation tooling, not production path-reader code.  It exists
only to measure the real source representations and select an evidence-backed
production strategy before Batch 9.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tempfile
import time
import traceback
from typing import Any
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from vascuquest.data import require_verified_artifact  # noqa: E402
from vascuquest.schema import load_manifest  # noqa: E402

N_SUBJECTS = 4374
SITES = (
    "AorticRoot", "ThorAorta", "AbdAorta", "IliacBif", "Carotid",
    "SupTemporal", "SupMidCerebral", "Brachial", "Radial", "Digital",
    "CommonIliac", "Femoral", "AntTibial",
)
SIGNALS = ("P", "U", "A", "PPG")
REQUIRED = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
    "common_site_waveforms_wfdb",
    "unified_matlab",
    "path_aorta_foot_p",
)


class SpikeFailure(RuntimeError):
    """A hard Batch-8 empirical-gate failure."""


def dep(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise SpikeFailure(f"missing Tier-3 validation dependency {name!r}") from exc


def subject_number(raw: str) -> int:
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise SpikeFailure(f"invalid subject identifier {raw!r}") from exc
    if not math.isfinite(value) or value < 1 or not value.is_integer():
        raise SpikeFailure(f"invalid subject identifier {raw!r}")
    return int(value)


def expected_subjects() -> tuple[int, ...]:
    return tuple(range(1, N_SUBJECTS + 1))


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
    t0 = time.perf_counter()
    value = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    after = rss_bytes()
    return value, elapsed, {
        "method": "linux-/proc/VmRSS" if before is not None else "unavailable",
        "before_bytes": before,
        "after_bytes": after,
        "delta_bytes": None if before is None or after is None else after - before,
    }


def verify_required(root: Path) -> dict[str, Any]:
    manifest = load_manifest()
    out: dict[str, Any] = {}
    for artifact_id in REQUIRED:
        artifact = manifest.artifact(artifact_id)
        path = root / artifact.filename
        t0 = time.perf_counter()
        require_verified_artifact(path, artifact)
        out[artifact_id] = {
            "filename": artifact.filename,
            "checksum_algorithm": artifact.checksum_algorithm,
            "checksum": artifact.checksum_value,
            "size_bytes": path.stat().st_size,
            "verification_seconds": time.perf_counter() - t0,
        }
    return out


def inspect_metadata_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, skipinitialspace=True)
        header = tuple(item.strip() for item in next(reader))
        if "Subject Number" not in header:
            raise SpikeFailure("metadata CSV lacks explicit Subject Number")
        col = header.index("Subject Number")
        ids = tuple(subject_number(row[col]) for row in reader if row)
    if ids != expected_subjects():
        raise SpikeFailure("metadata CSV subject order is not exactly 1..4374")
    return {
        "rows": len(ids),
        "columns": list(header),
        "indexing": "explicit Subject Number; source order 1..4374",
        "decision": "DIRECT",
        "decision_basis": "complete explicit subject indexing in canonical CSV",
    }


def member_by_basename(zf: zipfile.ZipFile, basename: str) -> zipfile.ZipInfo:
    hits = [
        info for info in zf.infolist()
        if not info.is_dir() and PurePosixPath(info.filename).name == basename
    ]
    if len(hits) != 1:
        raise SpikeFailure(f"expected one {basename!r} member, found {len(hits)}")
    return hits[0]


def inspect_geometry(path: Path) -> dict[str, Any]:
    pat = re.compile(r"pwdb_geo_(\d{4})\.csv$")
    with zipfile.ZipFile(path) as zf:
        ids = sorted(
            int(m.group(1))
            for info in zf.infolist()
            if not info.is_dir()
            for m in [pat.fullmatch(PurePosixPath(info.filename).name)]
            if m
        )
        if tuple(ids) != expected_subjects():
            raise SpikeFailure("geometry members do not map exactly to subjects 1..4374")
        info = member_by_basename(zf, "pwdb_geo_0001.csv")
        with zf.open(info) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            header = tuple(item.strip() for item in next(reader))
            rows = [row for row in reader if row]
    required = {
        "seg_no", "inlet_node", "outlet_node", "length",
        "inlet_radius", "outlet_radius", "peripheral_c", "peripheral_r",
    }
    missing = sorted(required - set(header))
    if missing:
        raise SpikeFailure(f"geometry fields missing: {missing}")
    return {
        "subject_members": len(ids),
        "representative_member": info.filename,
        "representative_segments": len(rows),
        "columns": list(header),
        "indexing": "one explicitly numbered CSV member per subject",
        "decision": "DIRECT",
        "decision_basis": "bounded per-subject member access is native to the archive",
    }


def inspect_common_csv(path: Path) -> tuple[list[float], dict[str, Any]]:
    expected_names = {f"PWs_{site}_{signal}.csv" for site in SITES for signal in SIGNALS}
    basename = "PWs_AorticRoot_P.csv"
    with zipfile.ZipFile(path) as zf:
        names = {
            PurePosixPath(info.filename).name
            for info in zf.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".csv")
        }
        if names != expected_names:
            raise SpikeFailure("common-site CSV archive is not exactly 13 sites x 4 signals")
        info = member_by_basename(zf, basename)
        with zf.open(info) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            header = tuple(item.strip() for item in next(reader))
            if not header or header[0] != "Subject Number":
                raise SpikeFailure(f"{basename} lacks explicit Subject Number")
            ids: list[int] = []
            row1: list[str] | None = None
            for row in reader:
                if not row:
                    continue
                sid = subject_number(row[0])
                ids.append(sid)
                if sid == 1:
                    row1 = row
    if tuple(ids) != expected_subjects() or row1 is None:
        raise SpikeFailure(f"{basename} subject order is not exactly 1..4374")
    values = [float(x.strip()) if x.strip() else float("nan") for x in row1[1:]]
    last = max((i for i, value in enumerate(values) if math.isfinite(value)), default=-1)
    if last < 0:
        raise SpikeFailure("subject-1 AorticRoot pressure has no finite samples")
    finite_extent = values[: last + 1]
    return finite_extent, {
        "members": len(names),
        "source_member": info.filename,
        "subject": 1,
        "site": "AorticRoot",
        "signal": "P",
        "finite_extent_samples": len(finite_extent),
        "internal_missing": sum(not math.isfinite(value) for value in finite_extent),
        "trailing_padding": len(values) - len(finite_extent),
        "decision": "DIRECT",
        "decision_basis": "validated core production representation",
    }


def wfdb_subject(stem: str) -> int | None:
    match = re.fullmatch(r"pwdb(\d{4})", stem)
    return None if match is None else int(match.group(1))


def inspect_wfdb(path: Path, csv_values: list[float]) -> dict[str, Any]:
    np = dep("numpy")
    wfdb = dep("wfdb")
    with zipfile.ZipFile(path) as zf:
        header_members = [info for info in zf.infolist() if info.filename.endswith(".hea")]
        ids = tuple(sorted(
            sid for sid in (
                wfdb_subject(PurePosixPath(info.filename).stem) for info in header_members
            ) if sid is not None
        ))
        if ids != expected_subjects():
            raise SpikeFailure("WFDB record identities do not map exactly to 1..4374")
        stem = "pwdb0001"
        hea = member_by_basename(zf, stem + ".hea")
        dat = member_by_basename(zf, stem + ".dat")
        with tempfile.TemporaryDirectory(prefix="vascuquest-wfdb-") as td:
            base = Path(td) / stem
            base.with_suffix(".hea").write_bytes(zf.read(hea))
            base.with_suffix(".dat").write_bytes(zf.read(dat))
            header = wfdb.rdheader(str(base))
            if float(header.fs) != 500.0:
                raise SpikeFailure(f"WFDB sampling frequency is {header.fs!r}, expected 500 Hz")
            names = tuple(str(name).rstrip(",").strip() for name in header.sig_name)
            channels = [i for i, name in enumerate(names) if name == "AorticRoot_P"]
            if len(channels) != 1:
                raise SpikeFailure("WFDB lacks exactly one AorticRoot_P channel")
            channel = channels[0]
            units = tuple(str(unit).strip() for unit in header.units)
            if units[channel] != "mmHg":
                raise SpikeFailure(f"WFDB AorticRoot_P unit is {units[channel]!r}")
            n = min(int(header.sig_len), len(csv_values))
            record = wfdb.rdrecord(
                str(base), sampfrom=0, sampto=n, channels=[channel], physical=True
            )
    observed = np.asarray(record.p_signal[:, 0], dtype=float)
    expected = np.asarray(csv_values[:n], dtype=float)
    valid = np.isfinite(observed) & np.isfinite(expected)
    if not bool(valid.any()):
        raise SpikeFailure("CSV/WFDB comparison has no jointly finite samples")
    gain = float(header.adc_gain[channel])
    if not math.isfinite(gain) or gain == 0:
        raise SpikeFailure("WFDB ADC gain is invalid")
    quantization_step = 1.0 / abs(gain)
    difference = np.abs(observed[valid] - expected[valid])
    max_abs = float(difference.max())
    if max_abs > quantization_step * (1.0 + 1e-9):
        raise SpikeFailure(
            f"CSV/WFDB difference {max_abs} exceeds one ADC step {quantization_step}"
        )
    return {
        "records": len(ids),
        "subject_1_record": stem,
        "sampling_frequency_hz": float(header.fs),
        "signals": int(header.n_sig),
        "channel": names[channel],
        "unit": units[channel],
        "compared_samples": int(valid.sum()),
        "max_abs_difference": max_abs,
        "rmse": float(np.sqrt(np.mean((observed[valid] - expected[valid]) ** 2))),
        "adc_gain": gain,
        "quantization_step": quantization_step,
        "justified_abs_tolerance": quantization_step,
        "tolerance_basis": "one WFDB ADC quantization step",
        "decision": "DIRECT",
        "decision_basis": "canonical WFDB is directly readable; retained for validation rather than core production",
    }


def inspect_unified_mat(path: Path) -> dict[str, Any]:
    scipy_io = dep("scipy.io")
    with path.open("rb") as fh:
        header = fh.read(128)
    if not header.startswith(b"MATLAB 5.0 MAT-file"):
        raise SpikeFailure("pwdb_data.mat is not a conventional MATLAB 5.0 MAT-file")
    variables = scipy_io.whosmat(path)
    if not any(name == "data" for name, _, _ in variables):
        raise SpikeFailure("pwdb_data.mat lacks top-level variable data")
    return {
        "format": "MATLAB 5.0 MAT-file",
        "top_level": [
            {"name": name, "shape": list(shape), "class": klass}
            for name, shape, klass in variables
        ],
        "reader": "scipy.io",
        "nested_lazy_slicing": False,
        "decision": "DIRECT",
        "decision_basis": "direct structural inspection works; this artifact is not required by core production",
    }


def is_reference_dataset(h5py, dataset) -> bool:
    return h5py.check_dtype(ref=dataset.dtype) is not None


def subject_ref(h5py, dataset, subject: int):
    if not is_reference_dataset(h5py, dataset):
        raise SpikeFailure(f"{dataset.name} is not a MATLAB reference dataset")
    axes = [axis for axis, size in enumerate(dataset.shape) if size == N_SUBJECTS]
    if len(axes) != 1:
        raise SpikeFailure(f"{dataset.name} has ambiguous subject axis {dataset.shape}")
    index = [0] * dataset.ndim
    index[axes[0]] = subject - 1
    ref = dataset[tuple(index)]
    if not ref:
        raise SpikeFailure(f"{dataset.name} contains a null subject reference")
    return ref, axes[0]


def bounded_numeric(h5py, np, dataset) -> tuple[Any, dict[str, Any]]:
    if is_reference_dataset(h5py, dataset):
        raise SpikeFailure(f"{dataset.name} unexpectedly remains a reference dataset")
    if dataset.size < 1 or dataset.size > 1_000_000:
        raise SpikeFailure(f"unsafe bounded read size for {dataset.name}: {dataset.size}")
    values = np.asarray(dataset[...], dtype=float).reshape(-1)
    return values, {
        "dataset": dataset.name,
        "shape": list(dataset.shape),
        "dtype": str(dataset.dtype),
        "elements": int(dataset.size),
        "sha256_float64": hashlib.sha256(np.asarray(values, dtype=np.float64).tobytes()).hexdigest(),
    }


def inspect_large_path(path: Path) -> dict[str, Any]:
    h5py = dep("h5py")
    np = dep("numpy")
    if not h5py.is_hdf5(path):
        raise SpikeFailure("large path MAT is not HDF5-backed MATLAB v7.3")
    with h5py.File(path, "r") as handle:
        if "data" not in handle or "path_waves" not in handle["data"]:
            raise SpikeFailure("large path MAT lacks /data/path_waves")
        path_waves = handle["data"]["path_waves"]
        if "aorta_foot" not in path_waves:
            raise SpikeFailure("large path MAT lacks aorta_foot")
        group = path_waves["aorta_foot"]
        if "P" not in group:
            raise SpikeFailure("large path MAT lacks aorta_foot/P")
        signal = group["P"]
        ref, subject_axis = subject_ref(h5py, signal, 1)
        subject_cell = handle[ref]
        if not isinstance(subject_cell, h5py.Dataset) or not is_reference_dataset(h5py, subject_cell):
            raise SpikeFailure("subject-1 path pressure is not a MATLAB cell reference dataset")
        first_position_ref = subject_cell[tuple(0 for _ in subject_cell.shape)]
        if not first_position_ref:
            raise SpikeFailure("first path-position pressure reference is null")
        waveform, waveform_meta = bounded_numeric(h5py, np, handle[first_position_ref])
        if not bool(np.isfinite(waveform).any()):
            raise SpikeFailure("bounded path waveform contains no finite values")

        alignment: dict[str, Any] = {"waveform_position_count": int(subject_cell.size)}
        if "dist" in group:
            distance_ref, _ = subject_ref(h5py, group["dist"], 1)
            distance, distance_meta = bounded_numeric(h5py, np, handle[distance_ref])
            alignment.update({
                "distance_count": int(distance.size),
                "distance_dataset": distance_meta,
                "distance_count_matches_waveform_positions": int(distance.size) == int(subject_cell.size),
            })
            if int(distance.size) != int(subject_cell.size):
                raise SpikeFailure("path distance count does not match waveform-position count")

        return {
            "format": "MATLAB v7.3 / HDF5",
            "root_keys": sorted(handle.keys()),
            "data_keys": sorted(handle["data"].keys()),
            "path_waves_keys": sorted(path_waves.keys()),
            "path_fields": sorted(group.keys()),
            "subject": 1,
            "subject_axis": subject_axis,
            "signal_reference_shape": list(signal.shape),
            "subject_cell_shape": list(subject_cell.shape),
            "bounded_waveform": waveform_meta,
            "bounded_waveform_min": float(np.nanmin(waveform)),
            "bounded_waveform_max": float(np.nanmax(waveform)),
            "alignment": alignment,
            "reader": "h5py",
            "whole_file_materialized": False,
        }


def decide_path_strategy(first: dict[str, Any], repeated: dict[str, Any]) -> dict[str, Any]:
    first_hash = first["bounded_waveform"]["sha256_float64"]
    repeated_hash = repeated["bounded_waveform"]["sha256_float64"]
    if first_hash != repeated_hash:
        raise SpikeFailure("repeated bounded path read is not deterministic")
    alignment = first["alignment"]
    if alignment.get("distance_count_matches_waveform_positions") is False:
        raise SpikeFailure("path coordinate alignment failed")
    return {
        "selected": "DIRECT",
        "alternatives_not_selected": ["INDEXED", "CONVERTED"],
        "basis": [
            "checksum-verified canonical MATLAB v7.3 artifact opened directly with h5py",
            "one subject / one path / one signal / one position waveform was read without whole-file materialization",
            "repeated bounded read produced identical numeric bytes",
            "path-distance cardinality matched waveform-position cardinality when distance metadata was present",
        ],
        "qualification": (
            "Batch 8 establishes direct canonical HDF5 access as the production candidate. "
            "Batch 9 must still implement and test the bounded public path-reader semantics."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--report", type=Path, default=Path("pwdb3275625-tier3-report.json"))
    parser.add_argument("--code-revision", default=os.environ.get("GITHUB_SHA"))
    args = parser.parse_args()

    source_root = args.source_root.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    report: dict[str, Any] = {
        "status": "running",
        "validation_tier": 3,
        "batch": 8,
        "scope": "PWDB path-ingestion empirical gate",
        "record_id": "3275625",
        "doi": "10.5281/zenodo.3275625",
        "code_revision": args.code_revision,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "range_resume": {
            "claimed": False,
            "tested": False,
            "reason": "current ArtifactAcquirer intentionally makes no range/resume claim",
        },
        "checks": {},
    }
    started = time.perf_counter()

    try:
        if not source_root.is_dir():
            raise SpikeFailure(f"source root does not exist: {source_root}")
        manifest = load_manifest()
        report["checks"]["verified_artifacts"] = verify_required(source_root)

        value, seconds, rss = timed(
            inspect_metadata_csv, source_root / manifest.artifact("model_configurations").filename
        )
        report["checks"]["metadata_csv"] = {"seconds": seconds, "rss": rss, **value}

        value, seconds, rss = timed(
            inspect_geometry, source_root / manifest.artifact("geometry").filename
        )
        report["checks"]["geometry"] = {"seconds": seconds, "rss": rss, **value}

        csv_values, csv_info = inspect_common_csv(
            source_root / manifest.artifact("common_site_waveforms_csv").filename
        )
        report["checks"]["common_site_csv"] = csv_info

        value, seconds, rss = timed(
            inspect_wfdb,
            source_root / manifest.artifact("common_site_waveforms_wfdb").filename,
            csv_values,
        )
        report["checks"]["common_site_wfdb"] = {"seconds": seconds, "rss": rss, **value}

        value, seconds, rss = timed(
            inspect_unified_mat, source_root / manifest.artifact("unified_matlab").filename
        )
        report["checks"]["unified_matlab"] = {"seconds": seconds, "rss": rss, **value}

        path_file = source_root / manifest.artifact("path_aorta_foot_p").filename
        first, first_seconds, first_rss = timed(inspect_large_path, path_file)
        repeated, repeated_seconds, repeated_rss = timed(inspect_large_path, path_file)
        report["checks"]["large_path_mat"] = {
            "first_access_seconds": first_seconds,
            "repeated_access_seconds": repeated_seconds,
            "first_access_rss": first_rss,
            "repeated_access_rss": repeated_rss,
            "first": first,
            "repeated": repeated,
        }
        report["path_strategy"] = decide_path_strategy(first, repeated)
        report["source_class_decisions"] = {
            "metadata_csv": report["checks"]["metadata_csv"]["decision"],
            "geometry": report["checks"]["geometry"]["decision"],
            "common_site_csv": report["checks"]["common_site_csv"]["decision"],
            "common_site_wfdb": report["checks"]["common_site_wfdb"]["decision"],
            "unified_matlab": report["checks"]["unified_matlab"]["decision"],
            "large_path_mat": report["path_strategy"]["selected"],
        }
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
