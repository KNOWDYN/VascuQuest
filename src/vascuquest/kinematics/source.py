"""HEMOSPACE source bridge for exact kinematic and mechanical reconstruction."""
from __future__ import annotations

import numpy as np

from vascuquest.hemospace.path import PathWaveField, path_waves

from .core import KinematicLift, lift_path
from .state import MechanicalState, mechanical_state


MMHG_TO_PA = 133.32236842105263


def path_waves_from_hemospace(
    hemospace_session: object,
    subject_id: str,
    path_name: str,
    *,
    signals: tuple[str, ...] = ("U", "A"),
) -> PathWaveField:
    """Read raw aligned path waves from an open HEMOSPACE session."""
    if not hasattr(hemospace_session, "_resolve") or not hasattr(hemospace_session, "_session"):
        raise TypeError("hemospace_session must be an open VascuQuest HemospaceSession")
    hemospace_session._session.subject(subject_id)
    return path_waves(hemospace_session._resolve, subject_id, path_name, signals=signals)


def lift_hemospace_path(
    hemospace_session: object,
    subject_id: str,
    path_name: str,
    *,
    radial_fraction: object | None = None,
    radial_points: int = 17,
    respect_artery_boundaries: bool = True,
) -> KinematicLift:
    """Read canonical U/A source waves and perform the exact kinematic lift."""
    raw = path_waves_from_hemospace(hemospace_session, subject_id, path_name, signals=("U", "A"))
    return lift_path(
        raw, radial_fraction=radial_fraction, radial_points=radial_points,
        respect_artery_boundaries=respect_artery_boundaries,
    )


def mechanical_state_from_path_waves(
    path_waves_field: PathWaveField,
    time_s: object,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    *,
    velocity_scale_m_s: float,
    length_scale_m: float,
    radial_fraction: object | None = None,
    radial_points: int = 17,
    respect_artery_boundaries: bool = True,
    activity_threshold_fraction: float = 0.0,
    thickness_fraction: float = 0.10,
) -> MechanicalState:
    """Build the full mechanical state from canonical HEMOSPACE P/U/A waves.

    Canonical path pressure is stored in mmHg by the authoritative PWDB exporter
    and is converted explicitly to pascals. Pressure is never inferred from
    Crocco closure.
    """
    required={"P","U","A"}; available=set(path_waves_field.signals)
    if not required<=available:
        raise ValueError(f"path_waves_field must contain P/U/A; missing {sorted(required-available)!r}")
    field=lift_path(
        path_waves_field,radial_fraction=radial_fraction,radial_points=radial_points,
        respect_artery_boundaries=respect_artery_boundaries,
    )
    pressure_pa=np.asarray(path_waves_field.matrix("P"),dtype=float)*MMHG_TO_PA
    return mechanical_state(
        field,pressure_pa,time_s,density_kg_m3,dynamic_viscosity_pa_s,
        velocity_scale_m_s=velocity_scale_m_s,length_scale_m=length_scale_m,
        activity_threshold_fraction=activity_threshold_fraction,thickness_fraction=thickness_fraction,
    )


def mechanical_state_from_hemospace(
    hemospace_session: object,
    subject_id: str,
    path_name: str,
    time_s: object,
    density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    *,
    velocity_scale_m_s: float,
    length_scale_m: float,
    radial_fraction: object | None = None,
    radial_points: int = 17,
    respect_artery_boundaries: bool = True,
    activity_threshold_fraction: float = 0.0,
    thickness_fraction: float = 0.10,
) -> MechanicalState:
    """Read canonical P/U/A path waves and assemble the mechanical state."""
    raw=path_waves_from_hemospace(hemospace_session,subject_id,path_name,signals=("P","U","A"))
    return mechanical_state_from_path_waves(
        raw,time_s,density_kg_m3,dynamic_viscosity_pa_s,
        velocity_scale_m_s=velocity_scale_m_s,length_scale_m=length_scale_m,
        radial_fraction=radial_fraction,radial_points=radial_points,
        respect_artery_boundaries=respect_artery_boundaries,
        activity_threshold_fraction=activity_threshold_fraction,thickness_fraction=thickness_fraction,
    )


__all__=[
    "MMHG_TO_PA","lift_hemospace_path","mechanical_state_from_hemospace",
    "mechanical_state_from_path_waves","path_waves_from_hemospace",
]
