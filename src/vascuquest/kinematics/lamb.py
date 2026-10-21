"""Lamb-vector and hydrodynamic-charge diagnostics for VascuQuest kinematic lifts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core import KinematicLift
from .operators import (
    base_coefficients,
    coefficient_derivatives,
    mechanical_valid_mask,
    poly_eval,
    poly_z_fixed_r,
    poly_zz_fixed_r,
    readonly,
    readonly_bool,
)
from .topology import TopologyField, strain_rotation_topology


LAMB_METHOD_ID = "vascuquest:kinematics:mechanical-closure-lamb-v1"


@dataclass(frozen=True, slots=True)
class LambField:
    """Kinetic energy, Lamb vector and independently evaluated hydrodynamic charge."""

    kinetic_energy_m2_s2: np.ndarray
    lamb_r_m_s2: np.ndarray
    lamb_z_m_s2: np.ndarray
    conventional_lamb_r_m_s2: np.ndarray
    conventional_lamb_z_m_s2: np.ndarray
    q_h_divergence_s_2: np.ndarray
    q_h_identity_s_2: np.ndarray
    laplacian_kinetic_energy_s_2: np.ndarray
    charge_identity_residual_s_2: np.ndarray
    valid_path_mask: np.ndarray
    method_id: str = LAMB_METHOD_ID
    evidence: str = "DERIVED"


def _kinetic_coefficients(field: KinematicLift):
    base = base_coefficients(field, minimum_points=4)
    a = np.asarray(base.a1)
    b = np.asarray(base.a3)
    c = np.asarray(base.c0)
    d = np.asarray(base.c2)
    return base, {
        0: 0.5 * c**2,
        2: 0.5 * a**2 + c * d,
        4: a * b + 0.5 * d**2,
        6: 0.5 * b**2,
    }


def lamb_hydrodynamic_charge(
    field: KinematicLift,
    *,
    topology: TopologyField | None = None,
) -> LambField:
    """Evaluate ell=u×omega and q_H by two independent exact-coordinate routes."""

    if topology is None:
        topology = strain_rotation_topology(field)

    q = np.asarray(field.radial_fraction, dtype=float)
    q3 = q[None, None, :]
    radius = np.asarray(field.radius_m, dtype=float)
    z = np.asarray(field.distance_m, dtype=float)
    groups = field.derivative_groups
    ur = np.asarray(field.radial_velocity_m_s, dtype=float)
    uz = np.asarray(field.axial_velocity_m_s, dtype=float)
    omega = np.asarray(field.azimuthal_vorticity_s_1, dtype=float)

    lamb_r = -uz * omega
    lamb_z = ur * omega
    Lr = -lamb_r
    Lz = -lamb_z

    base, k_coeffs = _kinetic_coefficients(field)
    k_derivatives, k_valid = coefficient_derivatives(
        k_coeffs, z, groups=groups, minimum_points=4
    )
    kinetic = poly_eval(k_coeffs, q)

    radial_lap = np.zeros_like(kinetic)
    for power, coefficient in k_coeffs.items():
        if power == 0:
            continue
        radial_lap += (
            power**2 * coefficient[:, :, None] * q3 ** (power - 2)
            / radius[:, :, None] ** 2
        )
    axial_lap = poly_zz_fixed_r(
        k_coeffs, k_derivatives, q, radius,
        np.asarray(base.radius_z), np.asarray(base.radius_zz),
    )
    lap_k = radial_lap + axial_lap

    c = np.asarray(base.c0)
    d = np.asarray(base.c2)
    w1 = np.asarray(base.w1)
    w3 = np.asarray(base.w3)
    lr_coeffs = {1: c * w1, 3: c * w3 + d * w1, 5: d * w3}
    radial_div_L = (
        2.0 * lr_coeffs[1][:, :, None]
        + 4.0 * lr_coeffs[3][:, :, None] * q3**2
        + 6.0 * lr_coeffs[5][:, :, None] * q3**4
    ) / radius[:, :, None]

    a = np.asarray(base.a1)
    b = np.asarray(base.a3)
    lz_coeffs = {
        2: -a * w1,
        4: -(a * w3 + b * w1),
        6: -b * w3,
    }
    lz_derivatives, lz_valid = coefficient_derivatives(
        lz_coeffs, z, groups=groups, minimum_points=4
    )
    axial_div_L = poly_z_fixed_r(
        lz_coeffs, lz_derivatives, q, radius, np.asarray(base.radius_z)
    )
    q_h_div = radial_div_L + axial_div_L

    q_invariant = np.asarray(topology.q_invariant_s_2, dtype=float)
    q_h_identity = -2.0 * q_invariant - lap_k
    residual = q_h_div + 2.0 * q_invariant + lap_k

    valid = mechanical_valid_mask(
        field, np.asarray(base.valid_path_mask), np.asarray(topology.valid_path_mask),
        k_valid, lz_valid,
    )
    for array in (kinetic, lamb_r, lamb_z, Lr, Lz, q_h_div, q_h_identity, lap_k, residual):
        array[~valid, ...] = np.nan

    return LambField(
        kinetic_energy_m2_s2=readonly(kinetic), lamb_r_m_s2=readonly(lamb_r),
        lamb_z_m_s2=readonly(lamb_z), conventional_lamb_r_m_s2=readonly(Lr),
        conventional_lamb_z_m_s2=readonly(Lz), q_h_divergence_s_2=readonly(q_h_div),
        q_h_identity_s_2=readonly(q_h_identity),
        laplacian_kinetic_energy_s_2=readonly(lap_k),
        charge_identity_residual_s_2=readonly(residual),
        valid_path_mask=readonly_bool(valid),
    )


__all__ = ["LAMB_METHOD_ID", "LambField", "lamb_hydrodynamic_charge"]
