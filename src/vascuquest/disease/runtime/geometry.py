"""Structured disease-state arterial geometry stored inside runtime results."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _readonly_1d(values: object, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    if array.ndim != 1 or array.size < 1 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a non-empty finite one-dimensional array")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True, eq=False)
class RuntimeGeometrySegment:
    """One disease-state arterial segment with resolved solver geometry/mechanics.

    Unlike the source PWDB geometry row, a runtime disease segment may contain
    a local stenosis or aneurysm inside the source segment. Therefore the full
    solver-space axial arrays are retained instead of collapsing the disease
    back to source inlet/outlet radii.
    """

    segment_id: str
    inlet_node: int
    outlet_node: int
    length_m: float
    x_m: np.ndarray
    reference_radius_m: np.ndarray
    reference_area_m2: np.ndarray
    beta_pa: np.ndarray
    source_gamma_pa_s_per_m: np.ndarray
    peripheral_c: float
    peripheral_r: float

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        for value, name in ((self.inlet_node, "inlet_node"), (self.outlet_node, "outlet_node")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.length_m, (int, float)) or float(self.length_m) <= 0:
            raise ValueError("length_m must be positive")
        arrays = {
            "x_m": _readonly_1d(self.x_m, "x_m"),
            "reference_radius_m": _readonly_1d(self.reference_radius_m, "reference_radius_m"),
            "reference_area_m2": _readonly_1d(self.reference_area_m2, "reference_area_m2"),
            "beta_pa": _readonly_1d(self.beta_pa, "beta_pa"),
            "source_gamma_pa_s_per_m": _readonly_1d(
                self.source_gamma_pa_s_per_m, "source_gamma_pa_s_per_m"
            ),
        }
        shape = arrays["x_m"].shape
        if any(array.shape != shape for array in arrays.values()):
            raise ValueError("runtime geometry arrays must share shape")
        if np.any(np.diff(arrays["x_m"]) <= 0) and arrays["x_m"].size > 1:
            raise ValueError("x_m must be strictly increasing")
        if np.any(arrays["reference_radius_m"] <= 0):
            raise ValueError("reference_radius_m must be positive")
        if np.any(arrays["reference_area_m2"] <= 0) or np.any(arrays["beta_pa"] <= 0):
            raise ValueError("reference area and beta must be positive")
        if np.any(arrays["source_gamma_pa_s_per_m"] < 0):
            raise ValueError("source gamma must be non-negative")
        for name, array in arrays.items():
            object.__setattr__(self, name, array)
        for value, name in ((self.peripheral_c, "peripheral_c"), (self.peripheral_r, "peripheral_r")):
            if not isinstance(value, (int, float)) or not np.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")


__all__ = ["RuntimeGeometrySegment"]
