"""Run Batch 8 with the source-derived CSV/WFDB comparison oracle.

The first canonical Tier-3 run demonstrated that the original one-ADC-step
comparison omitted the independent precision loss from PWDB's CSV export.
PWDB's authoritative ``export_pwdb.m`` writes the common-site CSV matrices with
``dlmwrite`` and no precision override; MATLAB's documented default is five
significant digits.  The same physical waveform is independently passed to
``mat2wfdb`` for WFDB digitization.

This wrapper changes only that cross-representation validation oracle.  All
canonical checksum, subject-alignment, MATLAB/HDF5, bounded-path, memory,
timing, and strategy-selection gates remain the base Batch-8 harness.
"""

from __future__ import annotations

import math
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

import pwdb3275625_ingestion_spike as base

CSV_SIGNIFICANT_DIGITS = 5


def csv_rounding_half_interval(value: float) -> float:
    """Maximum half-interval from dlmwrite's five-significant-digit rounding."""
    if not math.isfinite(value):
        return float("nan")
    if value == 0.0:
        return 0.0
    decade = math.floor(math.log10(abs(value)))
    serialization_step = 10.0 ** (decade - (CSV_SIGNIFICANT_DIGITS - 1))
    return 0.5 * serialization_step


def inspect_wfdb(path: Path, csv_values: list[float]) -> dict[str, object]:
    """Compare canonical CSV and WFDB using both serialization error sources."""
    np = base.dep("numpy")
    wfdb = base.dep("wfdb")

    with zipfile.ZipFile(path) as zf:
        header_members = [info for info in zf.infolist() if info.filename.endswith(".hea")]
        ids = tuple(sorted(
            sid for sid in (
                base.wfdb_subject(PurePosixPath(info.filename).stem)
                for info in header_members
            ) if sid is not None
        ))
        if ids != base.expected_subjects():
            raise base.SpikeFailure("WFDB record identities do not map exactly to 1..4374")

        stem = "pwdb0001"
        hea = base.member_by_basename(zf, stem + ".hea")
        dat = base.member_by_basename(zf, stem + ".dat")
        with tempfile.TemporaryDirectory(prefix="vascuquest-wfdb-") as td:
            record_base = Path(td) / stem
            record_base.with_suffix(".hea").write_bytes(zf.read(hea))
            record_base.with_suffix(".dat").write_bytes(zf.read(dat))
            header = wfdb.rdheader(str(record_base))
            if float(header.fs) != 500.0:
                raise base.SpikeFailure(
                    f"WFDB sampling frequency is {header.fs!r}, expected 500 Hz"
                )
            names = tuple(str(name).rstrip(",").strip() for name in header.sig_name)
            channels = [i for i, name in enumerate(names) if name == "AorticRoot_P"]
            if len(channels) != 1:
                raise base.SpikeFailure("WFDB lacks exactly one AorticRoot_P channel")
            channel = channels[0]
            units = tuple(str(unit).strip() for unit in header.units)
            if units[channel] != "mmHg":
                raise base.SpikeFailure(f"WFDB AorticRoot_P unit is {units[channel]!r}")
            n = min(int(header.sig_len), len(csv_values))
            record = wfdb.rdrecord(
                str(record_base), sampfrom=0, sampto=n, channels=[channel], physical=True
            )

    observed = np.asarray(record.p_signal[:, 0], dtype=float)
    expected = np.asarray(csv_values[:n], dtype=float)
    valid = np.isfinite(observed) & np.isfinite(expected)
    if not bool(valid.any()):
        raise base.SpikeFailure("CSV/WFDB comparison has no jointly finite samples")

    gain = float(header.adc_gain[channel])
    if not math.isfinite(gain) or gain == 0:
        raise base.SpikeFailure("WFDB ADC gain is invalid")
    quantization_step = 1.0 / abs(gain)

    observed_valid = observed[valid]
    expected_valid = expected[valid]
    difference = np.abs(observed_valid - expected_valid)
    csv_half_intervals = np.asarray(
        [csv_rounding_half_interval(float(value)) for value in expected_valid],
        dtype=float,
    )
    floating_slack = (
        np.finfo(float).eps
        * 8.0
        * np.maximum(1.0, np.maximum(np.abs(observed_valid), np.abs(expected_valid)))
    )
    allowed = csv_half_intervals + quantization_step + floating_slack

    violations = difference > allowed
    if bool(violations.any()):
        ratios = np.divide(
            difference,
            allowed,
            out=np.full_like(difference, np.inf),
            where=allowed > 0,
        )
        worst = int(np.argmax(ratios))
        raise base.SpikeFailure(
            "CSV/WFDB difference exceeds source-derived serialization bound: "
            f"sample={worst}, csv={expected_valid[worst]}, wfdb={observed_valid[worst]}, "
            f"difference={difference[worst]}, allowed={allowed[worst]}, "
            f"ratio={ratios[worst]}"
        )

    max_index = int(np.argmax(difference))
    max_abs = float(difference[max_index])
    max_allowed = float(allowed[max_index])
    ratios = np.divide(
        difference,
        allowed,
        out=np.zeros_like(difference),
        where=allowed > 0,
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
        "rmse": float(np.sqrt(np.mean((observed_valid - expected_valid) ** 2))),
        "adc_gain": gain,
        "wfdb_quantization_step": quantization_step,
        "csv_significant_digits": CSV_SIGNIFICANT_DIGITS,
        "max_csv_rounding_half_interval": float(csv_half_intervals.max()),
        "max_allowed_difference_at_observed_max": max_allowed,
        "max_fraction_of_allowed_bound": float(ratios.max()),
        "tolerance_basis": (
            "PWDB export_pwdb.m writes CSV with dlmwrite and no precision override; "
            "MATLAB dlmwrite default precision is five significant digits. The "
            "same physical signal is independently digitized by mat2wfdb. Per-sample "
            "allowance is half the CSV five-significant-digit rounding interval plus "
            "one WFDB quantization step, with machine-epsilon slack."
        ),
        "decision": "DIRECT",
        "decision_basis": (
            "canonical WFDB is directly readable; retained for validation rather "
            "than core production"
        ),
    }


base.inspect_wfdb = inspect_wfdb


if __name__ == "__main__":
    raise SystemExit(base.main())
