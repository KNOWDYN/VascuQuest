"""Numerical value objects for the native Virtual Disease 1-D solver."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _readonly(values: object, *, ndim: int, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    if array.ndim != ndim or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite {ndim}-D array")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class SolverOptions:
    """Frozen numerical controls; none are disease parameters."""

    target_dx_m: float = 0.01
    minimum_cells_per_segment: int = 3
    cfl: float = 0.45
    diffusion_safety: float = 0.40
    minimum_cycles: int = 3
    maximum_cycles: int = 20
    periodicity_tolerance: float = 1e-4
    area_floor_ratio: float = 0.20

    def __post_init__(self) -> None:
        for value, name in (
            (self.target_dx_m, "target_dx_m"),
            (self.cfl, "cfl"),
            (self.diffusion_safety, "diffusion_safety"),
            (self.periodicity_tolerance, "periodicity_tolerance"),
            (self.area_floor_ratio, "area_floor_ratio"),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0
            ):
                raise ValueError(f"{name} must be positive and finite")
        if self.cfl >= 1 or self.diffusion_safety >= 1:
            raise ValueError("cfl and diffusion_safety must be less than 1")
        if self.area_floor_ratio >= 1:
            raise ValueError("area_floor_ratio must be less than 1")
        if (
            isinstance(self.minimum_cells_per_segment, bool)
            or not isinstance(self.minimum_cells_per_segment, int)
            or self.minimum_cells_per_segment < 2
        ):
            raise ValueError("minimum_cells_per_segment must be an integer >= 2")
        for value, name in (
            (self.minimum_cycles, "minimum_cycles"),
            (self.maximum_cycles, "maximum_cycles"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.maximum_cycles < self.minimum_cycles:
            raise ValueError("maximum_cycles must be >= minimum_cycles")


@dataclass(frozen=True, slots=True, eq=False)
class SegmentMesh:
    segment_id: str
    x_m: np.ndarray
    dx_m: np.ndarray
    reference_area_m2: np.ndarray
    beta_pa: np.ndarray
    source_gamma_pa_s_per_m: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        x = _readonly(self.x_m, ndim=1, name="x_m")
        dx = _readonly(self.dx_m, ndim=1, name="dx_m")
        a0 = _readonly(self.reference_area_m2, ndim=1, name="reference_area_m2")
        beta = _readonly(self.beta_pa, ndim=1, name="beta_pa")
        gamma = _readonly(
            self.source_gamma_pa_s_per_m,
            ndim=1,
            name="source_gamma_pa_s_per_m",
        )
        shape = x.shape
        if any(item.shape != shape for item in (dx, a0, beta, gamma)):
            raise ValueError("segment mesh arrays must share shape")
        if np.any(dx <= 0) or np.any(a0 <= 0) or np.any(beta <= 0) or np.any(gamma < 0):
            raise ValueError("segment mesh contains non-physical coefficients")
        object.__setattr__(self, "x_m", x)
        object.__setattr__(self, "dx_m", dx)
        object.__setattr__(self, "reference_area_m2", a0)
        object.__setattr__(self, "beta_pa", beta)
        object.__setattr__(self, "source_gamma_pa_s_per_m", gamma)

    @property
    def cell_count(self) -> int:
        return int(self.x_m.size)


@dataclass(frozen=True, slots=True)
class SolverDiagnostics:
    cycles_completed: int
    periodicity_error: float
    converged: bool
    minimum_area_ratio: float
    maximum_cfl: float
    maximum_diffusion_number: float
    terminal_mass_balance_relative_error: float
    wall_viscoelasticity_mode: str = "pwdb_voigt_gamma_explicit"

    def __post_init__(self) -> None:
        if isinstance(self.cycles_completed, bool) or self.cycles_completed < 1:
            raise ValueError("cycles_completed must be positive")
        for value, name in (
            (self.periodicity_error, "periodicity_error"),
            (self.minimum_area_ratio, "minimum_area_ratio"),
            (self.maximum_cfl, "maximum_cfl"),
            (self.maximum_diffusion_number, "maximum_diffusion_number"),
            (self.terminal_mass_balance_relative_error, "terminal_mass_balance_relative_error"),
        ):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not isinstance(self.converged, bool):
            raise TypeError("converged must be boolean")
        if not isinstance(self.wall_viscoelasticity_mode, str) or not self.wall_viscoelasticity_mode:
            raise ValueError("wall_viscoelasticity_mode must be non-empty")


@dataclass(frozen=True, slots=True, eq=False)
class SegmentSolution:
    segment_id: str
    x_m: np.ndarray
    area_m2: np.ndarray
    flow_m3_per_s: np.ndarray
    pressure_pa: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        x = _readonly(self.x_m, ndim=1, name="x_m")
        area = _readonly(self.area_m2, ndim=2, name="area_m2")
        flow = _readonly(self.flow_m3_per_s, ndim=2, name="flow_m3_per_s")
        pressure = _readonly(self.pressure_pa, ndim=2, name="pressure_pa")
        if area.shape != flow.shape or area.shape != pressure.shape:
            raise ValueError("solution fields must share shape")
        if area.shape[1] != x.size:
            raise ValueError("solution spatial dimension must match x_m")
        if np.any(area <= 0):
            raise ValueError("solution area must remain positive")
        object.__setattr__(self, "x_m", x)
        object.__setattr__(self, "area_m2", area)
        object.__setattr__(self, "flow_m3_per_s", flow)
        object.__setattr__(self, "pressure_pa", pressure)

    def spatial_index(self, fraction: float) -> int:
        if not 0.0 <= float(fraction) <= 1.0:
            raise ValueError("fraction must lie in [0, 1]")
        if self.x_m.size == 1:
            return 0
        domain_start = self.x_m[0] - 0.5 * (self.x_m[1] - self.x_m[0])
        domain_end = self.x_m[-1] + 0.5 * (self.x_m[-1] - self.x_m[-2])
        target = domain_start + float(fraction) * (domain_end - domain_start)
        return int(np.argmin(np.abs(self.x_m - target)))


@dataclass(frozen=True, slots=True, eq=False)
class ForwardSolution:
    time_s: np.ndarray
    segments: tuple[SegmentSolution, ...]
    diagnostics: SolverDiagnostics

    def __post_init__(self) -> None:
        time = _readonly(self.time_s, ndim=1, name="time_s")
        if time.size < 2 or not np.all(np.diff(time) > 0):
            raise ValueError("time_s must be strictly increasing")
        if not isinstance(self.segments, tuple) or not self.segments:
            raise ValueError("segments must be a non-empty tuple")
        if any(not isinstance(item, SegmentSolution) for item in self.segments):
            raise TypeError("segments must contain SegmentSolution values")
        if any(item.area_m2.shape[0] != time.size for item in self.segments):
            raise ValueError("all segment histories must align with time_s")
        if len({item.segment_id for item in self.segments}) != len(self.segments):
            raise ValueError("segments must have unique identifiers")
        if not isinstance(self.diagnostics, SolverDiagnostics):
            raise TypeError("diagnostics must be SolverDiagnostics")
        object.__setattr__(self, "time_s", time)

    def segment(self, segment_id: str) -> SegmentSolution:
        for item in self.segments:
            if item.segment_id == segment_id:
                return item
        raise KeyError(segment_id)


__all__ = [
    "ForwardSolution",
    "SegmentMesh",
    "SegmentSolution",
    "SolverDiagnostics",
    "SolverOptions",
]
