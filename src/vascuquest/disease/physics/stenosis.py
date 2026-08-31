"""Empirical focal-stenosis pressure-loss physics for Virtual Disease v1."""

from __future__ import annotations

from dataclasses import dataclass
import math

SEELEY_YOUNG_1976_DOI = "doi:10.1016/0021-9290(76)90086-5"
YOUNG_SEELEY_KT = 1.52
YOUNG_SEELEY_KU = 1.20


@dataclass(frozen=True, slots=True)
class YoungSeeleyExcessCoefficients:
    """Excess trans-stenotic loss coefficients layered on the native 1-D PDE.

    The healthy 1-D equations already contain distributed viscous friction and
    fluid inertia. Therefore Virtual Disease adds only the *excess* viscous
    contribution relative to an unstenosed region plus the empirical
    separation loss. The original Young/Seeley inertial term is not added a
    second time.
    """

    nominal_diameter_m: float
    stenosis_diameter_m: float
    lesion_length_m: float
    nominal_area_m2: float
    stenosis_area_m2: float
    kv_stenosed: float
    kv_unstenosed: float
    kt: float
    ku_reference: float
    linear_excess_pa_s_per_m3: float
    quadratic_pa_s2_per_m6: float

    def __post_init__(self) -> None:
        for value, name in (
            (self.nominal_diameter_m, "nominal_diameter_m"),
            (self.stenosis_diameter_m, "stenosis_diameter_m"),
            (self.lesion_length_m, "lesion_length_m"),
            (self.nominal_area_m2, "nominal_area_m2"),
            (self.stenosis_area_m2, "stenosis_area_m2"),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for value, name in (
            (self.kv_stenosed, "kv_stenosed"),
            (self.kv_unstenosed, "kv_unstenosed"),
            (self.kt, "kt"),
            (self.ku_reference, "ku_reference"),
            (self.linear_excess_pa_s_per_m3, "linear_excess_pa_s_per_m3"),
            (self.quadratic_pa_s2_per_m6, "quadratic_pa_s2_per_m6"),
        ):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def pressure_drop_pa(self, flow_m3_per_s: float) -> float:
        q = float(flow_m3_per_s)
        if not math.isfinite(q):
            raise ValueError("flow_m3_per_s must be finite")
        return float(
            self.linear_excess_pa_s_per_m3 * q
            + self.quadratic_pa_s2_per_m6 * q * abs(q)
        )


def young_seeley_excess_coefficients(
    *,
    nominal_diameter_m: float,
    stenosis_diameter_m: float,
    lesion_length_m: float,
    blood_density_kg_per_m3: float,
    blood_viscosity_pa_s: float,
) -> YoungSeeleyExcessCoefficients:
    """Return excess Young/Seeley coefficients in SI units.

    The underlying empirical model uses::

        Kv = 32 * (0.83*Ls + 1.64*Ds)/D0 * (A0/As)^2
        Kt = 1.52

        dP_visc = Kv * mu/(A0*D0) * Q
        dP_sep  = Kt * rho/(2*A0^2) * (A0/As - 1)^2 * Q*|Q|

    ``Kv`` at ``As=A0`` is subtracted because the native 1-D solver already
    contains the ordinary-vessel viscous term. This makes zero stenosis an
    exact no-op instead of adding artificial healthy-vessel resistance.
    """

    d0 = float(nominal_diameter_m)
    ds = float(stenosis_diameter_m)
    length = float(lesion_length_m)
    rho = float(blood_density_kg_per_m3)
    mu = float(blood_viscosity_pa_s)
    for value, name in (
        (d0, "nominal_diameter_m"),
        (ds, "stenosis_diameter_m"),
        (length, "lesion_length_m"),
        (rho, "blood_density_kg_per_m3"),
        (mu, "blood_viscosity_pa_s"),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    if ds > d0:
        raise ValueError("stenosis diameter must not exceed nominal diameter")

    a0 = math.pi * d0 * d0 / 4.0
    area_s = math.pi * ds * ds / 4.0
    area_ratio = a0 / area_s
    kv_stenosed = 32.0 * (0.83 * length + 1.64 * ds) / d0 * area_ratio**2
    kv_unstenosed = 32.0 * (0.83 * length + 1.64 * d0) / d0
    linear = max(kv_stenosed - kv_unstenosed, 0.0) * mu / (a0 * d0)
    quadratic = (
        YOUNG_SEELEY_KT
        * rho
        / (2.0 * a0 * a0)
        * (area_ratio - 1.0) ** 2
    )
    return YoungSeeleyExcessCoefficients(
        nominal_diameter_m=d0,
        stenosis_diameter_m=ds,
        lesion_length_m=length,
        nominal_area_m2=a0,
        stenosis_area_m2=area_s,
        kv_stenosed=kv_stenosed,
        kv_unstenosed=kv_unstenosed,
        kt=YOUNG_SEELEY_KT,
        ku_reference=YOUNG_SEELEY_KU,
        linear_excess_pa_s_per_m3=linear,
        quadratic_pa_s2_per_m6=quadratic,
    )


__all__ = [
    "SEELEY_YOUNG_1976_DOI",
    "YOUNG_SEELEY_KT",
    "YOUNG_SEELEY_KU",
    "YoungSeeleyExcessCoefficients",
    "young_seeley_excess_coefficients",
]
