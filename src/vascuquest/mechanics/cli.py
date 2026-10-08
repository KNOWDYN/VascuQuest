"""CLI for VascuQuest vascular mechanics."""
from __future__ import annotations
import json
from pathlib import Path
import typer
from vascuquest.exporters.json_exporter import load_result_json
from vascuquest.domain.result import Waveform
from .core import compute

mechanics_app = typer.Typer(help="Qualified pressure-area and vascular-wall mechanics.", no_args_is_help=True)

@mechanics_app.command("compute")
def compute_cmd(metric: str, area: Path, pressure: Path | None = None, blood_density: float = 1060.0):
    """Compute one qualified mechanics metric from native VascuQuest waveform JSON."""
    area_result = load_result_json(area)
    if not isinstance(area_result, Waveform): raise typer.BadParameter("area input must be a VascuQuest Waveform")
    pressure_result = None if pressure is None else load_result_json(pressure)
    if pressure_result is not None and not isinstance(pressure_result, Waveform): raise typer.BadParameter("pressure input must be a VascuQuest Waveform")
    result = compute(metric, pressure=pressure_result, area=area_result, blood_density=blood_density)
    typer.echo(json.dumps({"quantity":result.quantity.canonical_name,"value":result.values,"unit":result.canonical_unit,"method_id":result.method_id,"evidence":result.evidence.value,"warnings":list(result.warnings)}, sort_keys=True))

@mechanics_app.command("list")
def list_cmd():
    """List canonical v1 mechanics metrics."""
    names = ["area_strain","diameter_strain","area_compliance","area_distensibility","pressure_area_slope","peterson_modulus","beta_stiffness_index","bramwell_hill_wave_speed","pressure_area_loop_integral"]
    typer.echo("\n".join(names))

__all__ = ["mechanics_app"]
