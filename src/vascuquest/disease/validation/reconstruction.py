"""Quantitative Gate-0 comparison of native-solver and canonical PWDB waves.

PR 2 deliberately computes reconstruction evidence without declaring a pass
threshold. Qualification tolerances require real-source evidence and are frozen
only after that evidence is reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from vascuquest.api import DatasetSession
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.result import Waveform
from vascuquest.errors import AdmissibilityError

from vascuquest.disease.baseline.model import MMHG_TO_PA
from vascuquest.disease.solver.model import ForwardSolution, SolverDiagnostics


PWDB_COMMON_SITE_MODEL_LOCATIONS: dict[str, tuple[str, float]] = {
    "AorticRoot": ("1", 0.0),
    "ThorAorta": ("18", 1.0),
    "AbdAorta": ("39", 0.0),
    "IliacBif": ("41", 1.0),
    "Carotid": ("15", 0.5),
    "SupTemporal": ("87", 1.0),
    "SupMidCerebral": ("72", 1.0),
    "Brachial": ("21", 0.75),
    "Radial": ("22", 1.0),
    "Digital": ("112", 1.0),
    "CommonIliac": ("44", 0.5),
    "Femoral": ("46", 0.5),
    "AntTibial": ("49", 1.0),
}


class ReconstructionQualificationState(str, Enum):
    """PR-2 reconstruction status before scientific tolerances are frozen."""

    METRICS_ONLY_THRESHOLDS_NOT_FROZEN = "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"


@dataclass(frozen=True, slots=True)
class WaveformReconstructionMetric:
    site_id: str
    signal: str
    normalized_rmse: float
    relative_mean_error: float
    peak_relative_error: float
    trough_relative_error: float
    phase_error_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.site_id, str) or not self.site_id:
            raise ValueError("site_id must be non-empty")
        if self.signal not in {"P", "U", "A", "Q"}:
            raise ValueError("signal must be one of P, U, A or Q")
        for value, name in (
            (self.normalized_rmse, "normalized_rmse"),
            (self.relative_mean_error, "relative_mean_error"),
            (self.peak_relative_error, "peak_relative_error"),
            (self.trough_relative_error, "trough_relative_error"),
        ):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not math.isfinite(float(self.phase_error_s)):
            raise ValueError("phase_error_s must be finite")


@dataclass(frozen=True, slots=True)
class HealthyReconstructionReport:
    canonical_subject_id: str
    metrics: tuple[WaveformReconstructionMetric, ...]
    solver_diagnostics: SolverDiagnostics
    qualification_state: ReconstructionQualificationState = (
        ReconstructionQualificationState.METRICS_ONLY_THRESHOLDS_NOT_FROZEN
    )

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_subject_id, str) or not self.canonical_subject_id:
            raise ValueError("canonical_subject_id must be non-empty")
        if not isinstance(self.metrics, tuple) or not self.metrics:
            raise ValueError("metrics must be a non-empty tuple")
        if any(not isinstance(item, WaveformReconstructionMetric) for item in self.metrics):
            raise TypeError("metrics must contain WaveformReconstructionMetric values")
        if not isinstance(self.solver_diagnostics, SolverDiagnostics):
            raise TypeError("solver_diagnostics must be SolverDiagnostics")
        if self.qualification_state is not ReconstructionQualificationState.METRICS_ONLY_THRESHOLDS_NOT_FROZEN:
            raise ValueError("PR 2 cannot claim reconstruction qualification before thresholds are frozen")


def _relative_error(observed: float, reference: float, scale: float) -> float:
    denominator = max(abs(reference), abs(scale), 1e-30)
    return abs(observed - reference) / denominator


def _phase_error(reference: np.ndarray, modeled: np.ndarray, dt_s: float) -> float:
    ref = reference - np.mean(reference)
    mod = modeled - np.mean(modeled)
    if np.linalg.norm(ref) <= 1e-30 or np.linalg.norm(mod) <= 1e-30:
        return 0.0
    scores = np.asarray([float(np.dot(ref, np.roll(mod, shift))) for shift in range(ref.size)])
    shift = int(np.argmax(scores))
    if shift > ref.size // 2:
        shift -= ref.size
    return float(shift * dt_s)


def waveform_metrics(
    reference: object,
    modeled: object,
    *,
    time_s: object,
    site_id: str,
    signal: str,
) -> WaveformReconstructionMetric:
    """Calculate reproducible reconstruction errors without applying thresholds."""

    ref = np.asarray(reference, dtype=float)
    mod = np.asarray(modeled, dtype=float)
    time = np.asarray(time_s, dtype=float)
    if ref.ndim != 1 or ref.size < 2 or ref.shape != mod.shape or ref.shape != time.shape:
        raise ValueError("reference, modeled and time_s must be aligned 1-D arrays")
    if not np.all(np.isfinite(ref)) or not np.all(np.isfinite(mod)) or not np.all(np.isfinite(time)):
        raise ValueError("reconstruction metric arrays must be finite")
    increments = np.diff(time)
    if np.any(increments <= 0):
        raise ValueError("time_s must be strictly increasing")
    dt = float(np.median(increments))
    rmse = float(np.sqrt(np.mean((mod - ref) ** 2)))
    amplitude = float(np.max(ref) - np.min(ref))
    scale = max(amplitude, float(np.sqrt(np.mean(ref * ref))), 1e-30)
    return WaveformReconstructionMetric(
        site_id=site_id,
        signal=signal,
        normalized_rmse=rmse / scale,
        relative_mean_error=_relative_error(float(np.mean(mod)), float(np.mean(ref)), scale),
        peak_relative_error=_relative_error(float(np.max(mod)), float(np.max(ref)), scale),
        trough_relative_error=_relative_error(float(np.min(mod)), float(np.min(ref)), scale),
        phase_error_s=_phase_error(ref, mod, dt),
    )


def _active_waveform(waveform: Waveform) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(waveform.values, dtype=float)
    time = np.asarray(waveform.time_coordinate.values, dtype=float)
    missing = np.zeros(values.shape, dtype=bool) if waveform.missing_mask is None else np.asarray(waveform.missing_mask, dtype=bool)
    padding = np.zeros(values.shape, dtype=bool) if waveform.padding_mask is None else np.asarray(waveform.padding_mask, dtype=bool)
    if values.shape != time.shape or values.shape != missing.shape or values.shape != padding.shape:
        raise AdmissibilityError("source waveform arrays are not aligned")
    active = ~(missing | padding)
    if np.any(missing & ~padding) or np.count_nonzero(active) < 2:
        raise AdmissibilityError("Gate-0 source waveform has internal missing data or too few samples")
    selected_values = values[active]
    selected_time = time[active]
    if not np.all(np.isfinite(selected_values)):
        raise AdmissibilityError("Gate-0 source waveform contains non-finite active samples")
    return selected_time, selected_values


def _periodic_interpolate(model_time: np.ndarray, values: np.ndarray, target_time: np.ndarray) -> np.ndarray:
    time = np.asarray(model_time, dtype=float)
    series = np.asarray(values, dtype=float)
    target = np.asarray(target_time, dtype=float)
    if time.ndim != 1 or time.size < 2 or time.shape != series.shape:
        raise ValueError("model time and values must be aligned 1-D arrays")
    phase = time - time[0]
    duration = float(phase[-1])
    if duration <= 0:
        raise ValueError("model solution cycle has non-positive duration")
    target_phase = np.mod(target - target[0], duration)
    return np.interp(target_phase, phase, series)


class HealthyReconstructionValidator:
    """Compare one healthy native-solver cycle with canonical PWDB common sites."""

    def evaluate(
        self,
        session: DatasetSession,
        subject_id: str,
        solution: ForwardSolution,
    ) -> HealthyReconstructionReport:
        if not isinstance(session, DatasetSession):
            raise TypeError("session must be a DatasetSession")
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("subject_id must be a non-empty string")
        if not isinstance(solution, ForwardSolution):
            raise TypeError("solution must be a ForwardSolution")
        session.subject(subject_id)

        metrics: list[WaveformReconstructionMetric] = []
        for site_id, (segment_id, fraction) in PWDB_COMMON_SITE_MODEL_LOCATIONS.items():
            site = MeasurementSite(site_id)
            source_p = session.waveform("pressure", subject=subject_id, location=site)
            source_u = session.waveform("flow_velocity", subject=subject_id, location=site)
            source_a = session.waveform("luminal_area", subject=subject_id, location=site)
            p_time, p_values = _active_waveform(source_p)
            u_time, u_values = _active_waveform(source_u)
            a_time, a_values = _active_waveform(source_a)
            if not (
                p_time.shape == u_time.shape == a_time.shape
                and np.allclose(p_time, u_time, rtol=0.0, atol=1e-12)
                and np.allclose(p_time, a_time, rtol=0.0, atol=1e-12)
            ):
                raise AdmissibilityError(f"PWDB P/U/A source coordinates are not aligned at {site_id}")

            segment = solution.segment(segment_id)
            index = segment.spatial_index(fraction)
            model_area = segment.area_m2[:, index]
            model_flow = segment.flow_m3_per_s[:, index]
            model_pressure = segment.pressure_pa[:, index] / MMHG_TO_PA
            model_velocity = model_flow / model_area
            modeled = {
                "P": _periodic_interpolate(solution.time_s, model_pressure, p_time),
                "U": _periodic_interpolate(solution.time_s, model_velocity, p_time),
                "A": _periodic_interpolate(solution.time_s, model_area, p_time),
                "Q": _periodic_interpolate(solution.time_s, model_flow, p_time),
            }
            source = {
                "P": p_values,
                "U": u_values,
                "A": a_values,
                "Q": u_values * a_values,
            }
            for signal in ("P", "U", "A", "Q"):
                metrics.append(
                    waveform_metrics(
                        source[signal],
                        modeled[signal],
                        time_s=p_time,
                        site_id=site_id,
                        signal=signal,
                    )
                )

        return HealthyReconstructionReport(
            canonical_subject_id=subject_id,
            metrics=tuple(metrics),
            solver_diagnostics=solution.diagnostics,
        )


__all__ = [
    "HealthyReconstructionReport",
    "HealthyReconstructionValidator",
    "PWDB_COMMON_SITE_MODEL_LOCATIONS",
    "ReconstructionQualificationState",
    "WaveformReconstructionMetric",
    "waveform_metrics",
]
