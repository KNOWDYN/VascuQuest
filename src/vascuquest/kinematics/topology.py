"""Strain-rotation topology for exact VascuQuest axisymmetric lifts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core import KinematicLift
from .operators import base_coefficients, readonly, readonly_bool


TOPOLOGY_METHOD_ID = "vascuquest:kinematics:mechanical-closure-topology-v1"


@dataclass(frozen=True, slots=True)
class TopologyField:
    """Velocity-gradient, strain/rotation and Q fields in the (r,theta,z) basis."""

    grad_rr_s_1: np.ndarray
    grad_tt_s_1: np.ndarray
    grad_rz_s_1: np.ndarray
    grad_zr_s_1: np.ndarray
    grad_zz_s_1: np.ndarray
    strain_rr_s_1: np.ndarray
    strain_tt_s_1: np.ndarray
    strain_zz_s_1: np.ndarray
    strain_rz_s_1: np.ndarray
    rotation_rz_s_1: np.ndarray
    q_invariant_s_2: np.ndarray
    valid_path_mask: np.ndarray
    method_id: str = TOPOLOGY_METHOD_ID
    evidence: str = "DERIVED"


def strain_rotation_topology(field: KinematicLift) -> TopologyField:
    """Evaluate the exact cylindrical velocity-gradient topology of a lift."""

    q = np.asarray(field.radial_fraction, dtype=float)
    q3 = q[None, None, :]
    radius = np.asarray(field.radius_m, dtype=float)
    coefficients = base_coefficients(field, minimum_points=3)

    a1 = np.asarray(coefficients.a1)
    a3 = np.asarray(coefficients.a3)
    u = np.asarray(field.mean_velocity_m_s)
    omega = np.asarray(field.azimuthal_vorticity_s_1)

    grad_rr = (a1[:, :, None] + 3.0 * a3[:, :, None] * q3**2) / radius[:, :, None]
    grad_tt = (a1[:, :, None] + a3[:, :, None] * q3**2) / radius[:, :, None]
    grad_zr = -4.0 * u[:, :, None] * q3 / radius[:, :, None]
    grad_rz = omega + grad_zr
    grad_zz = -(grad_rr + grad_tt)

    strain_rr = grad_rr
    strain_tt = grad_tt
    strain_zz = grad_zz
    strain_rz = 0.5 * (grad_rz + grad_zr)
    rotation_rz = 0.5 * (grad_rz - grad_zr)

    s_contract = strain_rr**2 + strain_tt**2 + strain_zz**2 + 2.0 * strain_rz**2
    omega_contract = 2.0 * rotation_rz**2
    q_invariant = 0.5 * (omega_contract - s_contract)

    valid = np.asarray(coefficients.valid_path_mask, dtype=bool)
    return TopologyField(
        grad_rr_s_1=readonly(grad_rr), grad_tt_s_1=readonly(grad_tt),
        grad_rz_s_1=readonly(grad_rz), grad_zr_s_1=readonly(grad_zr),
        grad_zz_s_1=readonly(grad_zz), strain_rr_s_1=readonly(strain_rr),
        strain_tt_s_1=readonly(strain_tt), strain_zz_s_1=readonly(strain_zz),
        strain_rz_s_1=readonly(strain_rz), rotation_rz_s_1=readonly(rotation_rz),
        q_invariant_s_2=readonly(q_invariant), valid_path_mask=readonly_bool(valid),
    )


__all__ = ["TOPOLOGY_METHOD_ID", "TopologyField", "strain_rotation_topology"]
