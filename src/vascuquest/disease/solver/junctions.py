"""Linearised characteristic coupling at internal arterial junctions."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from vascuquest.disease.baseline.model import BaselineCardiovascularState

from .network import NetworkDiscretization, ThinWallLaw

EndpointKey = tuple[str, str]
BoundaryState = tuple[float, float]


def _impedance(
    area: float,
    reference_area: float,
    beta: float,
    density: float,
) -> float:
    c = float(ThinWallLaw.wave_speed_m_per_s(area, reference_area, beta, density))
    return density * c / area


def internal_junction_states(
    baseline: BaselineCardiovascularState,
    network: NetworkDiscretization,
    conserved: dict[str, np.ndarray],
) -> dict[EndpointKey, BoundaryState]:
    """Return boundary states for every non-root, non-terminal network node.

    The coupling is a first-order characteristic compatibility solve around the
    adjacent cell states. It enforces a single nodal pressure and exact flow
    conservation for arbitrary junction degree.
    """

    incoming: dict[int, list[str]] = defaultdict(list)
    outgoing: dict[int, list[str]] = defaultdict(list)
    for segment in baseline.segments:
        incoming[segment.outlet_node].append(segment.segment_id)
        outgoing[segment.inlet_node].append(segment.segment_id)

    result: dict[EndpointKey, BoundaryState] = {}
    nodes = set(incoming) | set(outgoing)
    for node in nodes:
        ins = incoming.get(node, [])
        outs = outgoing.get(node, [])
        if not ins or not outs:
            continue

        numerator = 0.0
        denominator = 0.0
        in_data: list[tuple[str, float, float, float]] = []
        out_data: list[tuple[str, float, float, float]] = []

        for segment_id in ins:
            mesh = network.mesh(segment_id)
            values = conserved[segment_id]
            area = float(values[0, -1])
            flow = float(values[1, -1])
            pressure = float(
                ThinWallLaw.pressure_pa(
                    area,
                    mesh.reference_area_m2[-1],
                    mesh.beta_pa[-1],
                    baseline.diastolic_pressure_pa,
                )
            )
            impedance = _impedance(
                area,
                float(mesh.reference_area_m2[-1]),
                float(mesh.beta_pa[-1]),
                baseline.blood_density_kg_per_m3,
            )
            in_data.append((segment_id, flow, pressure, impedance))
            numerator += flow + pressure / impedance
            denominator += 1.0 / impedance

        for segment_id in outs:
            mesh = network.mesh(segment_id)
            values = conserved[segment_id]
            area = float(values[0, 0])
            flow = float(values[1, 0])
            pressure = float(
                ThinWallLaw.pressure_pa(
                    area,
                    mesh.reference_area_m2[0],
                    mesh.beta_pa[0],
                    baseline.diastolic_pressure_pa,
                )
            )
            impedance = _impedance(
                area,
                float(mesh.reference_area_m2[0]),
                float(mesh.beta_pa[0]),
                baseline.blood_density_kg_per_m3,
            )
            out_data.append((segment_id, flow, pressure, impedance))
            numerator -= flow - pressure / impedance
            denominator += 1.0 / impedance

        p_node = numerator / denominator

        for segment_id, flow, pressure, impedance in in_data:
            mesh = network.mesh(segment_id)
            q_boundary = flow + (pressure - p_node) / impedance
            a_boundary = float(
                ThinWallLaw.area_from_pressure(
                    p_node,
                    mesh.reference_area_m2[-1],
                    mesh.beta_pa[-1],
                    baseline.diastolic_pressure_pa,
                )
            )
            result[(segment_id, "outlet")] = (a_boundary, q_boundary)

        for segment_id, flow, pressure, impedance in out_data:
            mesh = network.mesh(segment_id)
            q_boundary = flow + (p_node - pressure) / impedance
            a_boundary = float(
                ThinWallLaw.area_from_pressure(
                    p_node,
                    mesh.reference_area_m2[0],
                    mesh.beta_pa[0],
                    baseline.diastolic_pressure_pa,
                )
            )
            result[(segment_id, "inlet")] = (a_boundary, q_boundary)

    return result


def junction_mass_residual(
    states: dict[EndpointKey, BoundaryState],
    node_in: tuple[str, ...],
    node_out: tuple[str, ...],
) -> float:
    return float(
        sum(states[(segment_id, "outlet")][1] for segment_id in node_in)
        - sum(states[(segment_id, "inlet")][1] for segment_id in node_out)
    )


__all__ = [
    "BoundaryState",
    "EndpointKey",
    "internal_junction_states",
    "junction_mass_residual",
]
