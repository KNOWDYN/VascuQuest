"""Dimensionless mechanical-state assembly for closure analysis."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .crocco import CroccoField, crocco_decomposition
from .lamb import LambField, lamb_hydrodynamic_charge
from .loading import LambLoadField, radial_shell_lamb_load
from .operators import mechanical_valid_mask, readonly, readonly_bool
from .stress import WallTractionField, wall_traction
from .topology import TopologyField, strain_rotation_topology


MECHANICAL_STATE_METHOD_ID = "vascuquest:kinematics:mechanical-closure-state-v1"


@dataclass(frozen=True, slots=True)
class MechanicalState:
    """Primary dimensionless mechanical state and its physical supporting fields."""

    field: KinematicLift
    topology: TopologyField
    lamb: LambField
    wall_traction: WallTractionField
    crocco: CroccoField
    lamb_load: LambLoadField
    q_star: np.ndarray
    q_h_star: np.ndarray
    c_u_r_star: np.ndarray
    c_u_z_star: np.ndarray
    c_h_r_star: np.ndarray
    c_h_z_star: np.ndarray
    c_d_r_star: np.ndarray
    c_d_z_star: np.ndarray
    velocity_scale_m_s: float
    length_scale_m: float
    acceleration_scale_m_s2: float
    source_scale_s_2: float
    valid_path_mask: np.ndarray
    method_id: str = MECHANICAL_STATE_METHOD_ID
    evidence: str = "DERIVED"

    def metadata(self) -> dict[str, object]:
        return {
            "kind":"vascuquest.kinematics.mechanical_closure_state",
            "method_id":self.method_id,
            "evidence":self.evidence,
            "velocity_scale_m_s":self.velocity_scale_m_s,
            "length_scale_m":self.length_scale_m,
            "acceleration_scale_m_s2":self.acceleration_scale_m_s2,
            "source_scale_s_2":self.source_scale_s_2,
            "valid_path_points":int(np.count_nonzero(self.valid_path_mask)),
            "invalid_path_points":int(self.valid_path_mask.size-np.count_nonzero(self.valid_path_mask)),
            "primary_coordinates":["Q_star","q_H_star","C_U_star","C_H_star","C_D_star"],
        }


def mechanical_state(
    field: KinematicLift,
    pressure_pa: object,
    time_s: object,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    *,
    velocity_scale_m_s: float,
    length_scale_m: float,
    potential_head_m2_s2: object | None = None,
    activity_threshold_fraction: float = 0.0,
    thickness_fraction: float = 0.10,
) -> MechanicalState:
    """Assemble the primary dimensionless mechanical state from an exact lift."""

    uc=float(velocity_scale_m_s); lc=float(length_scale_m); eta=float(activity_threshold_fraction)
    if not np.isfinite(uc) or uc <= 0:
        raise AdmissibilityError("velocity_scale_m_s must be a finite positive scalar")
    if not np.isfinite(lc) or lc <= 0:
        raise AdmissibilityError("length_scale_m must be a finite positive scalar")
    if not np.isfinite(eta) or eta < 0:
        raise AdmissibilityError("activity_threshold_fraction must be finite and non-negative")
    a_scale=uc**2/lc; q_scale=uc**2/lc**2

    topology=strain_rotation_topology(field)
    lamb=lamb_hydrodynamic_charge(field,topology=topology)
    traction=wall_traction(field,dynamic_viscosity_pa_s,topology=topology)
    crocco=crocco_decomposition(
        field,pressure_pa,time_s,density_kg_m3,dynamic_viscosity_pa_s,
        potential_head_m2_s2=potential_head_m2_s2,
        activity_threshold_m_s2=eta*a_scale,lamb=lamb,
    )
    load=radial_shell_lamb_load(field,density_kg_m3,thickness_fraction=thickness_fraction,lamb=lamb)

    valid=mechanical_valid_mask(
        field,topology.valid_path_mask,lamb.valid_path_mask,traction.valid_path_mask,
        crocco.valid_path_mask,load.valid_path_mask,
    )
    q_star=np.asarray(topology.q_invariant_s_2,dtype=float)/q_scale
    q_h_star=np.asarray(lamb.q_h_divergence_s_2,dtype=float)/q_scale
    cu_r=np.asarray(crocco.unsteady_r_m_s2,dtype=float)/a_scale
    cu_z=np.asarray(crocco.unsteady_z_m_s2,dtype=float)/a_scale
    ch_r=np.asarray(crocco.head_gradient_r_m_s2,dtype=float)/a_scale
    ch_z=np.asarray(crocco.head_gradient_z_m_s2,dtype=float)/a_scale
    cd_r=np.asarray(crocco.viscous_r_m_s2,dtype=float)/a_scale
    cd_z=np.asarray(crocco.viscous_z_m_s2,dtype=float)/a_scale
    for array in (q_star,q_h_star,cu_r,cu_z,ch_r,ch_z,cd_r,cd_z):
        array[~valid,...]=np.nan

    return MechanicalState(
        field=field,topology=topology,lamb=lamb,wall_traction=traction,crocco=crocco,lamb_load=load,
        q_star=readonly(q_star),q_h_star=readonly(q_h_star),c_u_r_star=readonly(cu_r),c_u_z_star=readonly(cu_z),
        c_h_r_star=readonly(ch_r),c_h_z_star=readonly(ch_z),c_d_r_star=readonly(cd_r),c_d_z_star=readonly(cd_z),
        velocity_scale_m_s=uc,length_scale_m=lc,acceleration_scale_m_s2=a_scale,source_scale_s_2=q_scale,
        valid_path_mask=readonly_bool(valid),
    )


__all__=["MECHANICAL_STATE_METHOD_ID","MechanicalState","mechanical_state"]
