"""Typer commands for the integrated HEMOSPACE operation mode."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .api import open_hemospace


hemospace_app = typer.Typer(
    name="hemospace",
    help="Build comprehensive, provenance-aware cardiovascular records for PWDB virtual subjects.",
    no_args_is_help=True,
)


def _emit(payload: object, *, output: Path | None, compact: bool) -> None:
    text = json.dumps(payload, indent=None if compact else 2, sort_keys=True, separators=(",", ":") if compact else None)
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
    record = hs.record(subject, depth=depth)
    _emit(record.to_dict(), output=output, compact=compact)


@hemospace_app.command("coverage")
def coverage_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    depth: str = typer.Option("scalar", "--depth", help="Record depth: scalar, geometry, or comprehensive."),
    source: Path | None = typer.Option(None, "--source", help="Existing directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid network acquisition of missing artifacts."),
) -> None:
    """Report machine-auditable HEMOSPACE knowledge coverage for one subject."""

    hs = open_hemospace(source=source, offline=offline)
    record = hs.record(subject, depth=depth)
    _emit(record.coverage.to_dict(), output=None, compact=False)


@hemospace_app.command("explain")
def explain_command() -> None:
    """Describe the epistemic boundary of HEMOSPACE for humans and agents."""

    typer.echo(
        "HEMOSPACE builds Virtual Cardiovascular Records for PWDB simulation instances. "
        "It preserves SOURCE data, deterministic RECONSTRUCTED quantities, documented DERIVED physiology, "
        "and explicit MODELLED/INFERRED outputs when present. It does not invent unencoded patient history, "
        "clinical diagnoses, symptoms, genetics, medication use, plaque biology, or longitudinal life events."
    )


__all__ = ["hemospace_app"]
