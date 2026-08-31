from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.solver.disease_finite_volume import DiseaseOneDSolver
from vascuquest.disease.solver.losses import LocalizedPressureLoss
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network


def test_disease_solver_preserves_zero_flow_equilibrium_with_local_loss(
    one_segment_baseline,
) -> None:
    options = SolverOptions(
        target_dx_m=0.05,
        minimum_cells_per_segment=2,
        minimum_cycles=2,
        maximum_cycles=3,
        periodicity_tolerance=1e-10,
    )
    network = build_network(one_segment_baseline, options)
    mesh = network.mesh("1")
    weights = np.ones(mesh.cell_count, dtype=float) / float(np.sum(mesh.dx_m))
    loss = LocalizedPressureLoss(
        segment_id="1",
        weights_per_m=weights,
        linear_resistance_pa_s_per_m3=2.0e8,
        quadratic_resistance_pa_s2_per_m6=1.0e12,
        model_id="synthetic-test-loss",
    )
    solution = DiseaseOneDSolver(options).solve(
        one_segment_baseline,
        network,
        pressure_losses=(loss,),
    )
    segment = solution.segment("1")
    assert solution.diagnostics.converged
    assert np.max(np.abs(segment.flow_m3_per_s)) == pytest.approx(0.0, abs=1e-14)
    np.testing.assert_allclose(
        segment.pressure_pa,
        one_segment_baseline.diastolic_pressure_pa,
        rtol=0.0,
        atol=1e-8,
    )
