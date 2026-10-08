"""CLI for qualified VascuQuest statistics."""
from __future__ import annotations
import json
from pathlib import Path
import typer
import numpy as np
from vascuquest.exporters.json_exporter import load_result_json
from .core import bootstrap_mean_ci, correlate, describe, empirical_quantiles, exceedance_probability, independent_compare, linear_regression, normality_test, paired_compare, partial_correlation, permutation_mean_difference, robust_regression, variance_test

stats_app = typer.Typer(help="Qualified statistics for native VascuQuest scientific results.", no_args_is_help=True)

def _portable(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k:_portable(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [_portable(v) for v in value]
    return value

def _emit(result):
    typer.echo(json.dumps({"quantity": result.quantity.canonical_name, "evidence": result.evidence.value, "method_id": result.method_id, "provenance_ref": result.provenance_ref, "values": _portable(result.values), "warnings": list(result.warnings)}, sort_keys=True))

@stats_app.command("describe")
def describe_cmd(source: Path):
    """Describe one native VascuQuest result."""
    _emit(describe(load_result_json(source)))

@stats_app.command("bootstrap")
def bootstrap_cmd(source: Path, confidence: float = 0.95, resamples: int = 2000, seed: int = 0):
    """Bootstrap the arithmetic mean with an explicit reproducible seed."""
    _emit(bootstrap_mean_ci(load_result_json(source), confidence=confidence, n_resamples=resamples, seed=seed))

@stats_app.command("compare")
def compare_cmd(a: Path, b: Path, paired: bool = typer.Option(False, "--paired"), method: str = "auto"):
    """Compare two VascuQuest results; paired analysis requires identical subject alignment."""
    ra, rb = load_result_json(a), load_result_json(b)
    chosen = ("ttest" if paired else "welch") if method == "auto" else method
    _emit(paired_compare(ra, rb, method=chosen) if paired else independent_compare(ra, rb, method=chosen))

@stats_app.command("correlate")
def correlate_cmd(x: Path, y: Path, method: str = "pearson"):
    """Correlate two results over the same deterministically aligned cohort."""
    _emit(correlate(load_result_json(x), load_result_json(y), method=method))

@stats_app.command("regress")
def regress_cmd(response: Path, predictor: list[Path] = typer.Argument(...), standardized: bool = False):
    """Fit OLS to an aligned cohort response and one or more predictors."""
    _emit(linear_regression(load_result_json(response), [load_result_json(p) for p in predictor], standardized=standardized))

@stats_app.command("normality")
def normality_cmd(source: Path, method: str = "shapiro"):
    """Run a qualified normality diagnostic."""
    _emit(normality_test(load_result_json(source), method=method))

@stats_app.command("variance")
def variance_cmd(a: Path, b: Path, center: str = "median"):
    """Run Levene/Brown-Forsythe variance-homogeneity test."""
    _emit(variance_test(load_result_json(a), load_result_json(b), center=center))

@stats_app.command("permutation")
def permutation_cmd(a: Path, b: Path, paired: bool = typer.Option(False, "--paired"), resamples: int = 5000, seed: int = 0):
    """Run deterministic two-sided permutation test of mean difference."""
    _emit(permutation_mean_difference(load_result_json(a), load_result_json(b), paired=paired, n_resamples=resamples, seed=seed))

@stats_app.command("partial-correlate")
def partial_correlate_cmd(x: Path, y: Path, control: list[Path] = typer.Argument(...), method: str = "pearson"):
    """Partial correlation after aligned linear residualization against controls."""
    _emit(partial_correlation(load_result_json(x), load_result_json(y), [load_result_json(c) for c in control], method=method))

@stats_app.command("robust-regress")
def robust_regress_cmd(response: Path, predictor: list[Path] = typer.Argument(...), huber_delta: float = 1.345):
    """Fit Huber IRLS robust regression to aligned cohort results."""
    _emit(robust_regression(load_result_json(response), [load_result_json(p) for p in predictor], huber_delta=huber_delta))

@stats_app.command("quantiles")
def quantiles_cmd(source: Path):
    """Return canonical empirical quantiles."""
    _emit(empirical_quantiles(load_result_json(source)))

@stats_app.command("exceedance")
def exceedance_cmd(source: Path, threshold: float, inclusive: bool = True):
    """Compute empirical designed-cohort exceedance fraction at an explicit threshold."""
    _emit(exceedance_probability(load_result_json(source), threshold=threshold, inclusive=inclusive))

__all__ = ["stats_app"]
