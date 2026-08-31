from __future__ import annotations

from vascuquest.disease.cohort.execution import (
    JAX_SPLIT_SCHEME_ID,
    NUMPY_REFERENCE_SCHEME_ID,
    solver_execution_descriptor,
)
from vascuquest.disease.solver.model import SolverOptions


def test_solver_execution_identity_separates_backend_from_scientific_plan() -> None:
    options = SolverOptions()
    numpy_execution = solver_execution_descriptor("numpy", options)
    jax_execution = solver_execution_descriptor("jax", options)
    assert numpy_execution["numerical_scheme_id"] == NUMPY_REFERENCE_SCHEME_ID
    assert jax_execution["numerical_scheme_id"] == JAX_SPLIT_SCHEME_ID
    assert numpy_execution["solver_execution_id"] != jax_execution["solver_execution_id"]
    assert numpy_execution["solver_options"] == jax_execution["solver_options"]


def test_solver_execution_identity_is_deterministic_and_option_sensitive() -> None:
    first = solver_execution_descriptor("jax", SolverOptions())
    second = solver_execution_descriptor(" JAX ", SolverOptions())
    changed = solver_execution_descriptor("jax", SolverOptions(cfl=0.40))
    assert first == second
    assert first["solver_execution_id"] != changed["solver_execution_id"]
