"""Newtonian stress and complete tangential wall traction for kinematic lifts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .operators import base_coefficients, readonly, readonly_bool
from .topology import TopologyField, strain_rotation_topology


WALL_TRACTION_METHOD_ID = "vascuquest:kinematics:mechanical-closure-wall-traction-v1"


@dataclass(frozen=True, slots=True)
class WallTractionField:
    """Tangential Newtonian traction on the moving/sloped axisymmetric wall."""

    tangential_scalar_pa: np.ndarray
    radial_component_pa: np.ndarray
    axial_component_pa: np.ndarray
    magnitude_pa: np.ndarray
    wall_normal_r: np.ndarray
    wall_normal_z: np.ndarray
    wall_tangent_r: np.ndarray
    wall_tangent_z: np.ndarray
    valid_path_mask: np.ndarray
    method_id: str = WALL_TRACTION_METHOD_ID
    evidence: str = "DERIVED"


def wall_traction(
    field: KinematicLift,
    dynamic_viscosity_pa_s: float,
    *,
    topology: TopologyField | None = None,
) -> WallTractionField:
    """Evaluate the full tangential traction [(I-nn) tau n]_wall."""

    mu = float(dynamic_viscosity_pa_s)
    if not np.isfinite(mu) or mu <= 0:
        raise AdmissibilityError("dynamic_viscosity_pa_s must be a finite positive scalar")
    if topology is None:
        topology = strain_rotation_topology(field)

    base = base_coefficients(field, minimum_points=3)
    rz = np.asarray(base.radius_z, dtype=float)
    slope_scale = np.sqrt(1.0 + rz**2)
    n_r = -1.0 / slope_scale
    n_z = rz / slope_scale
    t_r = rz / slope_scale
    t_z = 1.0 / slope_scale

    s_rr = np.asarray(topology.strain_rr_s_1)[:, :, -1]
    s_zz = np.asarray(topology.strain_zz_s_1)[:, :, -1]
    s_rz = np.asarray(topology.strain_rz_s_1)[:, :, -1]
    tau_rr = 2.0 * mu * s_rr
    tau_zz = 2.0 * mu * s_zz
    tau_rz = 2.0 * mu * s_rz

    traction_r = tau_rr * n_r + tau_rz * n_z
    traction_z = tau_rz * n_r + tau_zz * n_z
    tangential = t_r * traction_r + t_z * traction_z
    wall_tau_r = tangential * t_r
    wall_tau_z = tangential * t_z
    magnitude = np.abs(tangential)

    valid = np.asarray(field.valid_path_mask, dtype=bool) & np.asarray(topology.valid_path_mask, dtype=bool)
    for array in (tangential, wall_tau_r, wall_tau_z, magnitude, n_r, n_z, t_r, t_z):
        array[~valid, ...] = np.nan

    return WallTractionField(
        tangential_scalar_pa=readonly(tangential), radial_component_pa=readonly(wall_tau_r),
        axial_component_pa=readonly(wall_tau_z), magnitude_pa=readonly(magnitude),
        wall_normal_r=readonly(n_r), wall_normal_z=readonly(n_z),
        wall_tangent_r=readonly(t_r), wall_tangent_z=readonly(t_z),
        valid_path_mask=readonly_bool(valid),
    )


__all__ = ["WALL_TRACTION_METHOD_ID", "WallTractionField", "wall_traction"]
