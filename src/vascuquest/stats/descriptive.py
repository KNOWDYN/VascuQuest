"""Descriptive and probabilistic statistics."""
from __future__ import annotations
from collections.abc import Sequence
import numpy as np
from vascuquest.analysis import make_result
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import AdmissibilityError
from ._shared import _finite_vector, _stats

def describe(result: ScientificResult) -> ScientificResult:
    x = _finite_vector(result, 1)
    values = {
        "n": int(x.size),
        "mean": float(np.mean(x)),
        "sd": float(np.std(x, ddof=1)) if x.size > 1 else 0.0,
        "median": float(np.median(x)),
        "q25": float(np.quantile(x, 0.25)),
        "q75": float(np.quantile(x, 0.75)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }
    return make_result(
        result,
        canonical_name=f"stats.describe.{result.quantity.canonical_name}",
        label=f"Descriptive statistics: {result.quantity.label}",
        description="Qualified descriptive statistics preserving VascuQuest scientific context.",
        values=values,
        method_id="vascuquest:stats:describe-v1",
        evidence=EvidenceClass.DERIVED,
        canonical_unit=result.canonical_unit,
        physical_dimension=result.physical_dimension,
        value_kind="mapping",
        parameters={"ddof": 1},
    )

def bootstrap_mean_ci(
    result: ScientificResult,
    *,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int = 0,
) -> ScientificResult:
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    if n_resamples < 100:
        raise ValueError("n_resamples must be at least 100")
    x = _finite_vector(result, 2)
    rng = np.random.default_rng(seed)
    means = np.mean(rng.choice(x, size=(n_resamples, x.size), replace=True), axis=1)
    alpha = 1.0 - confidence
    values = {
        "estimate": float(np.mean(x)),
        "lower": float(np.quantile(means, alpha / 2.0)),
        "upper": float(np.quantile(means, 1.0 - alpha / 2.0)),
        "confidence": confidence,
        "n_resamples": int(n_resamples),
        "seed": int(seed),
    }
    return make_result(
        result,
        canonical_name=f"stats.bootstrap_mean_ci.{result.quantity.canonical_name}",
        label=f"Bootstrap mean CI: {result.quantity.label}",
        description="Percentile bootstrap confidence interval for the arithmetic mean.",
        values=values,
        method_id="vascuquest:stats:bootstrap-mean-ci-v1",
        evidence=EvidenceClass.INFERRED,
        canonical_unit=result.canonical_unit,
        physical_dimension=result.physical_dimension,
        value_kind="mapping",
        parameters={"confidence": confidence, "n_resamples": n_resamples, "seed": seed},
    )

def normality_test(result: ScientificResult, *, method: str = "shapiro") -> ScientificResult:
    x = _finite_vector(result, 3)
    scipy_stats = _stats()
    if method == "shapiro":
        test = scipy_stats.shapiro(x)
        warning = ("Shapiro-Wilk p-values may be less accurate for very large samples.",) if x.size > 5000 else ()
    elif method == "dagostino":
        if x.size < 8:
            raise AdmissibilityError("D'Agostino-Pearson normality test requires at least 8 observations")
        test = scipy_stats.normaltest(x)
        warning = ()
    else:
        raise ValueError("normality method must be 'shapiro' or 'dagostino'")
    return make_result(
        result, canonical_name=f"stats.normality.{method}.{result.quantity.canonical_name}", label=f"Normality test ({method})",
        description="Qualified normality diagnostic for a scalar VascuQuest result.",
        values={"method":method,"n":int(x.size),"statistic":float(test.statistic),"pvalue":float(test.pvalue)},
        method_id=f"vascuquest:stats:normality-{method}-v1", evidence=EvidenceClass.INFERRED, canonical_unit="1",
        physical_dimension="dimensionless", value_kind="mapping", warnings=warning,
    )

def empirical_quantiles(result: ScientificResult, probabilities: Sequence[float] = (0.05,0.25,0.5,0.75,0.95)) -> ScientificResult:
    x = _finite_vector(result, 1)
    probs = np.asarray(tuple(probabilities), dtype=float)
    if probs.ndim != 1 or probs.size == 0 or np.any((probs < 0) | (probs > 1)):
        raise ValueError("probabilities must be a non-empty vector in [0,1]")
    values = {format(float(p), ".12g"): float(q) for p,q in zip(probs, np.quantile(x, probs))}
    return make_result(
        result, canonical_name=f"stats.quantiles.{result.quantity.canonical_name}", label="Empirical quantiles",
        description="Empirical quantiles of a scalar VascuQuest result.", values=values, method_id="vascuquest:stats:quantiles-v1",
        evidence=EvidenceClass.DERIVED, canonical_unit=result.canonical_unit, physical_dimension=result.physical_dimension,
        value_kind="mapping", parameters={"probabilities":probs.tolist()},
    )

def exceedance_probability(result: ScientificResult, *, threshold: float, inclusive: bool = True) -> ScientificResult:
    x = _finite_vector(result, 1)
    mask = x >= threshold if inclusive else x > threshold
    value = float(np.mean(mask))
    return make_result(
        result, canonical_name=f"stats.exceedance_probability.{result.quantity.canonical_name}", label="Empirical exceedance probability",
        description="Fraction of the designed virtual cohort at or above an explicit threshold.",
        values={"threshold":float(threshold),"inclusive":inclusive,"count":int(np.count_nonzero(mask)),"n":int(x.size),"probability":value},
        method_id="vascuquest:stats:exceedance-probability-v1", evidence=EvidenceClass.DERIVED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="mapping",
        warnings=("This is an empirical fraction of a designed virtual population, not a clinical or epidemiological probability.",),
    )
