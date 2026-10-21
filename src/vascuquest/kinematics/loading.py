"""Near-wall Lamb loading for the mechanical-closure extension."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .lamb import LambField, lamb_hydrodynamic_charge
from .operators import base_coefficients, mechanical_valid_mask, readonly, readonly_bool


LAMB_LOAD_METHOD_ID = "vascuquest:kinematics:mechanical-closure-radial-shell-load-v1"


@dataclass(frozen=True, slots=True)
class LambLoadField:
    """Areal Lamb load for an axisymmetric wall-adjacent radial shell."""

    thickness_fraction: float
    radial_component_pa: np.ndarray
    axial_component_pa: np.ndarray
    wall_normal_component_pa: np.ndarray
    wall_normal_absolute_pa: np.ndarray
    valid_path_mask: np.ndarray
    control_volume_definition: str
    method_id: str = LAMB_LOAD_METHOD_ID
    evidence: str = "DERIVED"


def _integral_q_polynomial(coefficients: dict[int, np.ndarray], q0: float) -> np.ndarray:
    result = np.zeros_like(next(iter(coefficients.values())), dtype=float)
    for power, coefficient in coefficients.items():
        result += coefficient * (1.0-q0**(power+2))/(power+2)
    return result


def radial_shell_lamb_load(
    field: KinematicLift,
    density_kg_m3: float,
    *,
    thickness_fraction: float = 0.10,
    lamb: LambField | None = None,
) -> LambLoadField:
    """Integrate rho*ell over q in [1-delta*,1] per local wall area.

    The control volume is an exact local axisymmetric radial shell. It coincides
    with a strict wall-normal shell when R_z=0; for sloped walls the result is
    intentionally labelled radial-shell loading rather than silently imposing
    an interpolation-based normal mapping.
    """

    rho = float(density_kg_m3); eps = float(thickness_fraction)
    if not np.isfinite(rho) or rho <= 0:
        raise AdmissibilityError("density_kg_m3 must be a finite positive scalar")
    if not np.isfinite(eps) or eps <= 0 or eps > 1:
        raise AdmissibilityError("thickness_fraction must lie in (0, 1]")
    if lamb is None:
        lamb = lamb_hydrodynamic_charge(field)

    base = base_coefficients(field, minimum_points=4)
    radius = np.asarray(field.radius_m, dtype=float)
    rz = np.asarray(base.radius_z, dtype=float)
    scale = np.sqrt(1.0+rz**2); q0 = 1.0-eps
    a=np.asarray(base.a1); b=np.asarray(base.a3); c=np.asarray(base.c0); d=np.asarray(base.c2)
    w1=np.asarray(base.w1); w3=np.asarray(base.w3)
    ell_r_coeffs = {1:-(c*w1), 3:-(c*w3+d*w1), 5:-(d*w3)}
    ell_z_coeffs = {2:a*w1, 4:a*w3+b*w1, 6:b*w3}

    geometric = rho*radius/scale
    pi_r = geometric*_integral_q_polynomial(ell_r_coeffs,q0)
    pi_z = geometric*_integral_q_polynomial(ell_z_coeffs,q0)
    n_r=-1.0/scale; n_z=rz/scale
    pi_n=n_r*pi_r+n_z*pi_z

    nodes, gauss_weights = np.polynomial.legendre.leggauss(32)
    qg=0.5*(1.0-q0)*nodes+0.5*(1.0+q0)
    wg=0.5*(1.0-q0)*gauss_weights
    ell_r_g=np.zeros((*radius.shape,qg.size),dtype=float)
    ell_z_g=np.zeros_like(ell_r_g)
    for power,coefficient in ell_r_coeffs.items():
        ell_r_g += coefficient[:,:,None]*qg[None,None,:]**power
    for power,coefficient in ell_z_coeffs.items():
        ell_z_g += coefficient[:,:,None]*qg[None,None,:]**power
    ell_n_g=n_r[:,:,None]*ell_r_g+n_z[:,:,None]*ell_z_g
    absolute_integral=np.sum(np.abs(ell_n_g)*qg[None,None,:]*wg[None,None,:],axis=2)
    pi_abs=geometric*absolute_integral

    valid=mechanical_valid_mask(field,np.asarray(base.valid_path_mask),np.asarray(lamb.valid_path_mask))
    for array in (pi_r,pi_z,pi_n,pi_abs):
        array[~valid,...]=np.nan

    return LambLoadField(
        thickness_fraction=eps, radial_component_pa=readonly(pi_r), axial_component_pa=readonly(pi_z),
        wall_normal_component_pa=readonly(pi_n), wall_normal_absolute_pa=readonly(pi_abs),
        valid_path_mask=readonly_bool(valid),
        control_volume_definition=(
            "axisymmetric local radial shell q=r/R in "
            f"[{q0:.12g},1]; per-wall-area Jacobian exact for that shell"
        ),
    )


near_wall_lamb_load=radial_shell_lamb_load

__all__=["LAMB_LOAD_METHOD_ID","LambLoadField","near_wall_lamb_load","radial_shell_lamb_load"]
