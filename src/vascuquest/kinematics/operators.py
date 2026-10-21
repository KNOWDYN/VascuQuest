"""Internal exact-coordinate operators for the mechanical-closure extension."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .derivatives import SpatialDerivatives, spatial_derivatives


def readonly(values: object) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    result.setflags(write=False)
    return result


def readonly_bool(values: object) -> np.ndarray:
    result = np.asarray(values, dtype=bool).copy()
    result.setflags(write=False)
    return result


def path_time(values: object, shape: tuple[int, int], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim == 0:
        result = np.full(shape, float(result), dtype=float)
    elif result.ndim == 1 and result.shape[0] == shape[0]:
        result = np.repeat(result[:, None], shape[1], axis=1)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise AdmissibilityError(f"{name} must be finite and broadcast to (path_position, time)")
    return result


def validate_time(time_s: object, samples: int) -> np.ndarray:
    t = np.asarray(time_s, dtype=float)
    if t.ndim != 1 or t.size != samples or t.size < 3:
        raise AdmissibilityError(
            "time_s must be a one-dimensional vector aligned with the field time dimension "
            "and contain at least three samples"
        )
    if not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
        raise AdmissibilityError("time_s must be finite and strictly increasing")
    return t


def time_derivative(values: object, time_s: object) -> np.ndarray:
    a = np.asarray(values, dtype=float)
    if a.ndim < 2:
        raise AdmissibilityError("time derivative requires an array with time on axis 1")
    t = validate_time(time_s, a.shape[1])
    return np.gradient(a, t, axis=1, edge_order=2)


@dataclass(frozen=True, slots=True)
class BaseCoefficients:
    """Polynomial coefficients of the exact lift in q=r/R."""

    a1: np.ndarray
    a3: np.ndarray
    c0: np.ndarray
    c2: np.ndarray
    w1: np.ndarray
    w3: np.ndarray
    radius_z: np.ndarray
    radius_zz: np.ndarray
    mean_velocity_z: np.ndarray
    mean_velocity_zz: np.ndarray
    valid_path_mask: np.ndarray


def base_coefficients(field: KinematicLift, *, minimum_points: int = 3) -> BaseCoefficients:
    z = np.asarray(field.distance_m, dtype=float)
    u = np.asarray(field.mean_velocity_m_s, dtype=float)
    radius = np.asarray(field.radius_m, dtype=float)
    groups = field.derivative_groups

    du = spatial_derivatives(u, z, groups=groups, minimum_points=minimum_points)
    dr = spatial_derivatives(radius, z, groups=groups, minimum_points=minimum_points)
    valid = np.asarray(field.valid_path_mask, dtype=bool) & du.valid_mask & dr.valid_mask

    a1 = -radius * du.first
    a3 = 0.5 * radius * du.first - u * dr.first
    c0 = 2.0 * u
    c2 = -2.0 * u
    w1 = 4.0 * u / radius - radius * du.second
    w3 = (
        0.5 * radius * du.second
        - 2.0 * dr.first * du.first
        - u * dr.second
        + 3.0 * u * dr.first**2 / radius
    )
    return BaseCoefficients(
        readonly(a1), readonly(a3), readonly(c0), readonly(c2),
        readonly(w1), readonly(w3), readonly(dr.first), readonly(dr.second),
        readonly(du.first), readonly(du.second), readonly_bool(valid),
    )


def poly_eval(coefficients: Mapping[int, np.ndarray], q: np.ndarray) -> np.ndarray:
    out = np.zeros((*next(iter(coefficients.values())).shape, q.size), dtype=float)
    q3 = q[None, None, :]
    for power, coefficient in coefficients.items():
        out += np.asarray(coefficient, dtype=float)[:, :, None] * q3**power
    return out


def poly_q(coefficients: Mapping[int, np.ndarray], q: np.ndarray, *, order: int = 1) -> np.ndarray:
    if order not in {1, 2}:
        raise ValueError("polynomial q derivative supports order 1 or 2")
    derived: dict[int, np.ndarray] = {}
    for power, coefficient in coefficients.items():
        if power < order:
            continue
        factor = power if order == 1 else power * (power - 1)
        derived[power - order] = factor * np.asarray(coefficient, dtype=float)
    if not derived:
        shape = next(iter(coefficients.values())).shape
        return np.zeros((*shape, q.size), dtype=float)
    return poly_eval(derived, q)


def coefficient_derivatives(
    coefficients: Mapping[int, np.ndarray],
    distance_m: np.ndarray,
    *,
    groups: Sequence[object] | None,
    minimum_points: int,
) -> tuple[dict[int, SpatialDerivatives], np.ndarray]:
    result: dict[int, SpatialDerivatives] = {}
    valid: np.ndarray | None = None
    for power, coefficient in coefficients.items():
        derivative = spatial_derivatives(
            coefficient, distance_m, groups=groups, minimum_points=minimum_points
        )
        result[power] = derivative
        valid = derivative.valid_mask.copy() if valid is None else (valid & derivative.valid_mask)
    assert valid is not None
    return result, valid


def poly_z_fixed_r(
    coefficients: Mapping[int, np.ndarray],
    derivatives: Mapping[int, SpatialDerivatives],
    q: np.ndarray,
    radius: np.ndarray,
    radius_z: np.ndarray,
) -> np.ndarray:
    h = radius_z / radius
    transformed = {
        power: derivatives[power].first - power * h * coefficient
        for power, coefficient in coefficients.items()
    }
    return poly_eval(transformed, q)


def poly_zz_fixed_r(
    coefficients: Mapping[int, np.ndarray],
    derivatives: Mapping[int, SpatialDerivatives],
    q: np.ndarray,
    radius: np.ndarray,
    radius_z: np.ndarray,
    radius_zz: np.ndarray,
) -> np.ndarray:
    h = radius_z / radius
    transformed = {
        power: (
            derivatives[power].second
            - 2.0 * power * h * derivatives[power].first
            - power * (radius_zz / radius) * coefficient
            + power * (power + 1.0) * h**2 * coefficient
        )
        for power, coefficient in coefficients.items()
    }
    return poly_eval(transformed, q)


def poly_t_fixed_r(
    coefficients: Mapping[int, np.ndarray],
    time_s: np.ndarray,
    q: np.ndarray,
    radius: np.ndarray,
) -> np.ndarray:
    radius_t = time_derivative(radius, time_s)
    h_t = radius_t / radius
    transformed = {
        power: time_derivative(coefficient, time_s) - power * h_t * coefficient
        for power, coefficient in coefficients.items()
    }
    return poly_eval(transformed, q)


def mechanical_valid_mask(field: KinematicLift, *masks: np.ndarray) -> np.ndarray:
    valid = np.asarray(field.valid_path_mask, dtype=bool).copy()
    for mask in masks:
        valid &= np.asarray(mask, dtype=bool)
    return valid


__all__ = [
    "BaseCoefficients", "base_coefficients", "coefficient_derivatives",
    "mechanical_valid_mask", "path_time", "poly_eval", "poly_q",
    "poly_t_fixed_r", "poly_z_fixed_r", "poly_zz_fixed_r", "readonly",
    "readonly_bool", "time_derivative", "validate_time",
]
