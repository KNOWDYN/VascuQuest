"""Analytical mapping from arterial cardioacoustic modes to endothelial loads."""
from __future__ import annotations

import math
import numpy as np

from vascuquest.analysis.core import require_optional_dependency
from .arterial import arterial_mode_spectrum, womersley_parameter
from .model import EndothelialLoadSpectrum


def _field_between_pressures(
    p0: np.ndarray,
    p1: np.ndarray,
    *,
    length_m: float,
    fraction: float,
    wavenumber: np.ndarray,
    series_impedance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if length_m <= 0:
        raise ValueError("length_m must be positive")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must lie in [0, 1]")
    k = np.asarray(wavenumber, dtype=np.complex128)
    p0 = np.asarray(p0, dtype=np.complex128)
    p1 = np.asarray(p1, dtype=np.complex128)
    if p0.shape != k.shape or p1.shape != k.shape:
        raise ValueError("boundary pressure arrays must align with wavenumber")
    kl = k * length_m
    denominator = np.sin(kl)
    near = np.abs(kl) < 1e-6
    singular = (np.abs(denominator) < 1e-12) & ~near
    if np.any(singular):
        raise ValueError("cell boundary-value reconstruction is singular at an exact resonance")
    x = fraction * length_m
    pressure = np.empty(k.shape, dtype=np.complex128)
    flow = np.empty(k.shape, dtype=np.complex128)

    regular = ~near
    if np.any(regular):
        b = (p1[regular] - p0[regular] * np.cos(kl[regular])) / denominator[regular]
        pressure[regular] = (
            p0[regular] * np.cos(k[regular] * x)
            + b * np.sin(k[regular] * x)
        )
        dpdx = k[regular] * (
            -p0[regular] * np.sin(k[regular] * x)
            + b * np.cos(k[regular] * x)
        )
        flow[regular] = -dpdx / series_impedance[regular]

    if np.any(near):
        pressure[near] = p0[near] + fraction * (p1[near] - p0[near])
        dpdx = (p1[near] - p0[near]) / length_m
        flow[near] = -dpdx / series_impedance[near]
    return pressure, flow


def wall_shear_traction_from_flow(
    frequency_hz: object,
    volume_flow_m3_per_s: object,
    *,
    radius_m: float,
    density_kg_per_m3: float,
    viscosity_pa_s: float,
) -> np.ndarray:
    """Tangential traction exerted by oscillatory blood on the luminal wall.

    The sign is chosen so that the low-Womersley limit for positive volume flow
    is the familiar positive Poiseuille wall traction ``4 mu Q/(pi R^3)``.
    """

    special = require_optional_dependency("scipy.special", "cardioacoustics")
    frequency = np.asarray(frequency_hz, dtype=float)
    flow = np.asarray(volume_flow_m3_per_s, dtype=np.complex128)
    if frequency.shape != flow.shape:
        raise ValueError("frequency_hz and volume_flow_m3_per_s must align")
    if radius_m <= 0 or density_kg_per_m3 <= 0 or viscosity_pa_s <= 0:
        raise ValueError("radius, density and viscosity must be positive")
    alpha = womersley_parameter(
        frequency, radius_m, density_kg_per_m3, viscosity_pa_s
    )
    lam = ((-1.0 + 1.0j) / math.sqrt(2.0)) * alpha
    area = math.pi * radius_m * radius_m

    # Flow factor duplicated here only to retain the same small-alpha stable
    # asymptotics while avoiding an additional public dependency cycle.
    f = np.empty(lam.shape, dtype=np.complex128)
    ratio = np.empty(lam.shape, dtype=np.complex128)
    small = np.abs(lam) < 1e-3
    f[small] = -(lam[small] ** 2) / 8.0
    ratio[small] = (lam[small] ** 2) / 2.0
    if np.any(~small):
        z = lam[~small]
        j0 = special.jve(0, z)
        j1 = special.jve(1, z)
        f[~small] = 1.0 - 2.0 * j1 / (z * j0)
        ratio[~small] = z * j1 / j0
    return -viscosity_pa_s * flow * ratio / (area * f * radius_m)


def endothelial_load_in_uniform_cell(
    frequency_hz: object,
    proximal_pressure_pa: object,
    distal_pressure_pa: object,
    *,
    length_m: float,
    area_m2: float,
    beta_pa: float,
    gamma_pa_s_per_m: float,
    density_kg_per_m3: float,
    viscosity_pa_s: float,
    axial_fraction: float = 0.5,
) -> EndothelialLoadSpectrum:
    """Return pressure, tangential traction and wall motion inside one cell."""

    mode = arterial_mode_spectrum(
        frequency_hz,
        area_m2=area_m2,
        beta_pa=beta_pa,
        gamma_pa_s_per_m=gamma_pa_s_per_m,
        density_kg_per_m3=density_kg_per_m3,
        viscosity_pa_s=viscosity_pa_s,
    )
    p0 = np.asarray(proximal_pressure_pa, dtype=np.complex128)
    p1 = np.asarray(distal_pressure_pa, dtype=np.complex128)
    pressure, flow = _field_between_pressures(
        p0,
        p1,
        length_m=length_m,
        fraction=axial_fraction,
        wavenumber=mode.wavenumber_per_m,
        series_impedance=mode.series_impedance_pa_s_per_m4,
    )
    radius = math.sqrt(area_m2 / math.pi)
    traction = wall_shear_traction_from_flow(
        mode.frequency_hz,
        flow,
        radius_m=radius,
        density_kg_per_m3=density_kg_per_m3,
        viscosity_pa_s=viscosity_pa_s,
    )
    displacement = mode.area_compliance_m2_per_pa * pressure / (2.0 * math.pi * radius)
    return EndothelialLoadSpectrum(
        frequency_hz=mode.frequency_hz,
        pressure_pa=pressure,
        tangential_traction_pa=traction,
        wall_displacement_m=displacement,
        volume_flow_m3_per_s=flow,
    )


__all__ = [
    "endothelial_load_in_uniform_cell",
    "wall_shear_traction_from_flow",
]
