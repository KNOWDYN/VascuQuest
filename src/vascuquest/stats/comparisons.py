"""Aligned comparisons, correlations and group tests."""
from __future__ import annotations
from collections.abc import Sequence
import math
import numpy as np
from vascuquest.analysis import ensure_paired, ensure_same_dataset, make_result
from vascuquest.analysis.core import cohort_subject_ids
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import AdmissibilityError
from ._shared import _finite_vector, _stats

def paired_compare(a: ScientificResult, b: ScientificResult, *, method: str = "ttest") -> ScientificResult:
    ensure_paired(a, b)
    x, y = _finite_vector(a), _finite_vector(b)
    if x.size != y.size:
        raise AdmissibilityError("paired results must contain the same number of values")
    scipy_stats = _stats()
    diff = y - x
    if method == "ttest":
        test = scipy_stats.ttest_rel(y, x, nan_policy="raise")
        sd = float(np.std(diff, ddof=1))
        effect = float(np.mean(diff) / sd) if sd > 0 else math.inf if np.mean(diff) != 0 else 0.0
        effect_name = "cohens_dz"
        statistic = float(test.statistic)
        pvalue = float(test.pvalue)
    elif method == "wilcoxon":
        test = scipy_stats.wilcoxon(y, x, zero_method="wilcox", alternative="two-sided")
        statistic, pvalue = float(test.statistic), float(test.pvalue)
        effect, effect_name = float("nan"), "not_reported"
    else:
        raise ValueError("paired method must be 'ttest' or 'wilcoxon'")
    values = {
        "method": method,
        "n": int(x.size),
        "mean_difference": float(np.mean(diff)),
        "statistic": statistic,
        "pvalue": pvalue,
        "effect_size": effect,
        "effect_size_name": effect_name,
    }
    return make_result(
        a,
        canonical_name=f"stats.paired_{method}.{a.quantity.canonical_name}.{b.quantity.canonical_name}",
        label=f"Paired {method} comparison",
        description="Paired inferential comparison over identical canonical virtual subjects in identical deterministic order.",
        values=values,
        method_id=f"vascuquest:stats:paired-{method}-v1",
        inputs=(a, b),
        evidence=EvidenceClass.INFERRED,
        canonical_unit=a.canonical_unit if a.canonical_unit == b.canonical_unit else None,
        physical_dimension=a.physical_dimension if a.physical_dimension == b.physical_dimension else None,
        value_kind="mapping",
        parameters={"paired": True, "method": method},
        cohort=a.cohort,
        subject=None,
        location=None,
    )

def independent_compare(a: ScientificResult, b: ScientificResult, *, method: str = "welch") -> ScientificResult:
    ensure_same_dataset(a, b)
    if a.cohort is not None:
        cohort_subject_ids(a)
    if b.cohort is not None:
        cohort_subject_ids(b)
    x, y = _finite_vector(a), _finite_vector(b)
    scipy_stats = _stats()
    if method == "welch":
        test = scipy_stats.ttest_ind(x, y, equal_var=False, nan_policy="raise")
        statistic, pvalue = float(test.statistic), float(test.pvalue)
        nx, ny = x.size, y.size
        pooled_num = (nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)
        pooled_den = nx + ny - 2
        pooled = math.sqrt(float(pooled_num / pooled_den)) if pooled_den > 0 and pooled_num > 0 else 0.0
        d = float((np.mean(x) - np.mean(y)) / pooled) if pooled > 0 else 0.0
        correction = 1.0 - 3.0 / (4.0 * (nx + ny) - 9.0) if nx + ny > 2 else 1.0
        effect, effect_name = correction * d, "hedges_g"
    elif method == "mannwhitney":
        test = scipy_stats.mannwhitneyu(x, y, alternative="two-sided")
        statistic, pvalue = float(test.statistic), float(test.pvalue)
        effect, effect_name = float(2.0 * statistic / (x.size * y.size) - 1.0), "rank_biserial"
    else:
        raise ValueError("independent method must be 'welch' or 'mannwhitney'")
    values = {
        "method": method,
        "n_a": int(x.size),
        "n_b": int(y.size),
        "mean_a": float(np.mean(x)),
        "mean_b": float(np.mean(y)),
        "mean_difference": float(np.mean(x) - np.mean(y)),
        "statistic": statistic,
        "pvalue": pvalue,
        "effect_size": float(effect),
        "effect_size_name": effect_name,
    }
    return make_result(
        a,
        canonical_name=f"stats.independent_{method}.{a.quantity.canonical_name}.{b.quantity.canonical_name}",
        label=f"Independent {method} comparison",
        description="Independent-cohort inferential comparison for designed virtual populations.",
        values=values,
        method_id=f"vascuquest:stats:independent-{method}-v1",
        inputs=(a, b),
        evidence=EvidenceClass.INFERRED,
        canonical_unit=a.canonical_unit if a.canonical_unit == b.canonical_unit else None,
        physical_dimension=a.physical_dimension if a.physical_dimension == b.physical_dimension else None,
        value_kind="mapping",
        parameters={"paired": False, "method": method},
        cohort=None,
        subject=None,
        location=None,
        warnings=("PWDB cohorts are designed virtual populations; statistical results are not epidemiological prevalence estimates.",),
    )

def correlate(x_result: ScientificResult, y_result: ScientificResult, *, method: str = "pearson") -> ScientificResult:
    ensure_paired(x_result, y_result)
    x, y = _finite_vector(x_result), _finite_vector(y_result)
    scipy_stats = _stats()
    if method == "pearson":
        r = scipy_stats.pearsonr(x, y)
    elif method == "spearman":
        r = scipy_stats.spearmanr(x, y)
    else:
        raise ValueError("correlation method must be 'pearson' or 'spearman'")
    values = {"method": method, "n": int(x.size), "coefficient": float(r.statistic), "pvalue": float(r.pvalue)}
    return make_result(
        x_result,
        canonical_name=f"stats.correlation.{method}.{x_result.quantity.canonical_name}.{y_result.quantity.canonical_name}",
        label=f"{method.title()} correlation",
        description="Correlation computed over explicitly paired canonical virtual subjects.",
        values=values,
        method_id=f"vascuquest:stats:correlation-{method}-v1",
        inputs=(x_result, y_result),
        evidence=EvidenceClass.INFERRED,
        canonical_unit="1",
        physical_dimension="dimensionless",
        value_kind="mapping",
        parameters={"method": method},
        subject=None,
        location=None,
    )

def variance_test(a: ScientificResult, b: ScientificResult, *, center: str = "median") -> ScientificResult:
    ensure_same_dataset(a, b)
    x, y = _finite_vector(a), _finite_vector(b)
    if center not in {"mean", "median", "trimmed"}:
        raise ValueError("center must be mean, median, or trimmed")
    test = _stats().levene(x, y, center=center)
    return make_result(
        a, canonical_name=f"stats.levene.{a.quantity.canonical_name}.{b.quantity.canonical_name}", label="Levene variance test",
        description="Levene/Brown-Forsythe variance-homogeneity test for two virtual-subject groups.",
        values={"center":center,"statistic":float(test.statistic),"pvalue":float(test.pvalue),"n_a":int(x.size),"n_b":int(y.size)},
        method_id="vascuquest:stats:levene-v1", inputs=(a,b), evidence=EvidenceClass.INFERRED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="mapping", subject=None, cohort=None, location=None,
    )

def permutation_mean_difference(a: ScientificResult, b: ScientificResult, *, paired: bool, n_resamples: int = 5000, seed: int = 0) -> ScientificResult:
    if n_resamples < 100:
        raise ValueError("n_resamples must be at least 100")
    rng = np.random.default_rng(seed)
    if paired:
        ensure_paired(a, b)
        x, y = _finite_vector(a), _finite_vector(b)
        diff = y - x
        observed = float(np.mean(diff))
        signs = rng.choice(np.array([-1.0, 1.0]), size=(n_resamples, diff.size))
        null = np.mean(signs * diff, axis=1)
        cohort = a.cohort
    else:
        ensure_same_dataset(a, b)
        x, y = _finite_vector(a), _finite_vector(b)
        observed = float(np.mean(y) - np.mean(x))
        pooled = np.concatenate([x, y])
        null = np.empty(n_resamples, dtype=float)
        nx = x.size
        for i in range(n_resamples):
            perm = rng.permutation(pooled)
            null[i] = np.mean(perm[nx:]) - np.mean(perm[:nx])
        cohort = None
    pvalue = float((np.count_nonzero(np.abs(null) >= abs(observed)) + 1) / (n_resamples + 1))
    return make_result(
        a, canonical_name=f"stats.permutation_mean_difference.{a.quantity.canonical_name}.{b.quantity.canonical_name}", label="Permutation mean-difference test",
        description="Two-sided permutation test of the mean difference with explicit pairing and deterministic seed.",
        values={"paired":paired,"observed_mean_difference":observed,"pvalue":pvalue,"n_resamples":n_resamples,"seed":seed},
        method_id="vascuquest:stats:permutation-mean-difference-v1", inputs=(a,b), parameters={"paired":paired,"n_resamples":n_resamples,"seed":seed},
        evidence=EvidenceClass.INFERRED, canonical_unit=a.canonical_unit if a.canonical_unit==b.canonical_unit else None,
        physical_dimension=a.physical_dimension if a.physical_dimension==b.physical_dimension else None, value_kind="mapping",
        subject=None, cohort=cohort, location=None,
    )

def partial_correlation(x_result: ScientificResult, y_result: ScientificResult, controls: Sequence[ScientificResult], *, method: str = "pearson") -> ScientificResult:
    if not controls:
        return correlate(x_result, y_result, method=method)
    ids = ensure_paired(x_result, y_result)
    for control in controls:
        if cohort_subject_ids(control) != ids:
            raise AdmissibilityError("partial-correlation controls must share identical canonical subject alignment")
    x, y = _finite_vector(x_result), _finite_vector(y_result)
    c = np.column_stack([_finite_vector(control) for control in controls])
    design = np.column_stack([np.ones(x.size), c])
    bx = np.linalg.lstsq(design, x, rcond=None)[0]; by = np.linalg.lstsq(design, y, rcond=None)[0]
    rx = x - design @ bx; ry = y - design @ by
    if float(np.std(rx, ddof=1)) <= np.finfo(float).eps or float(np.std(ry, ddof=1)) <= np.finfo(float).eps:
        raise AdmissibilityError("partial correlation is undefined because residual variance is effectively zero")
    scipy_stats = _stats()
    if method == "pearson": test = scipy_stats.pearsonr(rx, ry)
    elif method == "spearman": test = scipy_stats.spearmanr(rx, ry)
    else: raise ValueError("partial correlation method must be 'pearson' or 'spearman'")
    return make_result(
        x_result, canonical_name=f"stats.partial_correlation.{method}.{x_result.quantity.canonical_name}.{y_result.quantity.canonical_name}",
        label=f"Partial {method} correlation", description="Correlation after linear residualization against explicitly aligned control variables.",
        values={"method":method,"n":int(x.size),"n_controls":len(controls),"coefficient":float(test.statistic),"pvalue":float(test.pvalue)},
        method_id=f"vascuquest:stats:partial-correlation-{method}-v1", inputs=(x_result,y_result,*tuple(controls)), evidence=EvidenceClass.INFERRED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="mapping", subject=None, location=None,
    )

def one_way_anova(groups: Sequence[ScientificResult], *, nonparametric: bool = False) -> ScientificResult:
    results=tuple(groups)
    if len(results)<2: raise ValueError("at least two groups are required")
    ensure_same_dataset(*results)
    arrays=[_finite_vector(r) for r in results]
    scipy_stats=_stats()
    test=scipy_stats.kruskal(*arrays) if nonparametric else scipy_stats.f_oneway(*arrays)
    method="kruskal" if nonparametric else "anova"
    return make_result(
        results[0], canonical_name=f"stats.{method}.{results[0].quantity.canonical_name}", label="Kruskal-Wallis test" if nonparametric else "One-way ANOVA",
        description="Multi-group comparison across explicit VascuQuest result groups.",
        values={"method":method,"groups":len(results),"group_sizes":[int(a.size) for a in arrays],"statistic":float(test.statistic),"pvalue":float(test.pvalue)},
        method_id=f"vascuquest:stats:{method}-v1", inputs=results, evidence=EvidenceClass.INFERRED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="mapping", subject=None, cohort=None, location=None,
        warnings=("Group frequencies in designed virtual populations are not epidemiological prevalence estimates.",),
    )

def ancova(response: ScientificResult, group: ScientificResult, covariates: Sequence[ScientificResult]) -> ScientificResult:
    ids=ensure_paired(response,group)
    for cov in covariates:
        if cohort_subject_ids(cov)!=ids: raise AdmissibilityError("ANCOVA covariates must share identical canonical subject alignment")
    y=_finite_vector(response); g=_finite_vector(group)
    levels=np.unique(g)
    if levels.size<2: raise AdmissibilityError("ANCOVA group result must contain at least two distinct levels")
    if levels.size>20: raise AdmissibilityError("ANCOVA group result has too many levels for a categorical group variable")
    cov=np.column_stack([_finite_vector(c) for c in covariates]) if covariates else np.empty((y.size,0))
    dummies=np.column_stack([(g==level).astype(float) for level in levels[1:]])
    reduced=np.column_stack([np.ones(y.size),cov]); full=np.column_stack([reduced,dummies])
    if np.linalg.matrix_rank(full)<full.shape[1]: raise AdmissibilityError("ANCOVA design matrix is rank deficient")
    b0=np.linalg.lstsq(reduced,y,rcond=None)[0]; b1=np.linalg.lstsq(full,y,rcond=None)[0]
    sse0=float(np.sum((y-reduced@b0)**2)); sse1=float(np.sum((y-full@b1)**2))
    df_num=dummies.shape[1]; df_den=y.size-full.shape[1]
    if df_den<=0: raise AdmissibilityError("ANCOVA requires residual degrees of freedom")
    f=((sse0-sse1)/df_num)/(sse1/df_den) if sse1>0 else math.inf
    pvalue=float(_stats().f.sf(f,df_num,df_den))
    return make_result(
        response, canonical_name=f"stats.ancova.{response.quantity.canonical_name}", label="ANCOVA group effect",
        description="Nested-model ANCOVA test of an explicit categorical group effect after aligned covariate adjustment.",
        values={"group_levels":[float(x) for x in levels],"df_group":int(df_num),"df_residual":int(df_den),"f_statistic":float(f),"pvalue":pvalue,"full_coefficients":[float(x) for x in b1]},
        method_id="vascuquest:stats:ancova-v1", inputs=(response,group,*tuple(covariates)), evidence=EvidenceClass.INFERRED,
        canonical_unit="1", physical_dimension="dimensionless", value_kind="mapping", subject=None, location=None,
    )
