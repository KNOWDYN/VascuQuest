from __future__ import annotations

import pytest

from vascuquest.disease.solver.backends import (
    create_disease_solver,
    normalize_solver_backend,
)
from vascuquest.disease.solver.disease_finite_volume import DiseaseOneDSolver


def test_numpy_backend_remains_default_reference() -> None:
    solver = create_disease_solver()
    assert isinstance(solver, DiseaseOneDSolver)
    assert normalize_solver_backend(" NumPy ") == "numpy"


def test_invalid_backend_is_rejected_before_optional_import() -> None:
    with pytest.raises(ValueError, match="numpy.*jax"):
        create_disease_solver(backend="cuda")


def test_jax_backend_is_lazy_optional() -> None:
    try:
        solver = create_disease_solver(backend="jax")
    except ImportError as exc:
        assert "optional 'jax' dependency" in str(exc)
    else:
        assert solver.__class__.__name__ == "JaxDiseaseOneDSolver"
