"""Generalized Crocco--Vazsonyi decomposition for exact VascuQuest kinematic lifts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .derivatives import spatial_derivatives
from .lamb import LambField, lamb_hydrodynamic_charge
from .operators import (
    base_coefficients,
    coefficient_derivatives,
    mechanical_valid_mask,
    path_time,
    poly_q,
    poly_t_fixed_r,
    poly_z_fixed_r,
    poly_zz_fixed_r,
    readonly,
    readonly_bool,
    validate_time,
)


CROCCO_METHOD_ID = "vascuquest:kinematics:mechanical-closure-crocco-v1"


@dataclass(frozen=True, slots=True)
class CroccoField:
    """Independent generalized Crocco decomposition in the (r,z) plane."""

    unsteady_r_m_s2: np.ndarray
    unsteady_z_m_s2: np.ndarray
    head_gradient_r_m_s2: np.ndarray
    head_gradient_z_m_s2: np.ndarray
    viscous_r_m_s2: np.ndarray
    viscous_z_m_s2: np.ndarray
    residual_r_m_s2: np.ndarray
    residual_z_m_s2: np.ndarray
    normalized_residual: np.ndarray
    dominance_unsteady: np.ndarray
    dominance_head: np.ndarray
    dominance_viscous: np.ndarray
    cancellation_index: np.ndarray
    lamb_unsteady_balance: np.ndarray
    lamb_unsteady_alignment: np.ndarray
    valid_path_mask: np.ndarray
    method_id: str = CROCCO_METHOD_ID
    evidence: str = "DERIVED"


def _kinetic_coefficients(base):
    a = np.asarray(base.a1); b = np.asarray(base.a3)
    c = np.asarray(base.c0); d = np.asarray(base.c2)
    return {0: 0.5*c**2, 2: 0.5*a**2+c*d, 4: a*b+0.5*d**2, 6: 0.5*b**2}


def _norm(r: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.sqrt(r**2 + z**2)


def crocco_decomposition(
    field: KinematicLift,
    pressure_pa: object,
    time_s: object,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    *,
    potential_head_m2_s2: object | None = None,
    activity_threshold_m_s2: float = 0.0,
    lamb: LambField | None = None,
) -> CroccoField:
    """Evaluate ell=C_U+C_H+C_D without residual construction of any term.

    Pressure and optional conservative potential are cross-section-uniform
    path/time fields. Thus p(r,z,t)=P(z,t) is an explicit one-dimensional
    pressure-lift axiom, never inferred from the Crocco residual.
    """

    rho = float(density_kg_m3); mu = float(dynamic_viscosity_pa_s)
    threshold = float(activity_threshold_m_s2)
    if not np.isfinite(rho) or rho <= 0:
        raise AdmissibilityError("density_kg_m3 must be a finite positive scalar")
    if not np.isfinite(mu) or mu <= 0:
        raise AdmissibilityError("dynamic_viscosity_pa_s must be a finite positive scalar")
    if not np.isfinite(threshold) or threshold < 0:
        raise AdmissibilityError("activity_threshold_m_s2 must be finite and non-negative")

    z = np.asarray(field.distance_m, dtype=float)
    q = np.asarray(field.radial_fraction, dtype=float)
    q3 = q[None, None, :]
    radius = np.asarray(field.radius_m, dtype=float)
    shape = np.asarray(field.mean_velocity_m_s).shape
    groups = field.derivative_groups
    t = validate_time(time_s, shape[1])
    pressure = path_time(pressure_pa, shape, "pressure_pa")
    potential = np.zeros(shape, dtype=float) if potential_head_m2_s2 is None else path_time(
        potential_head_m2_s2, shape, "potential_head_m2_s2"
    )

    base = base_coefficients(field, minimum_points=4)
    ur_coeffs = {1: np.asarray(base.a1), 3: np.asarray(base.a3)}
    uz_coeffs = {0: np.asarray(base.c0), 2: np.asarray(base.c2)}
    cu_r = poly_t_fixed_r(ur_coeffs, t, q, radius)
    cu_z = poly_t_fixed_r(uz_coeffs, t, q, radius)

    k_coeffs = _kinetic_coefficients(base)
    k_derivatives, k_valid = coefficient_derivatives(k_coeffs, z, groups=groups, minimum_points=4)
    k_r = poly_q(k_coeffs, q, order=1) / radius[:, :, None]
    k_z = poly_z_fixed_r(k_coeffs, k_derivatives, q, radius, np.asarray(base.radius_z))
    pressure_z = spatial_derivatives(pressure, z, groups=groups, minimum_points=4)
    potential_z = spatial_derivatives(potential, z, groups=groups, minimum_points=4)
    ch_r = k_r
    ch_z = pressure_z.first[:, :, None] / rho + k_z + potential_z.first[:, :, None]

    ur_derivatives, ur_valid = coefficient_derivatives(ur_coeffs, z, groups=groups, minimum_points=4)
    uz_derivatives, uz_valid = coefficient_derivatives(uz_coeffs, z, groups=groups, minimum_points=4)
    ur_zz = poly_zz_fixed_r(
        ur_coeffs, ur_derivatives, q, radius, np.asarray(base.radius_z), np.asarray(base.radius_zz)
    )
    uz_zz = poly_zz_fixed_r(
        uz_coeffs, uz_derivatives, q, radius, np.asarray(base.radius_z), np.asarray(base.radius_zz)
    )
    lap_ur = 8.0*np.asarray(base.a3)[:, :, None]*q3/radius[:, :, None]**2 + ur_zz
    lap_uz = 4.0*np.asarray(base.c2)[:, :, None]/radius[:, :, None]**2 + uz_zz
    nu = mu/rho
    cd_r = -nu*lap_ur
    cd_z = -nu*lap_uz

    if lamb is None:
        lamb = lamb_hydrodynamic_charge(field)
    ell_r = np.asarray(lamb.lamb_r_m_s2, dtype=float)
    ell_z = np.asarray(lamb.lamb_z_m_s2, dtype=float)
    residual_r = ell_r-cu_r-ch_r-cd_r
    residual_z = ell_z-cu_z-ch_z-cd_z

    ell_mag = _norm(ell_r, ell_z); cu_mag = _norm(cu_r, cu_z)
    ch_mag = _norm(ch_r, ch_z); cd_mag = _norm(cd_r, cd_z)
    residual_mag = _norm(residual_r, residual_z)
    component_sum = cu_mag+ch_mag+cd_mag
    residual_denominator = ell_mag+component_sum

    valid = mechanical_valid_mask(
        field, np.asarray(base.valid_path_mask), np.asarray(lamb.valid_path_mask), k_valid,
        pressure_z.valid_mask, potential_z.valid_mask, ur_valid, uz_valid,
    )
    normalized = np.full_like(residual_mag, np.nan)
    mask = (residual_denominator > 0) & valid[:, None, None]
    normalized[mask] = residual_mag[mask]/residual_denominator[mask]

    active = (component_sum > threshold) & valid[:, None, None]
    du = np.full_like(component_sum, np.nan); dh = np.full_like(component_sum, np.nan)
    dd = np.full_like(component_sum, np.nan); chi = np.full_like(component_sum, np.nan)
    du[active] = cu_mag[active]/component_sum[active]
    dh[active] = ch_mag[active]/component_sum[active]
    dd[active] = cd_mag[active]/component_sum[active]
    chi[active] = 1.0-ell_mag[active]/component_sum[active]

    lu_den = ell_mag+cu_mag
    blu = np.full_like(lu_den, np.nan)
    lu_active = (lu_den > threshold) & valid[:, None, None]
    blu[lu_active] = (ell_mag[lu_active]-cu_mag[lu_active])/lu_den[lu_active]
    alu = np.full_like(lu_den, np.nan)
    directional = (ell_mag > threshold) & (cu_mag > threshold) & valid[:, None, None]
    dot = ell_r*cu_r+ell_z*cu_z
    alu[directional] = dot[directional]/(ell_mag[directional]*cu_mag[directional])

    for array in (cu_r,cu_z,ch_r,ch_z,cd_r,cd_z,residual_r,residual_z,normalized,du,dh,dd,chi,blu,alu):
        array[~valid, ...] = np.nan

    return CroccoField(
        unsteady_r_m_s2=readonly(cu_r), unsteady_z_m_s2=readonly(cu_z),
        head_gradient_r_m_s2=readonly(ch_r), head_gradient_z_m_s2=readonly(ch_z),
        viscous_r_m_s2=readonly(cd_r), viscous_z_m_s2=readonly(cd_z),
        residual_r_m_s2=readonly(residual_r), residual_z_m_s2=readonly(residual_z),
        normalized_residual=readonly(normalized), dominance_unsteady=readonly(du),
        dominance_head=readonly(dh), dominance_viscous=readonly(dd),
        cancellation_index=readonly(chi), lamb_unsteady_balance=readonly(blu),
        lamb_unsteady_alignment=readonly(alu), valid_path_mask=readonly_bool(valid),
    )


__all__ = ["CROCCO_METHOD_ID", "CroccoField", "crocco_decomposition"]
