"""Typer commands for the integrated HEMOSPACE operation mode."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .agent import agent_contract
from .api import open_hemospace
from .cohort import TRIAL_PROFILES


hemospace_app = typer.Typer(
    name="hemospace",
    help="Build and interrogate provenance-aware cardiovascular records for PWDB virtual subjects.",
    no_args_is_help=True,
)
cohort_app = typer.Typer(
    name="cohort",
    help="Select and characterize phenotype-driven virtual research cohorts.",
    no_args_is_help=True,
)
hemospace_app.add_typer(cohort_app, name="cohort")


def _emit(payload: object, *, output: Path | None, compact: bool) -> None:
    text = json.dumps(
        payload,
        indent=None if compact else 2,
        sort_keys=True,
        separators=(",", ":") if compact else None,
        ensure_ascii=False,
    )
    if output is None:
        typer.echo(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


@hemospace_app.command("record")
def record_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    depth: str = typer.Option("scalar", "--depth", help="Record depth: scalar, geometry, or comprehensive."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
    output: Path | None = typer.Option(None, "--output", help="Write JSON to this path instead of stdout."),
    compact: bool = typer.Option(False, "--compact", help="Emit compact JSON for agents/pipelines."),
) -> None:
    """Build one Virtual Cardiovascular Record."""
    hs = open_hemospace(source=source, offline=offline)
    _emit(hs.record(subject, depth=depth).to_dict(), output=output, compact=compact)


@hemospace_app.command("coverage")
def coverage_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    depth: str = typer.Option("scalar", "--depth", help="Record depth: scalar, geometry, or comprehensive."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
) -> None:
    """Report machine-auditable HEMOSPACE knowledge coverage for one subject."""
    hs = open_hemospace(source=source, offline=offline)
    _emit(hs.record(subject, depth=depth).coverage.to_dict(), output=None, compact=False)


@hemospace_app.command("path")
def path_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    path_name: str = typer.Option(..., "--path", help="aorta_brain, aorta_finger, aorta_foot, or aorta_r_subclavian."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
    output: Path | None = typer.Option(None, "--output"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    """Lazily characterize one canonical PWDB path-resolved source."""
    hs = open_hemospace(source=source, offline=offline)
    _emit(hs.path(subject, path_name).to_dict(), output=output, compact=compact)


@hemospace_app.command("response")
def response_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB subject in the persisted disease cohort."),
    bundle: Path = typer.Option(..., "--bundle", help="Existing parameterized Virtual Disease cohort bundle."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing healthy-source artifacts."),
    output: Path | None = typer.Option(None, "--output"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    """Build a paired healthy-to-disease response record without rerunning the solver."""
    hs = open_hemospace(source=source, offline=offline)
    _emit(hs.response(bundle, subject).to_dict(), output=output, compact=compact)


@hemospace_app.command("closure")
def closure_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    depth: str = typer.Option("comprehensive", "--depth", help="Requested closure depth."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Audit HEMOSPACE knowledge closure and canonical-source disposition."""
    hs = open_hemospace(source=source, offline=offline)
    _emit(hs.closure(subject, depth=depth).to_dict(), output=output, compact=False)


@hemospace_app.command("agent-contract")
def agent_contract_command(
    output: Path | None = typer.Option(None, "--output"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    """Emit the machine-readable HEMOSPACE operating contract for AI agents."""
    _emit(agent_contract(), output=output, compact=compact)


@hemospace_app.command("profiles")
def profiles_command(
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    """List curated endovascular in-silico study profiles."""
    _emit(
        {
            "kind": "vascuquest.hemospace.trial_profiles",
            "profiles": {key: value.to_dict() for key, value in sorted(TRIAL_PROFILES.items())},
        },
        output=None,
        compact=compact,
    )


@cohort_app.command("select")
def cohort_select_command(
    criterion: list[str] = typer.Option([], "--criterion", "-c", help="Repeatable criterion such as arterial_stiffness_variation>=1."),
    profile_id: str | None = typer.Option(None, "--profile", help="Optional curated endovascular study profile."),
    describe: bool = typer.Option(False, "--describe", help="Include a baseline phenotype summary for the selected cohort."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
    output: Path | None = typer.Option(None, "--output"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    """Select a reproducible virtual cohort from explicit HEMOSPACE phenotypes."""
    hs = open_hemospace(source=source, offline=offline)
    cohort = hs.select_cohort(criterion, profile_id=profile_id)
    payload: dict[str, object] = {"cohort": cohort.to_dict()}
    if describe:
        payload["description"] = hs.describe_cohort(cohort)
    _emit(payload, output=output, compact=compact)


@hemospace_app.command("explain")
def explain_command() -> None:
    """Describe the epistemic boundary of HEMOSPACE for humans and agents."""
    typer.echo(
        "HEMOSPACE builds Virtual Cardiovascular Records for PWDB simulation instances. "
        "It preserves SOURCE data, deterministic RECONSTRUCTED quantities, documented DERIVED physiology, "
        "and explicit MODELLED/INFERRED outputs when present. It does not invent unencoded patient history, "
        "clinical diagnoses, symptoms, genetics, medication use, plaque biology, or longitudinal life events."
    )


__all__ = ["cohort_app", "hemospace_app"]
