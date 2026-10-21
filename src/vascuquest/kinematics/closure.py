"""Mechanical-closure distances and hydrodynamic-degeneracy classification."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .state import MechanicalState


CLOSURE_METHOD_ID = "vascuquest:kinematics:mechanical-closure-distance-v1"


@dataclass(frozen=True, slots=True)
class ClosureComparison:
    shear_distance: float
    mechanical_distance: float
    shear_equivalent: bool | None
    mechanically_equivalent: bool | None
    hydrodynamic_degeneracy: bool | None
    weights: tuple[float,float,float,float,float]
    method_id: str = CLOSURE_METHOD_ID


def _common_shape(a: MechanicalState,b: MechanicalState)->tuple[int,int,int]:
    shape_a=np.asarray(a.q_star).shape; shape_b=np.asarray(b.q_star).shape
    if shape_a != shape_b:
        raise AdmissibilityError("mechanical states must have identical mapped field shapes")
    if not np.allclose(a.field.radial_fraction,b.field.radial_fraction,atol=0.0,rtol=0.0):
        raise AdmissibilityError("mechanical states must share the same mapped radial_fraction coordinate")
    return shape_a


def _weighted_rms(squared:np.ndarray,weights:np.ndarray,valid:np.ndarray)->float:
    mask=valid & np.isfinite(squared) & np.isfinite(weights) & (weights>0)
    if not np.any(mask):
        raise AdmissibilityError("comparison has no common positively weighted valid samples")
    return float(np.sqrt(np.sum(weights[mask]*squared[mask])/np.sum(weights[mask])))


def wall_shear_distance(a:MechanicalState,b:MechanicalState,*,tau_scale_pa:float,wall_weights:object)->float:
    """Evaluate d_tau on an explicitly pre-mapped wall correspondence."""
    tau_c=float(tau_scale_pa)
    if not np.isfinite(tau_c) or tau_c<=0:
        raise AdmissibilityError("tau_scale_pa must be a finite positive scalar")
    ar=np.asarray(a.wall_traction.radial_component_pa); az=np.asarray(a.wall_traction.axial_component_pa)
    br=np.asarray(b.wall_traction.radial_component_pa); bz=np.asarray(b.wall_traction.axial_component_pa)
    if ar.shape != br.shape:
        raise AdmissibilityError("wall traction fields must have identical mapped shapes")
    weights=np.asarray(wall_weights,dtype=float)
    if weights.shape != ar.shape:
        raise AdmissibilityError("wall_weights must match (path_position,time)")
    valid=np.asarray(a.valid_path_mask)[:,None] & np.asarray(b.valid_path_mask)[:,None]
    return _weighted_rms((ar-br)**2+(az-bz)**2,weights,valid)/tau_c


def mechanical_state_distance(
    a:MechanicalState,b:MechanicalState,*,volume_weights:object,
    state_weights:tuple[float,float,float,float,float]=(0.2,0.2,0.2,0.2,0.2),
)->float:
    """Evaluate d_M on an explicitly pre-mapped near-wall volume correspondence."""
    shape=_common_shape(a,b); weights=np.asarray(volume_weights,dtype=float)
    if weights.shape != shape:
        raise AdmissibilityError("volume_weights must match (path_position,time,radial_fraction)")
    w=tuple(float(value) for value in state_weights)
    if len(w)!=5 or any((not np.isfinite(value) or value<0) for value in w) or not np.isclose(sum(w),1.0,atol=1e-12,rtol=0.0):
        raise AdmissibilityError("state_weights must be five non-negative values summing to one")
    dq=(np.asarray(a.q_star)-np.asarray(b.q_star))**2
    dqh=(np.asarray(a.q_h_star)-np.asarray(b.q_h_star))**2
    dcu=(np.asarray(a.c_u_r_star)-np.asarray(b.c_u_r_star))**2+(np.asarray(a.c_u_z_star)-np.asarray(b.c_u_z_star))**2
    dch=(np.asarray(a.c_h_r_star)-np.asarray(b.c_h_r_star))**2+(np.asarray(a.c_h_z_star)-np.asarray(b.c_h_z_star))**2
    dcd=(np.asarray(a.c_d_r_star)-np.asarray(b.c_d_r_star))**2+(np.asarray(a.c_d_z_star)-np.asarray(b.c_d_z_star))**2
    squared=w[0]*dq+w[1]*dqh+w[2]*dcu+w[3]*dch+w[4]*dcd
    valid=np.asarray(a.valid_path_mask)[:,None,None] & np.asarray(b.valid_path_mask)[:,None,None]
    return _weighted_rms(squared,weights,valid)


def closure_comparison(
    a:MechanicalState,b:MechanicalState,*,tau_scale_pa:float,wall_weights:object,volume_weights:object,
    state_weights:tuple[float,float,float,float,float]=(0.2,0.2,0.2,0.2,0.2),
    epsilon_tau:float|None=None,epsilon_mechanical:float|None=None,
)->ClosureComparison:
    """Compare shear and mechanical equivalence without choosing thresholds or mappings for the user."""
    d_tau=wall_shear_distance(a,b,tau_scale_pa=tau_scale_pa,wall_weights=wall_weights)
    d_m=mechanical_state_distance(a,b,volume_weights=volume_weights,state_weights=state_weights)
    if (epsilon_tau is None)!=(epsilon_mechanical is None):
        raise AdmissibilityError("epsilon_tau and epsilon_mechanical must either both be supplied or both omitted")
    shear_equivalent=mechanical_equivalent=degeneracy=None
    if epsilon_tau is not None and epsilon_mechanical is not None:
        e_tau=float(epsilon_tau); e_m=float(epsilon_mechanical)
        if e_tau<0 or e_m<0 or not np.isfinite(e_tau) or not np.isfinite(e_m):
            raise AdmissibilityError("closure thresholds must be finite and non-negative")
        shear_equivalent=d_tau<=e_tau; mechanical_equivalent=d_m<=e_m
        degeneracy=shear_equivalent and not mechanical_equivalent
    return ClosureComparison(d_tau,d_m,shear_equivalent,mechanical_equivalent,degeneracy,tuple(float(v) for v in state_weights))


__all__=["CLOSURE_METHOD_ID","ClosureComparison","closure_comparison","mechanical_state_distance","wall_shear_distance"]
