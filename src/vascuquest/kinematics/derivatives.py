"""Qualified spatial differentiation for path-resolved kinematic reconstruction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from vascuquest.errors import AdmissibilityError


@dataclass(frozen=True, slots=True)
class DerivativeQuality:
    """Deterministic diagnostics for pathwise numerical differentiation."""

    point_count: int
    run_count: int
    minimum_run_points: int
    minimum_spacing_m: float
    maximum_spacing_m: float
    maximum_spacing_ratio: float
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "point_count": self.point_count,
            "run_count": self.run_count,
            "minimum_run_points": self.minimum_run_points,
            "minimum_spacing_m": self.minimum_spacing_m,
            "maximum_spacing_m": self.maximum_spacing_m,
            "maximum_spacing_ratio": self.maximum_spacing_ratio,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class SpatialDerivatives:
    """First and second derivatives along the physical path coordinate."""

    first: np.ndarray
    second: np.ndarray
    quality: DerivativeQuality


def _readonly(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    result.setflags(write=False)
    return result


def _runs(groups: Sequence[object] | None, n: int) -> list[tuple[int, int]]:
    if groups is None:
        return [(0, n)]
    if len(groups) != n:
        raise AdmissibilityError("derivative groups must align one-to-one with path positions")
    runs: list[tuple[int, int]] = []
    start = 0
    for index in range(1, n):
        if groups[index] != groups[index - 1]:
            runs.append((start, index))
            start = index
    runs.append((start, n))
    return runs


def spatial_derivatives(
    values: object,
    distance_m: object,
    *,
    groups: Sequence[object] | None = None,
) -> SpatialDerivatives:
    """Differentiate an array along axis 0 without interpolation or smoothing.

    ``distance_m`` may be nonuniform. When ``groups`` is supplied, derivatives
    are evaluated independently on each contiguous group and never cross a
    declared anatomical boundary.
    """

    z = np.asarray(distance_m, dtype=float)
    a = np.asarray(values, dtype=float)
    if z.ndim != 1 or z.size < 3 or not np.all(np.isfinite(z)):
        raise AdmissibilityError("path distance must be a finite one-dimensional vector with at least three points")
    if np.any(np.diff(z) <= 0):
        raise AdmissibilityError("path distance must be strictly increasing")
    if a.ndim < 1 or a.shape[0] != z.size or not np.all(np.isfinite(a)):
        raise AdmissibilityError("values must be finite and have path position on axis 0")

    runs = _runs(groups, z.size)
    first = np.empty_like(a, dtype=float)
    second = np.empty_like(a, dtype=float)
    warnings: list[str] = []
    minimum_run_points = z.size
    spacing_ratios: list[float] = []

    for start, stop in runs:
        count = stop - start
        minimum_run_points = min(minimum_run_points, count)
        if count < 3:
            raise AdmissibilityError(
                "at least three stored path positions are required inside every differentiation run"
            )
        local_z = z[start:stop]
        dz = np.diff(local_z)
        ratio = float(np.max(dz) / np.min(dz))
        spacing_ratios.append(ratio)
        if count < 5:
            warnings.append(
                f"differentiation run [{start}:{stop}] has only {count} points; second derivatives are edge-dominated"
            )
        if ratio > 4.0:
            warnings.append(
                f"differentiation run [{start}:{stop}] has a spacing ratio of {ratio:.3g}"
            )
        local = a[start:stop]
        d1 = np.gradient(local, local_z, axis=0, edge_order=2)
        d2 = np.gradient(d1, local_z, axis=0, edge_order=2)
        first[start:stop] = d1
        second[start:stop] = d2

    dz_all = np.diff(z)
    quality = DerivativeQuality(
        point_count=int(z.size),
        run_count=len(runs),
        minimum_run_points=int(minimum_run_points),
        minimum_spacing_m=float(np.min(dz_all)),
        maximum_spacing_m=float(np.max(dz_all)),
        maximum_spacing_ratio=max(spacing_ratios, default=1.0),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    return SpatialDerivatives(_readonly(first), _readonly(second), quality)


__all__ = ["DerivativeQuality", "SpatialDerivatives", "spatial_derivatives"]
