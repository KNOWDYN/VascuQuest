"""Tier-3 empirical ingestion spike for canonical PWDB Zenodo record 3275625.

Repository validation tool only. This is not production reader code.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import time
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
    pass


def dep(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise SpikeFailure(
            f"missing spike dependency {name!r}; install the reader candidates "
            "listed in BUILD_PLAN.md"
        ) from exc


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


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    value = fn(*args, **kwargs)
    return value, time.perf_counter() - t0


def rss_bytes() -> int | None:
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return None


def timed_rss(fn, *args, **kwargs):
    before = rss_bytes()
    value, seconds = timed(fn, *args, **kwargs)
    after = rss_bytes()
    return value, seconds, {
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
            "md5": artifact.checksum_value,
            "size_bytes": path.stat().st_size,
            "verification_seconds": time.perf_counter() - t0,
        }
    return out


def inspect_metadata_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, skipinitialspace=True)
        header = tuple(item.strip() for item in next(reader))
        if "Subject Number" not in header:
            raise SpikeFailure("metadata CSV lacks explicit 'Subject Number'")
        col = header.index("Subject Number")
        ids = tuple(subject_number(row[col]) for row in reader if row)
    if ids != expected_subjects():
        raise SpikeFailure("metadata CSV subject coverage/order is not exactly 1..4374")
    return {
        "columns": list(header),
        "rows": len(ids),
        "subject_mapping": "explicit Subject Number, ordered 1..4374",
        "strategy": "DIRECT",
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
            raise SpikeFailure("geometry filenames do not map exactly to subjects 1..4374")
        info = member_by_basename(zf, "pwdb_geo_0001.csv")
        with zf.open(info) as raw:
            reader = csv.reader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""),
                skipinitialspace=True,
            )
            header = tuple(x.strip() for x in next(reader))
            rows = [row for row in reader if row]

    required = {
        "seg_no", "inlet_node", "outlet_node", "length",
        "inlet_radius", "outlet_radius", "peripheral_c", "peripheral_r",
    }
    if required - set(header):
        raise SpikeFailure("geometry source fields differ from the frozen adapter contract")
    return {
        "subject_files": len(ids),
        "subject_1_member": info.filename,
        "columns": list(header),
        "subject_1_segments": len(rows),
        "strategy": "DIRECT",
    }


def common_csv(path: Path) -> tuple[list[float], dict[str, Any]]:
    basename = "PWs_AorticRoot_P.csv"
    expected_names = {
        f"PWs_{site}_{signal}.csv" for site in SITES for signal in SIGNALS
    }
    with zipfile.ZipFile(path) as zf:
        names = {
            PurePosixPath(info.filename).name
            for info in zf.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".csv")
        }
        if names != expected_names:
            raise SpikeFailure("common-site CSV member set is not exactly 13 sites x 4 signals")
        info = member_by_basename(zf, basename)
        with zf.open(info) as raw:
            reader = csv.reader(
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""),
                skipinitialspace=True,
            )
            header = tuple(x.strip() for x in next(reader))
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
        raise SpikeFailure(f"{basename} subject coverage/order is not exactly 1..4374")

    values = [float(x.strip()) if x.strip() else float("nan") for x in row1[1:]]
    last = max((i for i, v in enumerate(values) if math.isfinite(v)), default=-1)
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
        "internal_missing": sum(not math.isfinite(v) for v in finite_extent),
        "trailing_padding": len(values) - len(finite_extent),
        "strategy": "DIRECT",
    }


def wfdb_subject(stem: str) -> int | None:
    match = re.fullmatch(r"pwdb(\d{4})", stem)
    return None if match is None else int(match.group(1))


def inspect_wfdb(path: Path, csv_values: list[float]) -> dict[str, Any]:
    np = dep("numpy")
    wfdb = dep("wfdb")
    with zipfile.ZipFile(path) as zf:
        try:
            records = member_by_basename(zf, "RECORDS")
        except SpikeFailure:
            records = None

        if records is not None:
            with zf.open(records) as raw:
                stems = [line.decode().strip() for line in raw if line.strip()]
            ids = tuple(
                sid for sid in
                (wfdb_subject(PurePosixPath(stem).name) for stem in stems)
                if sid is not None
            )
        else:
            ids = tuple(sorted(
                sid for sid in
                (wfdb_subject(PurePosixPath(info.filename).stem)
                 for info in zf.infolist() if info.filename.endswith(".hea"))
                if sid is not None
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
                raise SpikeFailure(f"WFDB fs={header.fs!r}; expected 500 Hz")
            names = tuple(str(x).strip() for x in header.sig_name)
            channels = [
                i for i, name in enumerate(names)
                if name.rstrip(",").strip() == "AorticRoot_P"
            ]
            if len(channels) != 1:
                raise SpikeFailure("WFDB does not contain exactly one AorticRoot_P channel")
            ch = channels[0]
            units = tuple(str(x).strip() for x in header.units)
            if units[ch] != "mmHg":
                raise SpikeFailure(f"WFDB AorticRoot_P unit={units[ch]!r}")
            n = min(int(header.sig_len), len(csv_values))
            record = wfdb.rdrecord(
                str(base), sampfrom=0, sampto=n, channels=[ch], physical=True
            )

    observed = np.asarray(record.p_signal[:, 0], dtype=float)
    expected = np.asarray(csv_values[:n], dtype=float)
    valid = np.isfinite(observed) & np.isfinite(expected)
    if not bool(valid.any()):
        raise SpikeFailure("CSV/WFDB overlap has no jointly finite samples")
    diff = np.abs(observed[valid] - expected[valid])
    gain = float(header.adc_gain[ch])
    if not math.isfinite(gain) or gain == 0:
        raise SpikeFailure("WFDB ADC gain is invalid")
    step = 1.0 / abs(gain)
    max_abs = float(diff.max())
    if max_abs > step * (1.0 + 1e-9):
        raise SpikeFailure(
            f"CSV/WFDB difference {max_abs} exceeds one WFDB quantization step {step}"
        )
    return {
        "records": len(ids),
        "subject_1_record": stem,
        "fs_hz": float(header.fs),
        "signals": int(header.n_sig),
        "compared_channel": names[ch],
        "unit": units[ch],
        "compared_samples": int(valid.sum()),
        "max_abs_difference": max_abs,
        "rmse": float(np.sqrt(np.mean((observed[valid] - expected[valid]) ** 2))),
        "adc_gain": gain,
        "quantization_step": step,
        "justified_abs_tolerance": step,
        "tolerance_basis": "one WFDB ADC quantization step",
        "strategy": "DIRECT",
    }


def inspect_unified_mat(path: Path) -> dict[str, Any]:
    scipy_io = dep("scipy.io")
    with path.open("rb") as fh:
        header = fh.read(128)
    if not header.startswith(b"MATLAB 5.0 MAT-file"):
        raise SpikeFailure("pwdb_data.mat is not a conventional MATLAB 5.0 MAT-file")
    variables = scipy_io.whosmat(path)
    if not any(name == "data" for name, _, _ in variables):
        raise SpikeFailure("pwdb_data.mat lacks top-level variable 'data'")
    return {
        "format": "MATLAB 5.0 MAT-file",
        "top_level": [
            {"name": name, "shape": list(shape), "class": klass}
            for name, shape, klass in variables
        ],
        "reader": "scipy.io",
        "nested_lazy_slicing": False,
        "strategy": "DIRECT",
        "scope_note": "direct inspection/read only; lightweight artifacts remain preferred",
    }


def is_ref_dataset(h5py, ds) -> bool:
    return h5py.check_dtype(ref=ds.dtype) is not None


def subject_ref(h5py, ds, subject: int):
    if not is_ref_dataset(h5py, ds):
        raise SpikeFailure(f"{ds.name} is not a reference dataset")
    axes = [i for i, size in enumerate(ds.shape) if size == N_SUBJECTS]
    if len(axes) != 1:
        raise SpikeFailure(f"{ds.name} has ambiguous subject axis: {ds.shape}")
    index = [0] * ds.ndim
    index[axes[0]] = subject - 1
    ref = ds[tuple(index)]
    if not ref:
        raise SpikeFailure(f"{ds.name} has null subject reference")
    return ref, axes[0]


def bounded_numeric(h5py, np, ds) -> tuple[Any, dict[str, Any]]:
    if is_ref_dataset(h5py, ds):
        raise SpikeFailure(f"{ds.name} unexpectedly remains a reference dataset")
    if ds.size < 1 or ds.size > 1_000_000:
        raise SpikeFailure(f"unsafe bounded read size for {ds.name}: {ds.size}")
    values = np.asarray(ds[...], dtype=float).reshape(-1)
    return values, {
        "dataset": ds.name,
        "shape": list(ds.shape),
        "dtype": str(ds.dtype),
        "elements": int(ds.size),
        "sha256_float64": hashlib.sha256(
            np.asarray(values, dtype=np.float64).tobytes()
        ).hexdigest(),
    }


def inspect_large_path(path: Path) -> dict[str, Any]:
    h5py = dep("h5py")
    np = dep("numpy")
    if not h5py.is_hdf5(path):
        raise SpikeFailure("large path MAT is not HDF5-backed MATLAB v7.3")

    with h5py.File(path, "r") as f:
        if "data" not in f or "path_waves" not in f["data"]:
            raise SpikeFailure("large path MAT lacks /data/path_waves")
        pw = f["data"]["path_waves"]
        if "aorta_foot" not in pw or "P" not in pw["aorta_foot"]:
            raise SpikeFailure("large path MAT lacks aorta_foot/P")
        group = pw["aorta_foot"]
        field = group["P"]
        ref, axis = subject_ref(h5py, field, 1)
        cell = f[ref]
        if not isinstance(cell, h5py.Dataset) or not is_ref_dataset(h5py, cell):
            raise SpikeFailure("subject-1 path pressure is not a MATLAB cell dataset")
        first_ref = cell[tuple(0 for _ in cell.shape)]
        if not first_ref:
            raise SpikeFailure("first path-position pressure reference is null")
        wave_ds = f[first_ref]
        wave, wave_meta = bounded_numeric(h5py, np, wave_ds)
        if not bool(np.isfinite(wave).any()):
            raise SpikeFailure("bounded path waveform has no finite values")

        alignment: dict[str, Any] = {"waveform_cells": int(cell.size)}
        if "dist" in group:
            dref, _ = subject_ref(h5py, group["dist"], 1)
            dist_ds = f[dref]
            dist, dist_meta = bounded_numeric(h5py, np, dist_ds)
            alignment.update({
                "distance_count": int(dist.size),
                "distance_dataset": dist_meta,
                "count_matches": int(dist.size) == int(cell.size),
            })
            if not alignment["count_matches"]:
                raise SpikeFailure("path distance count does not match waveform cell count")

        return {
            "format": "MATLAB v7.3 / HDF5",
            "root_keys": sorted(f.keys()),
            "data_keys": sorted(f["data"].keys()),
            "path_waves_keys": sorted(pw.keys()),
            "path_fields": sorted(group.keys()),
            "subject": 1,
            "subject_axis": axis,
            "signal_reference_shape": list(field.shape),
            "subject_cell_shape": list(cell.shape),
            "bounded_waveform": wave_meta,
            "bounded_waveform_min": float(np.nanmin(wave)),
            "bounded_waveform_max": float(np.nanmax(wave)),
            "alignment": alignment,
            "reader": "h5py",
            "whole_file_materialized": False,
            "strategy": "DIRECT",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument(
        "--report", type=Path,
        default=Path("pwdb3275625_ingestion_spike_report.json"),
    )
    args = parser.parse_args()
    root = args.source_root.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    report: dict[str, Any] = {
        "record_id": "3275625",
        "doi": "10.5281/zenodo.3275625",
        "status": "running",
        "checks": {},
        "resume_range": {
            "claimed": False,
            "tested": False,
            "reason": "current acquisition layer does not claim resume/range support",
        },
    }

    try:
        if not root.is_dir():
            raise SpikeFailure(f"source root does not exist: {root}")
        report["checks"]["verified_artifacts"] = verify_required(root)
        manifest = load_manifest()

        for name, fn, artifact_id in (
            ("metadata_csv", inspect_metadata_csv, "model_configurations"),
            ("geometry", inspect_geometry, "geometry"),
        ):
            value, seconds = timed(fn, root / manifest.artifact(artifact_id).filename)
            report["checks"][name] = {"seconds": seconds, **value}

        csv_values, csv_info = common_csv(
            root / manifest.artifact("common_site_waveforms_csv").filename
        )
        report["checks"]["common_site_csv"] = csv_info

        value, seconds = timed(
            inspect_wfdb,
            root / manifest.artifact("common_site_waveforms_wfdb").filename,
            csv_values,
        )
        report["checks"]["common_site_wfdb"] = {"seconds": seconds, **value}

        value, seconds = timed(
            inspect_unified_mat,
            root / manifest.artifact("unified_matlab").filename,
        )
        report["checks"]["unified_matlab"] = {"seconds": seconds, **value}

        path_file = root / manifest.artifact("path_aorta_foot_p").filename
        first, first_seconds, first_rss = timed_rss(inspect_large_path, path_file)
        second, second_seconds, second_rss = timed_rss(inspect_large_path, path_file)
        if (
            first["bounded_waveform"]["sha256_float64"]
            != second["bounded_waveform"]["sha256_float64"]
        ):
            raise SpikeFailure("repeated bounded path read is not deterministic")
        report["checks"]["large_path_mat"] = {
            "first_access_seconds": first_seconds,
            "repeated_access_seconds": second_seconds,
            "first_access_rss": first_rss,
            "repeated_access_rss": second_rss,
            "first": first,
            "repeated": second,
            "repeated_read_identical": True,
        }

        report["decisions"] = {
            "metadata_csv": "DIRECT",
            "geometry": "DIRECT",
            "common_site_csv": "DIRECT",
            "common_site_wfdb": "DIRECT",
            "unified_matlab": "DIRECT",
            "large_path_mat": "DIRECT",
        }
        report["status"] = "passed"
        rc = 0
    except Exception as exc:
        report["status"] = "failed"
        report["failure_type"] = type(exc).__name__
        report["failure"] = str(exc)
        rc = 1

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
