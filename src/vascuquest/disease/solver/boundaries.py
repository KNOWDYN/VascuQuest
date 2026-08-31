"""Aortic inflow and terminal three-element Windkessel boundary coupling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState, BaselineSegment

from .model import SegmentMesh
from .network import ThinWallLaw


@dataclass(frozen=True, slots=True)
class WindkesselParameters:
    r1_pa_s_per_m3: float
    r2_pa_s_per_m3: float
    compliance_m3_per_pa: float


def characteristic_impedance(
    baseline: BaselineCardiovascularState,
    mesh: SegmentMesh,
    area: float,
    *,
    at_outlet: bool,
) -> float:
    index = -1 if at_outlet else 0
    c = float(
        ThinWallLaw.wave_speed_m_per_s(
            area,
            mesh.reference_area_m2[index],
            mesh.beta_pa[index],
            baseline.blood_density_kg_per_m3,
        )
    )
    return baseline.blood_density_kg_per_m3 * c / area


def windkessel_parameters(
    baseline: BaselineCardiovascularState,
    segment: BaselineSegment,
    mesh: SegmentMesh,
) -> WindkesselParameters:
    """Split source total R into characteristic R1 and distal R2.

    PWDB/Nektar uses R1 equal to local characteristic impedance when possible.
    The exported geometry stores total terminal resistance and compliance.
    """
    total = segment.peripheral_resistance_pa_s_per_m3
    area = float(mesh.reference_area_m2[-1])
    zc = characteristic_impedance(baseline, mesh, area, at_outlet=True)
    if zc < total:
        r1 = zc
        r2 = total - zc
    else:
        # Preserve positivity for unusual source configurations while making the
        # deviation explicit through reconstruction metrics rather than hiding it.
        r1 = 0.5 * total
        r2 = total - r1
    return WindkesselParameters(r1, r2, segment.peripheral_compliance_m3_per_pa)


def root_boundary_state(
    baseline: BaselineCardiovascularState,
    mesh: SegmentMesh,
    conserved: np.ndarray,
    time_s: float,
) -> tuple[float, float]:
    a_int = float(conserved[0, 0])
    q_int = float(conserved[1, 0])
    p_int = float(
        ThinWallLaw.pressure_pa(
            a_int,
            mesh.reference_area_m2[0],
            mesh.beta_pa[0],
            baseline.diastolic_pressure_pa,
        )
    )
    z = characteristic_impedance(baseline, mesh, a_int, at_outlet=False)
    q_in = baseline.aortic_inflow.value_at(time_s)
    p_boundary = p_int + z * (q_in - q_int)
    a_boundary = float(
        ThinWallLaw.area_from_pressure(
            p_boundary,
            mesh.reference_area_m2[0],
            mesh.beta_pa[0],
            baseline.diastolic_pressure_pa,
        )
    )
    return a_boundary, q_in


def terminal_boundary_state(
    baseline: BaselineCardiovascularState,
    segment: BaselineSegment,
    mesh: SegmentMesh,
    conserved: np.ndarray,
    capacitor_pressure_pa: float,
) -> tuple[tuple[float, float], float]:
    a_int = float(conserved[0, -1])
    q_int = float(conserved[1, -1])
    p_int = float(
        ThinWallLaw.pressure_pa(
            a_int,
            mesh.reference_area_m2[-1],
            mesh.beta_pa[-1],
            baseline.diastolic_pressure_pa,
        )
    )
    wk = windkessel_parameters(baseline, segment, mesh)
    z = characteristic_impedance(baseline, mesh, a_int, at_outlet=True)

    # Solve linearized outgoing characteristic with P = Pc + R1 Q.
    q_boundary = (q_int + (p_int - capacitor_pressure_pa) / z) / (1.0 + wk.r1_pa_s_per_m3 / z)
    p_boundary = capacitor_pressure_pa + wk.r1_pa_s_per_m3 * q_boundary
    a_boundary = float(
        ThinWallLaw.area_from_pressure(
            p_boundary,
            mesh.reference_area_m2[-1],
            mesh.beta_pa[-1],
            baseline.diastolic_pressure_pa,
        )
    )
    dpc_dt = (
        q_boundary
        - (capacitor_pressure_pa - baseline.outlet_pressure_pa) / wk.r2_pa_s_per_m3
    ) / wk.compliance_m3_per_pa
    return (a_boundary, q_boundary), float(dpc_dt)


__all__ = [
    "WindkesselParameters",
    "characteristic_impedance",
    "root_boundary_state",
    "terminal_boundary_state",
    "windkessel_parameters",
]
