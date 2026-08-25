"""Typer application and centralized stable VascuQuest CLI exit mapping."""

from __future__ import annotations

import sys
import traceback

import typer

from vascuquest._version import __version__
from vascuquest.errors import (
    AdmissibilityError,
    CapabilityError,
    DatasetUnavailableError,
    IntegrityError,
    NumericalMethodError,
    PluginCompatibilityError,
    PluginError,
    ReproducibilityError,
    SchemaError,
    SelectionError,
    UnitError,
    VascuQuestError,
    VascuQuestInternalError,
)

from .commands import register_commands


app = typer.Typer(
    name="vascuquest",
    help="Scientific exploration and discovery for virtual vascular populations.",
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_enable=False,
)


@app.callback(invoke_without_command=True)
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the VascuQuest package version and exit.",
        is_eager=True,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show chained diagnostic tracebacks for failures.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress nonessential human diagnostics.",
    ),
) -> None:
    """Global operational flags; scientific behavior is unaffected."""

    del debug, quiet
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)


register_commands(app)


def _exit_code(exc: VascuQuestError) -> int:
    if isinstance(exc, (DatasetUnavailableError, CapabilityError)):
        return 3
    if isinstance(exc, IntegrityError):
        return 4
    if isinstance(exc, (SchemaError, UnitError, SelectionError)):
        return 5
    if isinstance(exc, (AdmissibilityError, NumericalMethodError)):
        return 6
    if isinstance(exc, (PluginCompatibilityError, PluginError)):
        return 7
    if isinstance(exc, ReproducibilityError):
        return 8
    if isinstance(exc, VascuQuestInternalError):
        return 70
    return 70


def _debug_requested(argv: list[str]) -> bool:
    return "--debug" in argv


def main() -> None:
    """Run the CLI while preserving Click usage exits and stable domain exits."""

    debug = _debug_requested(sys.argv[1:])
    try:
        app()
    except VascuQuestError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        if debug:
            traceback.print_exc(file=sys.stderr)
        raise SystemExit(_exit_code(exc)) from exc
    except Exception as exc:
        typer.echo(
            f"VascuQuestInternalError: unexpected internal software failure: {exc}",
            err=True,
        )
        if debug:
            traceback.print_exc(file=sys.stderr)
        raise SystemExit(70) from exc


__all__ = ["app", "main"]
