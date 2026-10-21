"""Independent certificate for the VascuQuest mechanical-closure extension."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state import MechanicalState


MECHANICAL_CERTIFICATE_METHOD_ID = "vascuquest:kinematics:mechanical-closure-certificate-v1"


@dataclass(frozen=True, slots=True)
class MechanicalClosureCertificate:
    charge_identity_max_normalized_residual: float
    crocco_max_normalized_residual: float
    dominance_partition_max_abs_error: float
    qualified_path_points: int
    masked_path_points: int
    passed: bool
    warnings: tuple[str,...]
    method_id: str = MECHANICAL_CERTIFICATE_METHOD_ID

    def to_dict(self)->dict[str,object]:
        return {
            "charge_identity_max_normalized_residual":self.charge_identity_max_normalized_residual,
            "crocco_max_normalized_residual":self.crocco_max_normalized_residual,
            "dominance_partition_max_abs_error":self.dominance_partition_max_abs_error,
            "qualified_path_points":self.qualified_path_points,
            "masked_path_points":self.masked_path_points,
            "passed":self.passed,
            "warnings":list(self.warnings),
            "method_id":self.method_id,
        }


def _nanmax_abs(values:np.ndarray)->float:
    finite=np.isfinite(values)
    return float(np.max(np.abs(values[finite]))) if np.any(finite) else float("nan")


def certify_mechanical_state(
    state:MechanicalState,*,charge_tolerance:float=5e-2,crocco_tolerance:float=5e-2,
    partition_tolerance:float=1e-10,
)->MechanicalClosureCertificate:
    """Certify independent identities without using them to construct each other."""
    lamb=state.lamb; topology=state.topology; crocco=state.crocco
    qh=np.asarray(lamb.q_h_divergence_s_2,dtype=float)
    q=np.asarray(topology.q_invariant_s_2,dtype=float)
    lap_k=np.asarray(lamb.laplacian_kinetic_energy_s_2,dtype=float)
    residual=np.asarray(lamb.charge_identity_residual_s_2,dtype=float)
    denominator=np.abs(qh)+2.0*np.abs(q)+np.abs(lap_k)
    normalized_charge=np.full_like(residual,np.nan)
    active=denominator>0
    normalized_charge[active]=np.abs(residual[active])/denominator[active]
    charge_error=_nanmax_abs(normalized_charge)
    crocco_error=_nanmax_abs(np.asarray(crocco.normalized_residual,dtype=float))
    partition=np.asarray(crocco.dominance_unsteady)+np.asarray(crocco.dominance_head)+np.asarray(crocco.dominance_viscous)-1.0
    partition_error=_nanmax_abs(partition)
    if np.isnan(partition_error): partition_error=0.0
    valid=np.asarray(state.valid_path_mask,dtype=bool)
    warnings=[]
    if np.isnan(charge_error): warnings.append("hydrodynamic-charge identity has no finite qualified samples")
    if np.isnan(crocco_error): warnings.append("Crocco residual has no finite qualified samples")
    passed=(
        np.isfinite(charge_error) and np.isfinite(crocco_error)
        and charge_error<=float(charge_tolerance) and crocco_error<=float(crocco_tolerance)
        and partition_error<=float(partition_tolerance)
    )
    return MechanicalClosureCertificate(
        charge_error,crocco_error,partition_error,int(np.count_nonzero(valid)),
        int(valid.size-np.count_nonzero(valid)),bool(passed),tuple(warnings),
    )


__all__=["MECHANICAL_CERTIFICATE_METHOD_ID","MechanicalClosureCertificate","certify_mechanical_state"]
