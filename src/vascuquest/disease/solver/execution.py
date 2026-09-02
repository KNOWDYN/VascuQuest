"""Canonical numerical execution identity for Virtual Disease solvers.

Scientific disease/run identity is intentionally independent of numerical
backend selection.  This module provides the single canonical descriptor used
wherever numerical execution must be persisted or included in provenance.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from .backends import normalize_solver_backend
from .model import SolverOptions

JAX_SPLIT_SCHEME_ID = "jax-exact-loss-rkc2-voigt-ssprk2-v1"
NUMPY_REFERENCE_SCHEME_ID = "numpy-explicit-ssprk2-vd1"
SOLVER_EXECUTION_CONTRACT_VERSION = "solver-execution-v1"


def solver_execution_descriptor(
    solver_backend: str,
    solver_options: SolverOptions,
) -> dict[str, object]:
    """Return the content-addressed numerical execution descriptor."""

    backend = normalize_solver_backend(solver_backend)
    if not isinstance(solver_options, SolverOptions):
        raise TypeError("solver_options must be SolverOptions")
    scheme = JAX_SPLIT_SCHEME_ID if backend == "jax" else NUMPY_REFERENCE_SCHEME_ID
    core = {
        "contract_version": SOLVER_EXECUTION_CONTRACT_VERSION,
        "solver_backend": backend,
        "numerical_scheme_id": scheme,
        "precision": "float64",
        "solver_options": asdict(solver_options),
    }
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False)
    execution_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"solver_execution_id": execution_id, **core}


__all__ = [
    "JAX_SPLIT_SCHEME_ID",
    "NUMPY_REFERENCE_SCHEME_ID",
    "SOLVER_EXECUTION_CONTRACT_VERSION",
    "solver_execution_descriptor",
]
