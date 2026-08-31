from __future__ import annotations

import numpy as np

from vascuquest.disease.solver import NativeOneDSolver, SolverOptions


def test_native_solver_preserves_zero_flow_reference_state(one_segment_baseline) -> None:
    solver = NativeOneDSolver(
        SolverOptions(
            target_dx_m=0.05,
            minimum_cells_per_segment=2,
            minimum_cycles=1,
            maximum_cycles=1,
            periodicity_tolerance=1e-10,
        )
    )
    solution = solver.solve(one_segment_baseline)
    segment = solution.segment("1")
    assert solution.diagnostics.converged
    assert solution.diagnostics.periodicity_error <= 1e-10
    assert solution.diagnostics.terminal_mass_balance_relative_error <= 1e-12
    assert np.all(np.isfinite(segment.area_m2))
    assert np.all(np.isfinite(segment.flow_m3_per_s))
    assert np.all(np.isfinite(segment.pressure_pa))
    assert np.max(np.abs(segment.flow_m3_per_s)) <= 1e-14
    assert np.allclose(
        segment.pressure_pa,
        one_segment_baseline.diastolic_pressure_pa,
        rtol=0.0,
        atol=1e-8,
    )
