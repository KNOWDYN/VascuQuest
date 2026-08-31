from __future__ import annotations

import numpy as np

from vascuquest.disease.solver import SolverOptions, build_network
from vascuquest.disease.solver.boundaries import terminal_boundary_state, windkessel_parameters


def test_terminal_windkessel_is_at_equilibrium_for_zero_flow(one_segment_baseline) -> None:
    network = build_network(
        one_segment_baseline,
        SolverOptions(target_dx_m=0.05, minimum_cells_per_segment=2),
    )
    mesh = network.mesh("1")
    conserved = np.vstack((mesh.reference_area_m2, np.zeros(mesh.cell_count)))
    boundary, derivative = terminal_boundary_state(
        one_segment_baseline,
        one_segment_baseline.segments[0],
        mesh,
        conserved,
        one_segment_baseline.diastolic_pressure_pa,
    )
    parameters = windkessel_parameters(
        one_segment_baseline,
        one_segment_baseline.segments[0],
        mesh,
    )
    assert parameters.r1_pa_s_per_m3 > 0
    assert parameters.r2_pa_s_per_m3 > 0
    assert np.isclose(boundary[1], 0.0, atol=1e-18)
    assert np.isclose(derivative, 0.0, atol=1e-18)
