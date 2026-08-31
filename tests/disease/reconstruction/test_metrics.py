from __future__ import annotations

import numpy as np

from vascuquest.disease.validation.reconstruction import (
    PWDB_COMMON_SITE_MODEL_LOCATIONS,
    ReconstructionQualificationState,
    waveform_metrics,
)


def test_gate0_site_mapping_matches_all_common_pwdb_sites() -> None:
    assert tuple(PWDB_COMMON_SITE_MODEL_LOCATIONS) == (
        "AorticRoot",
        "ThorAorta",
        "AbdAorta",
        "IliacBif",
        "Carotid",
        "SupTemporal",
        "SupMidCerebral",
        "Brachial",
        "Radial",
        "Digital",
        "CommonIliac",
        "Femoral",
        "AntTibial",
    )


def test_identical_waveforms_have_zero_reconstruction_error() -> None:
    time = np.arange(8, dtype=float) * 0.125
    reference = np.asarray([0.0, 1.0, 2.0, 1.0, 0.0, -1.0, -2.0, -1.0])
    metric = waveform_metrics(
        reference,
        reference.copy(),
        time_s=time,
        site_id="AorticRoot",
        signal="Q",
    )
    assert metric.normalized_rmse == 0.0
    assert metric.relative_mean_error == 0.0
    assert metric.peak_relative_error == 0.0
    assert metric.trough_relative_error == 0.0
    assert metric.phase_error_s == 0.0


def test_phase_metric_detects_circular_sample_shift() -> None:
    time = np.arange(8, dtype=float) * 0.125
    reference = np.asarray([0.0, 1.0, 2.0, 1.0, 0.0, -1.0, -2.0, -1.0])
    modeled = np.roll(reference, 2)
    metric = waveform_metrics(
        reference,
        modeled,
        time_s=time,
        site_id="Carotid",
        signal="P",
    )
    assert np.isclose(abs(metric.phase_error_s), 0.25)


def test_pr2_has_no_validated_qualification_state() -> None:
    assert tuple(ReconstructionQualificationState) == (
        ReconstructionQualificationState.METRICS_ONLY_THRESHOLDS_NOT_FROZEN,
    )
