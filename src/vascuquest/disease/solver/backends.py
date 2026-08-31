"""Virtual Disease numerical backend selection.

NumPy remains the default/frozen reference. JAX is loaded lazily only when
explicitly requested so the core package has no mandatory accelerator dependency.
"""

from __future__ import annotations

from typing import Literal

from .disease_finite_volume import DiseaseOneDSolver
from .model import SolverOptions

DiseaseSolverBackend = Literal["numpy", "jax"]


def normalize_solver_backend(value: str) -> DiseaseSolverBackend:
    if not isinstance(value, str):
        raise TypeError("solver_backend must be a string")
    normalized = value.strip().lower()
    if normalized not in {"numpy", "jax"}:
        raise ValueError("solver_backend must be 'numpy' or 'jax'")
    return normalized  # type: ignore[return-value]


def create_disease_solver(
    options: SolverOptions | None = None,
    *,
    backend: str = "numpy",
):
    resolved = normalize_solver_backend(backend)
    if resolved == "numpy":
        return DiseaseOneDSolver(options)
    from .jax_disease import JaxDiseaseOneDSolver

    return JaxDiseaseOneDSolver(options)


def jax_backend_available() -> bool:
    try:
        import jax  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "DiseaseSolverBackend",
    "create_disease_solver",
    "jax_backend_available",
    "normalize_solver_backend",
]
