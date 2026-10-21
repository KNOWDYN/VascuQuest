"""HEMOSPACE source bridge for exact kinematic reconstruction."""
from __future__ import annotations

from vascuquest.hemospace.path import PathWaveField, path_waves

from .core import KinematicLift, lift_path


def path_waves_from_hemospace(
    hemospace_session: object,
    subject_id: str,
    path_name: str,
    *,
    signals: tuple[str, ...] = ("U", "A"),
) -> PathWaveField:
    """Read raw aligned path waves from an open HEMOSPACE session.

    The bridge stays inside VascuQuest and uses HEMOSPACE's bound canonical
    artifact resolver; callers do not need to handle large path artifacts.
    """
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
    raw = path_waves_from_hemospace(
        hemospace_session,
        subject_id,
        path_name,
        signals=("U", "A"),
    )
    return lift_path(
        raw,
        radial_fraction=radial_fraction,
        radial_points=radial_points,
        respect_artery_boundaries=respect_artery_boundaries,
    )


__all__ = ["lift_hemospace_path", "path_waves_from_hemospace"]
