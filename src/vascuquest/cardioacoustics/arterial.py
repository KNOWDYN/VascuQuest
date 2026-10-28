"""Analytical coupled blood-wall propagation laws for cardioacoustics."""
from __future__ import annotations

import math
import numpy as np

from vascuquest.analysis.core import require_optional_dependency
from .model import ArterialModeSpectrum


def _frequency(frequency_hz: object) -> np.ndarray:
    values = np.asarray(frequency_hz, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("frequency_hz must be a finite one-dimensional array")
    if np.any(values <= 0) or np.any(np.diff(values) <= 0):
        raise ValueError("frequency_hz must be strictly increasing and positive")
    return values


def womersley_parameter(
    frequency_hz: object,
    radius_m: float,
    density_kg_per_m3: float,
    viscosity_pa_s: float,
) -> np.ndarray:
    frequency = _frequency(frequency_hz)
    if radius_m <= 0 or density_kg_per_m3 <= 0 or viscosity_pa_s <= 0:
        raise ValueError("radius, density and viscosity must be positive")
    omega = 2.0 * math.pi * frequency
    return radius_m * np.sqrt(omega * density_kg_per_m3 / viscosity_pa_s)


def womersley_factor(
    frequency_hz: object,
    radius_m: float,
    density_kg_per_m3: float,
    viscosity_pa_s: float,
) -> np.ndarray:
    """Return the exact circular-tube Womersley flow factor.

    For the ``exp(i omega t)`` convention, ``lambda = i^(3/2) alpha`` and
    ``F = 1 - 2 J1(lambda)/(lambda J0(lambda))``.  At small alpha this tends
    to ``i alpha^2 / 8`` and therefore recovers Poiseuille resistance.
    """

    special = require_optional_dependency("scipy.special", "cardioacoustics")
    alpha = womersley_parameter(
        frequency_hz, radius_m, density_kg_per_m3, viscosity_pa_s
    )
    lam = ((-1.0 + 1.0j) / math.sqrt(2.0)) * alpha
    result = np.empty(lam.shape, dtype=np.complex128)
    small = np.abs(lam) < 1e-3
    result[small] = -(lam[small] ** 2) / 8.0
    if np.any(~small):
        z = lam[~small]
        result[~small] = 1.0 - 2.0 * special.jve(1, z) / (z * special.jve(0, z))
    return result


def wall_area_compliance(
    frequency_hz: object,
    area_m2: float,
    beta_pa: float,
    gamma_pa_s_per_m: float = 0.0,
) -> np.ndarray:
    """Complex area compliance of VascuQuest's linearised Voigt wall law."""

    frequency = _frequency(frequency_hz)
    if area_m2 <= 0 or beta_pa <= 0 or gamma_pa_s_per_m < 0:
        raise ValueError("area and beta must be positive and gamma non-negative")
    omega = 2.0 * math.pi * frequency
    stiffness = beta_pa / (2.0 * area_m2) + 1j * omega * gamma_pa_s_per_m / math.sqrt(area_m2)
    return 1.0 / stiffness


def _positive_root(values: np.ndarray) -> np.ndarray:
    roots = np.sqrt(np.asarray(values, dtype=np.complex128))
    flip = (np.real(roots) < 0) | (
        np.isclose(np.real(roots), 0.0, atol=1e-15) & (np.imag(roots) < 0)
    )
    roots[flip] *= -1.0
    return roots


def arterial_mode_spectrum(
    frequency_hz: object,
    *,
    area_m2: float,
    beta_pa: float,
    gamma_pa_s_per_m: float,
    density_kg_per_m3: float,
    viscosity_pa_s: float,
    viscous_blood: bool = True,
) -> ArterialModeSpectrum:
    """Solve the local linear cardioacoustic mode analytically in frequency space.

    The formulation combines the exact Womersley relation for oscillatory flow
    in a circular tube with the linearised PWDB/Nektar elastic-Voigt wall law.
    No CFD, FSI discretisation or empirical fitted acoustic wave speed is used.
    """

    frequency = _frequency(frequency_hz)
    if area_m2 <= 0 or beta_pa <= 0 or density_kg_per_m3 <= 0 or viscosity_pa_s <= 0:
        raise ValueError("area, beta, density and viscosity must be positive")
    if gamma_pa_s_per_m < 0:
        raise ValueError("gamma_pa_s_per_m must be non-negative")

    radius = math.sqrt(area_m2 / math.pi)
    omega = 2.0 * math.pi * frequency
    compliance = wall_area_compliance(
        frequency, area_m2, beta_pa, gamma_pa_s_per_m
    )
    if viscous_blood:
        flow_factor = womersley_factor(
            frequency, radius, density_kg_per_m3, viscosity_pa_s
        )
    else:
        flow_factor = np.ones(frequency.shape, dtype=np.complex128)

    series_impedance = 1j * omega * density_kg_per_m3 / (area_m2 * flow_factor)
    shunt_admittance = 1j * omega * compliance
    propagation_constant = _positive_root(series_impedance * shunt_admittance)
    wavenumber = -1j * propagation_constant
    characteristic_impedance = _positive_root(series_impedance / shunt_admittance)
    specific_impedance = area_m2 * characteristic_impedance

    return ArterialModeSpectrum(
        frequency_hz=frequency,
        wavenumber_per_m=wavenumber,
        characteristic_impedance_pa_s_per_m3=characteristic_impedance,
        specific_impedance_pa_s_per_m=specific_impedance,
        area_compliance_m2_per_pa=compliance,
        womersley_factor=flow_factor,
        series_impedance_pa_s_per_m4=series_impedance,
    )


def reflection_coefficient(
    proximal_impedance_pa_s_per_m3: object,
    distal_impedance_pa_s_per_m3: object,
) -> np.ndarray:
    """Pressure reflection coefficient at a local impedance discontinuity."""

    z1 = np.asarray(proximal_impedance_pa_s_per_m3, dtype=np.complex128)
    z2 = np.asarray(distal_impedance_pa_s_per_m3, dtype=np.complex128)
    if z1.shape != z2.shape:
        raise ValueError("impedance arrays must share shape")
    denominator = z2 + z1
    if np.any(np.isclose(np.abs(denominator), 0.0)):
        raise ValueError("reflection coefficient is undefined for zero summed impedance")
    return (z2 - z1) / denominator


__all__ = [
    "arterial_mode_spectrum",
    "reflection_coefficient",
    "wall_area_compliance",
    "womersley_factor",
    "womersley_parameter",
]
