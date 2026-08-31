"""Local pressure-loss terms for disease-aware 1-D haemodynamics.

The healthy PWDB solver remains unchanged. Disease solvers may add one or
more distributed pressure losses whose cell weights integrate to unity over
the affected region.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


def _readonly_1d(values: object, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).copy()
    if array.ndim != 1 or array.size < 1 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a non-empty finite one-dimensional array")
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True, eq=False)
class LocalizedPressureLoss:
    """One distributed excess pressure loss applied to a solver segment.

    ``weights_per_m`` is a spatial density. The disease solver verifies that
    its integral over the target mesh is one, so the coefficients represent
    the total trans-lesion pressure loss rather than a per-unit-length value.
    """

    segment_id: str
    weights_per_m: np.ndarray
    linear_resistance_pa_s_per_m3: float
    quadratic_resistance_pa_s2_per_m6: float
    inertance_pa_s2_per_m3: float = 0.0
    model_id: str = "localized_pressure_loss"
    citation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not self.segment_id.strip():
            raise ValueError("segment_id must be non-empty")
        weights = _readonly_1d(self.weights_per_m, "weights_per_m")
        if np.any(weights < 0) or not np.any(weights > 0):
            raise ValueError("weights_per_m must be non-negative with positive support")
        object.__setattr__(self, "weights_per_m", weights)
        for value, name in (
            (self.linear_resistance_pa_s_per_m3, "linear_resistance_pa_s_per_m3"),
            (self.quadratic_resistance_pa_s2_per_m6, "quadratic_resistance_pa_s2_per_m6"),
            (self.inertance_pa_s2_per_m3, "inertance_pa_s2_per_m3"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("model_id must be non-empty")
        if self.citation is not None and (
            not isinstance(self.citation, str) or not self.citation.strip()
        ):
            raise ValueError("citation must be None or a non-empty string")

    def pressure_drop_pa(self, flow_m3_per_s: float, dflow_dt_m3_per_s2: float = 0.0) -> float:
        """Return the signed total pressure drop for a lumped flow state."""

        q = float(flow_m3_per_s)
        dqdt = float(dflow_dt_m3_per_s2)
        if not math.isfinite(q) or not math.isfinite(dqdt):
            raise ValueError("flow and flow derivative must be finite")
        return float(
            self.linear_resistance_pa_s_per_m3 * q
            + self.quadratic_resistance_pa_s2_per_m6 * q * abs(q)
            + self.inertance_pa_s2_per_m3 * dqdt
        )


__all__ = ["LocalizedPressureLoss"]
