"""CLI for exact VascuQuest kinematics and mechanical-closure analysis."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import typer

from vascuquest.hemospace.api import open_hemospace

from .certificate import certify_lift
from .mechanical_certificate import certify_mechanical_state
from .source import lift_hemospace_path, mechanical_state_from_hemospace


kinematics_app = typer.Typer(
    help="Exact axisymmetric kinematic lift and mechanical-closure analysis.",
    no_args_is_help=True,
)


def _time_vector(samples: int, sample_period_s: float | None) -> np.ndarray | None:
    if sample_period_s is None:
        return None
    if sample_period_s <= 0:
        raise typer.BadParameter("--sample-period-s must be positive")
    return np.arange(samples, dtype=float) * sample_period_s


def _required_time_vector(samples: int, sample_period_s: float | None) -> np.ndarray:
    result = _time_vector(samples, sample_period_s)
    if result is None:
        raise typer.BadParameter("--sample-period-s is required for mechanical-closure analysis")
    return result


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
        valid_path_mask=field.valid_path_mask,
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
    """Run the independent kinematic certificate without exporting the field."""
    hs = open_hemospace(source=source, offline=offline)
    field = lift_hemospace_path(hs, subject, path_name, radial_points=radial_points)
    time_s = _time_vector(field.mean_velocity_m_s.shape[1], sample_period_s)
    certificate = certify_lift(field, time_s=time_s)
    typer.echo(json.dumps(_payload(field, certificate, None), sort_keys=True))


def _mechanical_state_from_cli(
    subject: str,
    path_name: str,
    source: Path | None,
    offline: bool,
    radial_points: int,
    sample_period_s: float,
    density_kg_m3: float,
    viscosity_pa_s: float,
    velocity_scale_m_s: float,
    length_scale_m: float,
    activity_threshold_fraction: float,
    thickness_fraction: float,
):
    hs = open_hemospace(source=source, offline=offline)
    raw = hs._session.waveform if False else None  # keep HEMOSPACE acquisition lazy; source bridge owns path reads
    del raw
    # Read once through the canonical bridge to determine sample count without inventing timing.
    from .source import path_waves_from_hemospace
    waves = path_waves_from_hemospace(hs, subject, path_name, signals=("P", "U", "A"))
    samples = waves.matrix("U").shape[1]
    time_s = _required_time_vector(samples, sample_period_s)
    from .source import mechanical_state_from_path_waves
    return mechanical_state_from_path_waves(
        waves, time_s, density_kg_m3, viscosity_pa_s,
        velocity_scale_m_s=velocity_scale_m_s,
        length_scale_m=length_scale_m,
        radial_points=radial_points,
        activity_threshold_fraction=activity_threshold_fraction,
        thickness_fraction=thickness_fraction,
    )


@kinematics_app.command("mechanical-state")
def mechanical_state_command(
    subject: str = typer.Option(..., "--subject"),
    path_name: str = typer.Option(..., "--path"),
    source: Path | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    radial_points: int = typer.Option(33, "--radial-points", min=5),
    sample_period_s: float = typer.Option(..., "--sample-period-s"),
    density_kg_m3: float = typer.Option(..., "--density-kg-m3"),
    viscosity_pa_s: float = typer.Option(..., "--viscosity-pa-s"),
    velocity_scale_m_s: float = typer.Option(..., "--velocity-scale-m-s"),
    length_scale_m: float = typer.Option(..., "--length-scale-m"),
    activity_threshold_fraction: float = typer.Option(0.0, "--activity-threshold-fraction"),
    thickness_fraction: float = typer.Option(0.10, "--thickness-fraction"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    """Export the mechanical-closure state from canonical P/U/A path waves."""
    state = _mechanical_state_from_cli(
        subject,path_name,source,offline,radial_points,sample_period_s,density_kg_m3,
        viscosity_pa_s,velocity_scale_m_s,length_scale_m,activity_threshold_fraction,thickness_fraction,
    )
    certificate=certify_mechanical_state(state)
    output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(
        output,
        distance_m=state.field.distance_m,
        radial_fraction=state.field.radial_fraction,
        q_star=state.q_star,
        q_h_star=state.q_h_star,
        c_u_r_star=state.c_u_r_star,
        c_u_z_star=state.c_u_z_star,
        c_h_r_star=state.c_h_r_star,
        c_h_z_star=state.c_h_z_star,
        c_d_r_star=state.c_d_r_star,
        c_d_z_star=state.c_d_z_star,
        wall_shear_pa=state.wall_traction.magnitude_pa,
        lamb_load_normal_pa=state.lamb_load.wall_normal_component_pa,
        valid_path_mask=state.valid_path_mask,
    )
    payload=state.metadata(); payload["certificate"]=certificate.to_dict(); payload["output"]=str(output)
    typer.echo(json.dumps(payload,sort_keys=True))


@kinematics_app.command("mechanical-certify")
def mechanical_certify_command(
    subject: str = typer.Option(..., "--subject"),
    path_name: str = typer.Option(..., "--path"),
    source: Path | None = typer.Option(None, "--source"),
    offline: bool = typer.Option(False, "--offline"),
    radial_points: int = typer.Option(33, "--radial-points", min=5),
    sample_period_s: float = typer.Option(..., "--sample-period-s"),
    density_kg_m3: float = typer.Option(..., "--density-kg-m3"),
    viscosity_pa_s: float = typer.Option(..., "--viscosity-pa-s"),
    velocity_scale_m_s: float = typer.Option(..., "--velocity-scale-m-s"),
    length_scale_m: float = typer.Option(..., "--length-scale-m"),
    activity_threshold_fraction: float = typer.Option(0.0, "--activity-threshold-fraction"),
    thickness_fraction: float = typer.Option(0.10, "--thickness-fraction"),
) -> None:
    """Run the independent mechanical-closure certificate."""
    state = _mechanical_state_from_cli(
        subject,path_name,source,offline,radial_points,sample_period_s,density_kg_m3,
        viscosity_pa_s,velocity_scale_m_s,length_scale_m,activity_threshold_fraction,thickness_fraction,
    )
    payload=state.metadata(); payload["certificate"]=certify_mechanical_state(state).to_dict()
    typer.echo(json.dumps(payload,sort_keys=True))


__all__ = ["kinematics_app"]
