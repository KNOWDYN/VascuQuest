from __future__ import annotations

import numpy as np

from vascuquest.disease.runtime.materialize import _resample_history
from vascuquest.disease.solver.model import (
    ForwardSolution,
    SegmentSolution,
    SolverDiagnostics,
)


def test_runtime_resampling_aligns_to_requested_parent_cycle_grid() -> None:
    time = np.asarray([0.0, 0.25, 0.50, 0.75, 1.0])
    x = np.asarray([0.025, 0.075])
    area = np.column_stack(
        (
            np.asarray([1.0, 1.1, 1.2, 1.1, 1.0]) * 1e-4,
            np.asarray([2.0, 2.1, 2.2, 2.1, 2.0]) * 1e-4,
        )
    )
    flow = np.column_stack(
        (
            np.asarray([0.0, 1.0, 2.0, 1.0, 0.0]) * 1e-6,
            np.asarray([0.0, 2.0, 4.0, 2.0, 0.0]) * 1e-6,
        )
    )
    pressure = np.column_stack(
        (
            np.asarray([100.0, 110.0, 120.0, 110.0, 100.0]),
            np.asarray([200.0, 210.0, 220.0, 210.0, 200.0]),
        )
    )
    solution = ForwardSolution(
        time_s=time,
        segments=(
            SegmentSolution(
                segment_id="1",
                x_m=x,
                area_m2=area,
                flow_m3_per_s=flow,
                pressure_pa=pressure,
            ),
        ),
        diagnostics=SolverDiagnostics(
            cycles_completed=3,
            periodicity_error=0.0,
            converged=True,
            minimum_area_ratio=1.0,
            maximum_cfl=0.1,
            maximum_diffusion_number=0.0,
            terminal_mass_balance_relative_error=0.0,
        ),
    )
    parent_time = np.asarray([10.0, 10.125, 10.50, 10.875])
    sampled_area, sampled_flow, sampled_pressure = _resample_history(
        solution,
        "1",
        0.0,
        parent_time,
    )

    np.testing.assert_allclose(
        sampled_area,
        np.asarray([1.0, 1.05, 1.2, 1.05]) * 1e-4,
    )
    np.testing.assert_allclose(
        sampled_flow,
        np.asarray([0.0, 0.5, 2.0, 0.5]) * 1e-6,
    )
    np.testing.assert_allclose(
        sampled_pressure,
        np.asarray([100.0, 105.0, 120.0, 105.0]),
    )
    assert not sampled_area.flags.writeable
    assert not sampled_flow.flags.writeable
    assert not sampled_pressure.flags.writeable
