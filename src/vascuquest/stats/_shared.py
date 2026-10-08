from __future__ import annotations
import numpy as np
from vascuquest.analysis import numeric_values
from vascuquest.analysis.core import require_optional_dependency
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import AdmissibilityError

def _stats():
    return require_optional_dependency("scipy.stats", "research")

def _finite_vector(result: ScientificResult, min_size: int = 2) -> np.ndarray:
    values = numeric_values(result, min_size=min_size)
    values = np.asarray(values, dtype=float).reshape(-1)
    if result.cohort is not None and values.size != len(result.cohort.canonical_subject_ids):
        raise AdmissibilityError("cohort statistical inputs must contain one scalar value per canonical subject")
    return values
