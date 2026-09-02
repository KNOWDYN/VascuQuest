"""Native and optional accelerated 1-D cardiovascular solvers."""

from .backends import (
    DiseaseSolverBackend,
    create_disease_solver,
    jax_backend_available,
    normalize_solver_backend,
)
from .finite_volume import NativeOneDSolver
from .model import ForwardSolution, SegmentMesh, SegmentSolution, SolverDiagnostics, SolverOptions
from .network import (
    NetworkDiscretization,
    ThinWallLaw,
    VoigtWallLaw,
    build_network,
    wall_eh_n_per_m,
    wall_gamma_source,
)

__all__ = [
    "DiseaseSolverBackend",
    "ForwardSolution",
    "NativeOneDSolver",
    "NetworkDiscretization",
    "SegmentMesh",
    "SegmentSolution",
    "SolverDiagnostics",
    "SolverOptions",
    "ThinWallLaw",
    "VoigtWallLaw",
    "build_network",
    "create_disease_solver",
    "jax_backend_available",
    "normalize_solver_backend",
    "wall_eh_n_per_m",
    "wall_gamma_source",
]
