"""Qualified linear and robust regression."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from vascuquest.analysis import ensure_same_dataset, make_result
from vascuquest.analysis.core import cohort_subject_ids
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import AdmissibilityError
from ._shared import _finite_vector, _stats

def linear_regression(response: ScientificResult, predictors: Sequence[ScientificResult], *, standardized: bool = False) -> ScientificResult:
    if not predictors:
        raise ValueError("at least one predictor is required")
    all_results = (response, *tuple(predictors))
    ensure_same_dataset(*all_results)
    ids = cohort_subject_ids(response)
    for predictor in predictors:
        if cohort_subject_ids(predictor) != ids:
            raise AdmissibilityError("regression predictors and response must share identical canonical subject alignment")
    y = _finite_vector(response)
    columns = [_finite_vector(p) for p in predictors]
    if any(col.size != y.size for col in columns):
        raise AdmissibilityError("all regression inputs must contain the same number of observations")
    x = np.column_stack(columns)
    x_names = [p.quantity.canonical_name for p in predictors]
    if standardized:
        x_sd = np.std(x, axis=0, ddof=1)
        y_sd = float(np.std(y, ddof=1))
        if np.any(x_sd == 0) or y_sd == 0:
            raise AdmissibilityError("standardized regression requires non-zero variance in all variables")
        x = (x - np.mean(x, axis=0)) / x_sd
        y = (y - np.mean(y)) / y_sd
    design = np.column_stack([np.ones(y.size), x])
    rank = np.linalg.matrix_rank(design)
    if rank < design.shape[1]:
        raise AdmissibilityError("regression design matrix is rank deficient")
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ beta
    residual = y - fitted
    n, p = design.shape
    dof = n - p
    if dof <= 0:
        raise AdmissibilityError("regression requires more observations than fitted coefficients")
    sse = float(residual @ residual)
    mse = sse / dof
    covariance = mse * np.linalg.inv(design.T @ design)
    se = np.sqrt(np.diag(covariance))
    t_stat = beta / se
    scipy_stats = _stats()
    pvalues = 2.0 * scipy_stats.t.sf(np.abs(t_stat), dof)
    centered = y - np.mean(y)
    sst = float(centered @ centered)
    r2 = 1.0 - sse / sst if sst > 0 else 1.0
    adjusted = 1.0 - (1.0 - r2) * (n - 1) / dof if n > 1 else r2
    names = ["intercept", *x_names]
    values = {
        "n": int(n),
        "degrees_of_freedom": int(dof),
        "standardized": bool(standardized),
        "r2": float(r2),
        "adjusted_r2": float(adjusted),
        "coefficients": {name: float(value) for name, value in zip(names, beta)},
        "standard_errors": {name: float(value) for name, value in zip(names, se)},
        "t_statistics": {name: float(value) for name, value in zip(names, t_stat)},
        "pvalues": {name: float(value) for name, value in zip(names, pvalues)},
    }
    return make_result(
        response,
        canonical_name=f"stats.linear_regression.{response.quantity.canonical_name}",
        label="Linear regression",
        description="Ordinary least-squares regression over deterministically aligned VascuQuest cohort results.",
        values=values,
        method_id="vascuquest:stats:ols-v1",
        inputs=all_results,
        evidence=EvidenceClass.INFERRED,
        canonical_unit=None if standardized else response.canonical_unit,
        physical_dimension=None if standardized else response.physical_dimension,
        value_kind="mapping",
        parameters={"standardized": standardized, "predictors": x_names},
        subject=None,
        location=None,
    )

def robust_regression(response: ScientificResult, predictors: Sequence[ScientificResult], *, huber_delta: float = 1.345, max_iter: int = 100, tolerance: float = 1e-8) -> ScientificResult:
    if not predictors:
        raise ValueError("at least one predictor is required")
    if huber_delta <= 0 or max_iter < 1 or tolerance <= 0:
        raise ValueError("invalid robust-regression tuning parameters")
    ids = cohort_subject_ids(response)
    for p in predictors:
        if cohort_subject_ids(p) != ids:
            raise AdmissibilityError("robust-regression inputs must share identical canonical subject alignment")
    y = _finite_vector(response)
    x = np.column_stack([_finite_vector(p) for p in predictors])
    design = np.column_stack([np.ones(y.size), x])
    if np.linalg.matrix_rank(design) < design.shape[1]:
        raise AdmissibilityError("robust-regression design matrix is rank deficient")
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    for iteration in range(max_iter):
        residual = y - design @ beta
        med = np.median(residual); mad = np.median(np.abs(residual-med))
        scale = max(float(1.4826*mad), np.finfo(float).eps)
        u = residual/scale
        weights = np.ones_like(u); mask=np.abs(u)>huber_delta; weights[mask]=huber_delta/np.abs(u[mask])
        root_w=np.sqrt(weights); new_beta=np.linalg.lstsq(design*root_w[:,None], y*root_w, rcond=None)[0]
        if np.linalg.norm(new_beta-beta) <= tolerance*(1+np.linalg.norm(beta)):
            beta=new_beta; break
        beta=new_beta
    fitted=design@beta; residual=y-fitted
    names=["intercept",*[p.quantity.canonical_name for p in predictors]]
    return make_result(
        response, canonical_name=f"stats.robust_regression.{response.quantity.canonical_name}", label="Huber robust regression",
        description="Iteratively reweighted least-squares Huber regression over aligned VascuQuest cohort results.",
        values={"coefficients":{n:float(v) for n,v in zip(names,beta)},"iterations":int(iteration+1),"huber_delta":huber_delta,"median_absolute_residual":float(np.median(np.abs(residual)))},
        method_id="vascuquest:stats:huber-irls-v1", inputs=(response,*tuple(predictors)), parameters={"huber_delta":huber_delta,"max_iter":max_iter,"tolerance":tolerance},
        evidence=EvidenceClass.INFERRED, canonical_unit=response.canonical_unit, physical_dimension=response.physical_dimension,
        value_kind="mapping", subject=None, location=None,
    )
