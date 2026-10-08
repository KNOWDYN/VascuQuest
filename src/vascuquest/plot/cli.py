"""CLI for publication-grade VascuQuest figures."""
from __future__ import annotations
from pathlib import Path
import typer
from vascuquest.exporters.json_exporter import load_result_json
from .core import FigureSpec, LayerSpec, PanelSpec, render, write_spec

plot_app = typer.Typer(help="Declarative publication-grade figures from VascuQuest results.", no_args_is_help=True)

@plot_app.command("series")
def series_cmd(source: list[Path] = typer.Argument(...), output: Path = typer.Option(..., "--output"), title: str | None = None, spec_output: Path | None = None):
    """Plot one or more native VascuQuest results as a publication-ready panel."""
    layers = tuple(LayerSpec("line", load_result_json(path), label=path.stem) for path in source)
    spec = FigureSpec((PanelSpec("A", layers, title=title),))
    render(spec, output)
    if spec_output is not None: write_spec(spec, spec_output)

@plot_app.command("scatter")
def scatter_cmd(x: Path, y: Path, output: Path = typer.Option(..., "--output"), title: str | None = None, spec_output: Path | None = None):
    """Plot aligned x/y VascuQuest results; large cohorts remain fully represented."""
    spec = FigureSpec((PanelSpec("A", (LayerSpec("scatter", load_result_json(y), x=load_result_json(x)),), title=title),))
    render(spec, output)
    if spec_output is not None: write_spec(spec, spec_output)

__all__=["plot_app"]
