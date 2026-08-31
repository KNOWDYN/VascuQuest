"""Exact local propagator for Virtual Disease focal pressure losses.

Virtual Disease v1 focal stenosis uses a distributed Young--Seeley excess
pressure drop

    dP = L Q + K Q |Q|

with zero added inertance.  During a source-only substep the conserved area is
constant, so the local momentum equation is the separable scalar ODE

    dQ/dt = -a Q - b Q |Q|,

where ``a = A L / rho`` and ``b = A K / rho``.  This module integrates that
ODE analytically.  The source update is therefore unconditionally dissipative
and does not impose an explicit disease-loss time-step restriction.
"""

from __future__ import annotations

import math

import numpy as np


def exact_local_pressure_loss_flow(
    flow_m3_per_s: np.ndarray | float,
    area_m2: np.ndarray | float,
    linear_density_pa_s_per_m4: np.ndarray | float,
    quadratic_density_pa_s2_per_m7: np.ndarray | float,
    *,
    density_kg_per_m3: float,
    dt_s: float,
    inertance_density_pa_s2_per_m4: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Return the exact source-only flow after ``dt_s``.

    The ``*_density`` coefficients are the distributed per-length coefficients
    used internally by the disease finite-volume solver after multiplying the
    total lesion coefficient by ``weights_per_m``.

    Non-zero excess inertance is deliberately rejected.  The deployed vd1
    carotid/iliac Young--Seeley transformations set excess inertance to zero;
    a future non-zero-inertance disease model requires a separately qualified
    time-integration formulation because inertance changes the momentum mass
    factor of the complete semidiscrete RHS.
    """

    rho = float(density_kg_per_m3)
    dt = float(dt_s)
    if not math.isfinite(rho) or rho <= 0.0:
        raise ValueError("density_kg_per_m3 must be positive and finite")
    if not math.isfinite(dt) or dt < 0.0:
        raise ValueError("dt_s must be finite and non-negative")

    q = np.asarray(flow_m3_per_s, dtype=float)
    area = np.asarray(area_m2, dtype=float)
    linear = np.asarray(linear_density_pa_s_per_m4, dtype=float)
    quadratic = np.asarray(quadratic_density_pa_s2_per_m7, dtype=float)
    inertance = np.asarray(inertance_density_pa_s2_per_m4, dtype=float)
    q, area, linear, quadratic, inertance = np.broadcast_arrays(
        q, area, linear, quadratic, inertance
    )
    if not all(np.all(np.isfinite(item)) for item in (q, area, linear, quadratic, inertance)):
        raise ValueError("exact pressure-loss inputs must be finite")
    if np.any(area <= 0.0):
        raise ValueError("area_m2 must remain positive")
    if np.any(linear < 0.0) or np.any(quadratic < 0.0) or np.any(inertance < 0.0):
        raise ValueError("pressure-loss coefficients must be non-negative")
    if np.any(inertance != 0.0):
        raise ValueError(
            "exact focal-loss propagation supports only zero excess inertance"
        )
    if dt == 0.0:
        return np.asarray(q, dtype=float).copy()

    a = area / rho * linear
    b = area / rho * quadratic
    magnitude = np.abs(q)
    sign = np.sign(q)

    adt = a * dt
    decay = np.exp(-adt)
    one_minus_decay = -np.expm1(-adt)
    # Use the analytic a -> 0 limit rather than b/a near zero.
    use_linear_formula = a > 1e-30
    denominator_linear = 1.0 + np.where(
        use_linear_formula,
        (b / np.where(use_linear_formula, a, 1.0)) * magnitude * one_minus_decay,
        0.0,
    )
    magnitude_linear = magnitude * decay / denominator_linear
    magnitude_quadratic = magnitude / (1.0 + b * magnitude * dt)
    updated = np.where(use_linear_formula, magnitude_linear, magnitude_quadratic)
    result = sign * updated
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("exact focal-loss propagator produced non-finite flow")
    return np.asarray(result, dtype=float)


__all__ = ["exact_local_pressure_loss_flow"]
