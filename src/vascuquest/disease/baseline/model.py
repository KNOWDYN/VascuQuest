"""Immutable solver-ready healthy cardiovascular state for Virtual Disease."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from vascuquest.domain.identity import DatasetIdentity

MMHG_TO_PA = 133.33


def _positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    invalid = result < 0 if allow_zero else result <= 0
    if invalid:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}")
    return result


def _readonly_1d(values: object, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must be a one-dimensional array with at least two samples")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain finite values")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True, eq=False)
class InflowWaveform:
    """One complete aortic-root volumetric-flow cycle in SI units."""

    time_s: np.ndarray
    flow_m3_per_s: np.ndarray
    source_identity: str

    def __post_init__(self) -> None:
        time = _readonly_1d(self.time_s, "time_s")
        flow = _readonly_1d(self.flow_m3_per_s, "flow_m3_per_s")
        if time.shape != flow.shape:
            raise ValueError("time_s and flow_m3_per_s must have identical shape")
        if not np.all(np.diff(time) > 0):
            raise ValueError("time_s must be strictly increasing")
        if not isinstance(self.source_identity, str) or not self.source_identity.strip():
            raise ValueError("source_identity must be a non-empty string")
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "flow_m3_per_s", flow)

    @property
    def duration_s(self) -> float:
        """Cycle duration inferred from the uniformly sampled source waveform."""
        dt = float(np.median(np.diff(self.time_s)))
        return float(self.time_s[-1] - self.time_s[0] + dt)

    @property
    def mean_flow_m3_per_s(self) -> float:
        return float(np.mean(self.flow_m3_per_s))

    def value_at(self, time_s: float) -> float:
        """Periodically interpolate the source flow without changing its samples."""
        if not math.isfinite(time_s):
            raise ValueError("time_s must be finite")
        duration = self.duration_s
        phase = float(time_s) % duration
        base_time = self.time_s - self.time_s[0]
        extended_time = np.concatenate((base_time, [duration]))
        extended_flow = np.concatenate((self.flow_m3_per_s, [self.flow_m3_per_s[0]]))
        return float(np.interp(phase, extended_time, extended_flow))


@dataclass(frozen=True, slots=True)
class BaselineSegment:
    """One PWDB arterial segment in solver-ready SI units."""

    segment_id: str
    inlet_node: int
    outlet_node: int
    length_m: float
    inlet_radius_m: float
    outlet_radius_m: float
    peripheral_compliance_m3_per_pa: float
    peripheral_resistance_pa_s_per_m3: float

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be a non-empty string")
        for value, name in ((self.inlet_node, "inlet_node"), (self.outlet_node, "outlet_node")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        _positive(self.length_m, "length_m")
        _positive(self.inlet_radius_m, "inlet_radius_m")
        _positive(self.outlet_radius_m, "outlet_radius_m")
        _positive(self.peripheral_compliance_m3_per_pa, "peripheral_compliance_m3_per_pa", allow_zero=True)
        _positive(self.peripheral_resistance_pa_s_per_m3, "peripheral_resistance_pa_s_per_m3", allow_zero=True)

    def radius_at(self, axial_fraction: float) -> float:
        if not isinstance(axial_fraction, (int, float)) or not math.isfinite(float(axial_fraction)):
            raise TypeError("axial_fraction must be finite numeric")
        fraction = float(axial_fraction)
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("axial_fraction must lie in [0, 1]")
        return self.inlet_radius_m + fraction * (self.outlet_radius_m - self.inlet_radius_m)

    @property
    def is_terminal_by_source(self) -> bool:
        return self.peripheral_resistance_pa_s_per_m3 > 0.0


@dataclass(frozen=True, slots=True)
class BaselineCardiovascularState:
    """Complete healthy input state required by the PR-2 forward solver."""

    dataset_identity: DatasetIdentity
    canonical_subject_id: str
    age_years: int
    heart_rate_bpm: float
    stroke_volume_ml: float
    lvet_s: float
    peak_flow_time_s: float
    reverse_flow_volume_ml: float
    diastolic_pressure_pa: float
    mean_pressure_pa: float
    outlet_pressure_pa: float
    blood_density_kg_per_m3: float
    blood_viscosity_pa_s: float
    momentum_correction_alpha: float
    systemic_pvr_pa_s_per_m3: float
    wall_gamma_b0_g_per_s: float
    wall_gamma_b1_g_cm_per_s: float
    stiffness_k1_g_per_s2_per_cm: float
    stiffness_k2_per_cm: float
    stiffness_k3_g_per_s2_per_cm: float
    segments: tuple[BaselineSegment, ...]
    aortic_inflow: InflowWaveform
    source_configuration_member: str
    source_geometry_member: str

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")
        if not isinstance(self.canonical_subject_id, str) or not self.canonical_subject_id.strip():
            raise ValueError("canonical_subject_id must be a non-empty string")
        if isinstance(self.age_years, bool) or not isinstance(self.age_years, int) or self.age_years < 0:
            raise ValueError("age_years must be a non-negative integer")
        for value, name in (
            (self.heart_rate_bpm, "heart_rate_bpm"),
            (self.stroke_volume_ml, "stroke_volume_ml"),
            (self.lvet_s, "lvet_s"),
            (self.diastolic_pressure_pa, "diastolic_pressure_pa"),
            (self.mean_pressure_pa, "mean_pressure_pa"),
            (self.blood_density_kg_per_m3, "blood_density_kg_per_m3"),
            (self.blood_viscosity_pa_s, "blood_viscosity_pa_s"),
            (self.momentum_correction_alpha, "momentum_correction_alpha"),
            (self.systemic_pvr_pa_s_per_m3, "systemic_pvr_pa_s_per_m3"),
            (self.stiffness_k1_g_per_s2_per_cm, "stiffness_k1_g_per_s2_per_cm"),
            (self.stiffness_k3_g_per_s2_per_cm, "stiffness_k3_g_per_s2_per_cm"),
        ):
            _positive(value, name)
        for value, name in (
            (self.peak_flow_time_s, "peak_flow_time_s"),
            (self.reverse_flow_volume_ml, "reverse_flow_volume_ml"),
            (self.outlet_pressure_pa, "outlet_pressure_pa"),
            (self.wall_gamma_b0_g_per_s, "wall_gamma_b0_g_per_s"),
            (self.wall_gamma_b1_g_cm_per_s, "wall_gamma_b1_g_cm_per_s"),
        ):
            _positive(value, name, allow_zero=True)
        if not math.isfinite(self.stiffness_k2_per_cm):
            raise ValueError("stiffness_k2_per_cm must be finite")
        if not isinstance(self.segments, tuple) or not self.segments:
            raise ValueError("segments must be a non-empty tuple")
        if any(not isinstance(item, BaselineSegment) for item in self.segments):
            raise TypeError("segments must contain BaselineSegment values")
        ids = tuple(item.segment_id for item in self.segments)
        if len(ids) != len(set(ids)):
            raise ValueError("segments must not contain duplicate segment IDs")
        if not isinstance(self.aortic_inflow, InflowWaveform):
            raise TypeError("aortic_inflow must be an InflowWaveform")
        for value, name in (
            (self.source_configuration_member, "source_configuration_member"),
            (self.source_geometry_member, "source_geometry_member"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        inlet_nodes = {segment.inlet_node for segment in self.segments}
        outlet_nodes = {segment.outlet_node for segment in self.segments}
        roots = tuple(segment for segment in self.segments if segment.inlet_node not in outlet_nodes)
        if len(roots) != 1:
            raise ValueError("baseline arterial network must expose exactly one root segment")
        if roots[0].segment_id != "1":
            raise ValueError("PWDB baseline reconstruction requires canonical root segment '1'")

        terminals = tuple(segment for segment in self.segments if segment.outlet_node not in inlet_nodes)
        if not terminals:
            raise ValueError("baseline arterial network must contain terminal segments")
        for terminal in terminals:
            if terminal.peripheral_resistance_pa_s_per_m3 <= 0:
                raise ValueError(f"terminal segment {terminal.segment_id!r} lacks peripheral resistance")
            if terminal.peripheral_compliance_m3_per_pa <= 0:
                raise ValueError(f"terminal segment {terminal.segment_id!r} lacks peripheral compliance")

    @property
    def cardiac_period_s(self) -> float:
        return 60.0 / self.heart_rate_bpm

    @property
    def root_segment(self) -> BaselineSegment:
        return next(item for item in self.segments if item.segment_id == "1")

    @property
    def terminal_segment_ids(self) -> tuple[str, ...]:
        inlet_nodes = {segment.inlet_node for segment in self.segments}
        return tuple(segment.segment_id for segment in self.segments if segment.outlet_node not in inlet_nodes)


__all__ = [
    "BaselineCardiovascularState",
    "BaselineSegment",
    "InflowWaveform",
    "MMHG_TO_PA",
]
