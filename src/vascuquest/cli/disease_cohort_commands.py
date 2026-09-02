"""CLI surface for parameterized Virtual Disease cohorts."""

from __future__ import annotations

from pathlib import Path

import typer

from vascuquest.disease import (
    create_parameterized_cohort_plan,
    generate_parameterized_cohort,
    inspect_parameterized_cohort_bundle,
    read_cohort_plan,
    verify_parameterized_cohort_bundle,
    write_cohort_plan,
)
from vascuquest.disease.catalogue import resolve_condition
from vascuquest.disease.solver.backends import normalize_solver_backend
from vascuquest.errors import AdmissibilityError

from .commands import CANONICAL_DATASET, _emit, _parse_assignments
from .disease_commands import _preflight_sources

cohort_app = typer.Typer(
    help="Plan, generate, inspect and verify heterogeneous Virtual Disease cohorts.",
    no_args_is_help=True,
)


def _resolve_condition(value: str):
    try:
        return resolve_condition(value)
    except AdmissibilityError as exc:
        raise typer.BadParameter(str(exc), param_hint="condition") from exc


def _resolve_solver_backend(value: str) -> str:
    try:
        return normalize_solver_backend(value)
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="--solver-backend") from exc


@cohort_app.command("plan")
def cohort_plan(
    condition: str = typer.Argument(...),
    patients: int = typer.Option(..., "--patients"),
    age_min: int = typer.Option(..., "--age-min"),
    age_max: int = typer.Option(..., "--age-max"),
    severity_min: float = typer.Option(..., "--severity-min"),
    severity_max: float = typer.Option(..., "--severity-max"),
    param: list[str] = typer.Option([], "--param"),
    seed: int = typer.Option(0, "--seed"),
    plan_path: str = typer.Option(..., "--plan", help="Write the frozen cohort plan JSON here."),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    yes: bool = typer.Option(False, "--yes"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Freeze source-supported subjects and individually admissible severities; do not solve."""
    resolved = _resolve_condition(condition)
    fixed_parameters = _parse_assignments(param, "--param")
    _preflight_sources(source=source, offline=offline, yes=yes)
    plan = create_parameterized_cohort_plan(
        patients=patients,
        age_min=age_min,
        age_max=age_max,
        condition=resolved,
        severity_min=severity_min,
        severity_max=severity_max,
        fixed_parameters=fixed_parameters,
        seed=seed,
        dataset=dataset,
        source=source,
        offline=offline,
    )
    written = write_cohort_plan(plan, Path(plan_path).expanduser(), overwrite=overwrite)
    typer.echo(
        "Parameterized cohort boundary: source-supported PWDB ages only; "
        "subject-specific executable disease admissibility; designed counterfactual cohort, "
        "not an epidemiological population.",
        err=True,
    )
    payload = plan.to_dict()
    payload["plan_path"] = str(written)
    _emit(payload, output_format, output)


@cohort_app.command("generate")
def cohort_generate(
    plan_path: str = typer.Option(..., "--plan"),
    bundle: str = typer.Option(..., "--bundle"),
    resume: bool = typer.Option(False, "--resume"),
    solver_backend: str = typer.Option(
        "numpy",
        "--solver-backend",
        help="Numerical backend: numpy (frozen reference) or jax (accelerated split solver).",
    ),
    dataset: str = typer.Option(CANONICAL_DATASET, "--dataset"),
    source: str | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    yes: bool = typer.Option(False, "--yes"),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Execute a frozen plan with resumable full-network persistence."""
    plan = read_cohort_plan(Path(plan_path).expanduser())
    backend = _resolve_solver_backend(solver_backend)
    _preflight_sources(source=source, offline=offline, yes=yes)
    typer.echo(
        "Parameterized cohort generation: every subject runs the complete 116-segment "
        f"Virtual Disease solver with backend={backend}; outputs remain MODELLED and "
        "not clinically validated.",
        err=True,
    )
    path = generate_parameterized_cohort(
        plan,
        destination=Path(bundle).expanduser(),
        dataset=dataset,
        source=source,
        offline=offline,
        solver_backend=backend,
        resume=resume,
    )
    _emit(inspect_parameterized_cohort_bundle(path), output_format, output)


@cohort_app.command("inspect")
def cohort_inspect(
    bundle: str = typer.Argument(...),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Inspect cohort request, assignments, progress and scientific boundary."""
    _emit(
        inspect_parameterized_cohort_bundle(Path(bundle).expanduser()),
        output_format,
        output,
    )


@cohort_app.command("verify")
def cohort_verify(
    bundle: str = typer.Argument(...),
    output_format: str = typer.Option("text", "--format"),
    output: str | None = typer.Option(None, "--output"),
) -> None:
    """Verify plan identity, subject completeness and bundle SHA-256 integrity."""
    _emit(
        verify_parameterized_cohort_bundle(Path(bundle).expanduser()),
        output_format,
        output,
    )


__all__ = ["cohort_app"]
