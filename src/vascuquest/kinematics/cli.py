"""CLI for the exact VascuQuest axisymmetric kinematic lift."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import typer

from vascuquest.hemospace.api import open_hemospace

from .certificate import certify_lift
from .source import lift_hemospace_path


kinematics_app = typer.Typer(
    help="Exact axisymmetric kinematic lift from path-resolved U(z,t) and A(z,t).",
    no_args_is_help=True,
)


def _time_vector(samples: int, sample_period_s: float | None) -> np.ndarray | None:
    if sample_period_s is None:
        return None
    if sample_period_s <= 0:
        raise typer.BadParameter("--sample-period-s must be positive")
    return np.arange(samples, dtype=float) * sample_period_s


def _payload(field, certificate, output: Path | None) -> dict[str, object]:
    result = field.metadata()
    result["certificate"] = certificate.to_dict()
    result["output"] = None if output is None else str(output)
    return result


@kinematics_app.command("lift")
def lift_command(
    subject: str = typer.Option(..., "--subject", help="Canonical PWDB virtual-subject identifier."),
    path_name: str = typer.Option(..., "--path", help="Canonical HEMOSPACE arterial path."),
    source: Path | None = typer.Option(None, "--source", help="Directory containing canonical PWDB artifacts."),
    offline: bool = typer.Option(False, "--offline", help="Forbid acquisition of missing source artifacts."),
    radial_points: int = typer.Option(17, "--radial-points", min=5, help="Normalized radial grid size including axis and wall."),
    sample_period_s: float | None = typer.Option(None, "--sample-period-s", help="Optional stored-wave sample period for the wall-motion certificate."),
    output: Path = typer.Option(..., "--output", help="Compressed NPZ destination for the reconstructed fields."),
) -> None:
    """Reconstruct and export the exact axisymmetric velocity/vorticity field."""
    hs = open_hemospace(source=source, offline=offline)
    field = lift_hemospace_path(hs, subject, path_name, radial_points=radial_points)
    time_s = _time_vector(field.mean_velocity_m_s.shape[1], sample_period_s)
    certificate = certify_lift(field, time_s=time_s)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        distance_m=field.distance_m,
        radial_fraction=field.radial_fraction,
        mean_velocity_m_s=field.mean_velocity_m_s,
        area_m2=field.area_m2,
        radius_m=field.radius_m,
        axial_velocity_m_s=field.axial_velocity_m_s,
        radial_velocity_m_s=field.radial_velocity_m_s,
        azimuthal_vorticity_s_1=field.azimuthal_vorticity_s_1,
        wall_vorticity_s_1=field.wall_vorticity_s_1,
    )
    typer.echo(json.dumps(_payload(field, certificate, output), sort_keys=True))


@kinematics_app.command("certify")
def certify_command(
    subject: str = typer.Option(..., "--subject"),
    path_name: str = typer.Option(..., "--path"),
    source: Path | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    radial_points: int = typer.Option(17, "--radial-points", min=5),
    sample_period_s: float | None = typer.Option(None, "--sample-period-s"),
) -> None:
    """Run the independent numerical certificate without exporting the field."""
    hs = open_hemospace(source=source, offline=offline)
    field = lift_hemospace_path(hs, subject, path_name, radial_points=radial_points)
    time_s = _time_vector(field.mean_velocity_m_s.shape[1], sample_period_s)
    certificate = certify_lift(field, time_s=time_s)
    typer.echo(json.dumps(_payload(field, certificate, None), sort_keys=True))


__all__ = ["kinematics_app"]
