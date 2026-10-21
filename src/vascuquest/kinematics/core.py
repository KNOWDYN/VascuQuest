"""Exact axisymmetric kinematic lift of path-resolved PWDB mean-flow variables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from vascuquest.errors import AdmissibilityError

from .derivatives import DerivativeQuality, spatial_derivatives


LIFT_METHOD_ID = "vascuquest:kinematics:exact-axisymmetric-parabolic-lift-v1"
WALL_VORTICITY_METHOD_ID = "vascuquest:kinematics:exact-wall-vorticity-v1"

_ASSUMPTIONS = (
    "axisymmetric flow",
    "zero swirl velocity",
    "incompressible kinematics",
    "parabolic axial velocity profile whose cross-sectional mean is the source U(z,t)",
    "strictly positive circular-equivalent lumen radius R=sqrt(A/pi)",
)


def _readonly(values: object) -> np.ndarray:
    result = np.asarray(values, dtype=float).copy()
    result.setflags(write=False)
    return result


def _path_time(values: object, name: str, n_path: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim == 1:
        result = result[:, None]
    if result.ndim != 2 or result.shape[0] != n_path:
        raise AdmissibilityError(f"{name} must have shape (path_position, time) or (path_position,)")
    if not np.all(np.isfinite(result)):
        raise AdmissibilityError(f"{name} must contain only finite values")
    return result


def radius_from_area(area_m2: object) -> np.ndarray:
    area = np.asarray(area_m2, dtype=float)
    if not np.all(np.isfinite(area)) or np.any(area <= 0):
        raise AdmissibilityError("luminal area must be finite and strictly positive")
    return _readonly(np.sqrt(area / np.pi))


def radial_grid(points: int = 17) -> np.ndarray:
    if points < 5:
        raise ValueError("radial grid requires at least five points including axis and wall")
    return _readonly(np.linspace(0.0, 1.0, int(points)))


@dataclass(frozen=True, slots=True)
class WallVorticityResult:
    """Exact wall-vorticity lift evaluated at stored path/time samples."""

    distance_m: np.ndarray
    mean_velocity_m_s: np.ndarray
    area_m2: np.ndarray
    radius_m: np.ndarray
    azimuthal_vorticity_s_1: np.ndarray
    axial_shear_contribution_s_1: np.ndarray
    radial_motion_contribution_s_1: np.ndarray
    derivative_quality: DerivativeQuality
    method_id: str = WALL_VORTICITY_METHOD_ID
    evidence: str = "DERIVED"
    assumptions: tuple[str, ...] = _ASSUMPTIONS


@dataclass(frozen=True, slots=True)
class KinematicLift:
    """Complete axisymmetric velocity/vorticity field on a normalized radial grid.

    Field arrays use dimensions ``(path_position, time, radial_fraction)``.
    Under the declared source axioms the continuum lift is exact; only the
    pathwise derivatives of discretely stored U and A are numerical.
    """

    distance_m: np.ndarray
    radial_fraction: np.ndarray
    mean_velocity_m_s: np.ndarray
    area_m2: np.ndarray
    radius_m: np.ndarray
    axial_velocity_m_s: np.ndarray
    radial_velocity_m_s: np.ndarray
    azimuthal_vorticity_s_1: np.ndarray
    wall_vorticity_s_1: np.ndarray
    derivative_quality: DerivativeQuality
    derivative_groups: tuple[object, ...] | None
    method_id: str = LIFT_METHOD_ID
    evidence: str = "DERIVED"
    assumptions: tuple[str, ...] = _ASSUMPTIONS
    subject_id: str | None = None
    path_name: str | None = None
    source_artifacts: tuple[str, ...] = ()

    @property
    def dimensions(self) -> tuple[str, str, str]:
        return ("path_position", "time", "radial_fraction")

    @property
    def axial_shear_vorticity_s_1(self) -> np.ndarray:
        q = self.radial_fraction[None, None, :]
        return 4.0 * self.mean_velocity_m_s[:, :, None] * q / self.radius_m[:, :, None]

    @property
    def radial_motion_vorticity_s_1(self) -> np.ndarray:
        return self.azimuthal_vorticity_s_1 - self.axial_shear_vorticity_s_1

    def metadata(self) -> dict[str, object]:
        return {
            "kind": "vascuquest.kinematics.exact_axisymmetric_lift",
            "method_id": self.method_id,
            "evidence": self.evidence,
            "dimensions": list(self.dimensions),
            "shape": list(self.azimuthal_vorticity_s_1.shape),
            "subject_id": self.subject_id,
            "path_name": self.path_name,
            "source_artifacts": list(self.source_artifacts),
            "assumptions": list(self.assumptions),
            "derivative_quality": self.derivative_quality.to_dict(),
        }


def _validated_inputs(
    mean_velocity_m_s: object,
    area_m2: object,
    distance_m: object,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    z = np.asarray(distance_m, dtype=float)
    if z.ndim != 1 or z.size < 3 or not np.all(np.isfinite(z)) or np.any(np.diff(z) <= 0):
        raise AdmissibilityError("distance_m must be finite, strictly increasing, and contain at least three positions")
    u = _path_time(mean_velocity_m_s, "mean_velocity_m_s", z.size)
    area = _path_time(area_m2, "area_m2", z.size)
    if u.shape != area.shape:
        raise AdmissibilityError("mean velocity and area must have identical path/time shape")
    if np.any(area <= 0):
        raise AdmissibilityError("luminal area must be strictly positive")
    radius = np.sqrt(area / np.pi)
    return z, u, area, radius


def wall_vorticity(
    mean_velocity_m_s: object,
    area_m2: object,
    distance_m: object,
    *,
    groups: Sequence[object] | None = None,
) -> WallVorticityResult:
    """Evaluate the exact lifted azimuthal vorticity at the moving wall."""

    z, u, area, radius = _validated_inputs(mean_velocity_m_s, area_m2, distance_m)
    du = spatial_derivatives(u, z, groups=groups)
    dr = spatial_derivatives(radius, z, groups=groups)
    axial = 4.0 * u / radius
    radial = (
        -0.5 * radius * du.second
        - 2.0 * dr.first * du.first
        - u * dr.second
        + 3.0 * u * dr.first**2 / radius
    )
    omega = axial + radial
    return WallVorticityResult(
        distance_m=_readonly(z),
        mean_velocity_m_s=_readonly(u),
        area_m2=_readonly(area),
        radius_m=_readonly(radius),
        azimuthal_vorticity_s_1=_readonly(omega),
        axial_shear_contribution_s_1=_readonly(axial),
        radial_motion_contribution_s_1=_readonly(radial),
        derivative_quality=du.quality,
    )


def lift_axisymmetric(
    mean_velocity_m_s: object,
    area_m2: object,
    distance_m: object,
    *,
    radial_fraction: object | None = None,
    radial_points: int = 17,
    groups: Sequence[object] | None = None,
    subject_id: str | None = None,
    path_name: str | None = None,
    source_artifacts: tuple[str, ...] = (),
) -> KinematicLift:
    """Lift U(z,t), A(z,t) to the exact axisymmetric parabolic velocity/curl field."""

    z, u, area, radius = _validated_inputs(mean_velocity_m_s, area_m2, distance_m)
    if radial_fraction is None:
        q = np.linspace(0.0, 1.0, int(radial_points))
    else:
        q = np.asarray(radial_fraction, dtype=float)
    if (
        q.ndim != 1
        or q.size < 5
        or not np.all(np.isfinite(q))
        or np.any(np.diff(q) <= 0)
        or not np.isclose(q[0], 0.0, atol=1e-14, rtol=0.0)
        or not np.isclose(q[-1], 1.0, atol=1e-14, rtol=0.0)
        or np.any(q < 0.0)
        or np.any(q > 1.0)
    ):
        raise AdmissibilityError("radial_fraction must be strictly increasing from exactly 0 (axis) to 1 (wall)")

    du = spatial_derivatives(u, z, groups=groups)
    dr = spatial_derivatives(radius, z, groups=groups)
    q3 = q[None, None, :]
    r = radius[:, :, None] * q3

    uz = 2.0 * u[:, :, None] * (1.0 - q3**2)
    ur = (
        -r * du.first[:, :, None]
        + (r**3 / (2.0 * radius[:, :, None] ** 2)) * du.first[:, :, None]
        - (r**3 * u[:, :, None] / radius[:, :, None] ** 3) * dr.first[:, :, None]
    )
    omega = (
        4.0 * r * u[:, :, None] / radius[:, :, None] ** 2
        - r * du.second[:, :, None]
        + (r**3 / (2.0 * radius[:, :, None] ** 2)) * du.second[:, :, None]
        - 2.0 * r**3 * dr.first[:, :, None] * du.first[:, :, None] / radius[:, :, None] ** 3
        - r**3 * u[:, :, None] * dr.second[:, :, None] / radius[:, :, None] ** 3
        + 3.0 * r**3 * u[:, :, None] * dr.first[:, :, None] ** 2 / radius[:, :, None] ** 4
    )

    group_tuple = None if groups is None else tuple(groups)
    return KinematicLift(
        distance_m=_readonly(z),
        radial_fraction=_readonly(q),
        mean_velocity_m_s=_readonly(u),
        area_m2=_readonly(area),
        radius_m=_readonly(radius),
        axial_velocity_m_s=_readonly(uz),
        radial_velocity_m_s=_readonly(ur),
        azimuthal_vorticity_s_1=_readonly(omega),
        wall_vorticity_s_1=_readonly(omega[:, :, -1]),
        derivative_quality=du.quality,
        derivative_groups=group_tuple,
        subject_id=subject_id,
        path_name=path_name,
        source_artifacts=tuple(source_artifacts),
    )


def lift_path(
    path_waves: object,
    *,
    radial_fraction: object | None = None,
    radial_points: int = 17,
    respect_artery_boundaries: bool = True,
) -> KinematicLift:
    """Lift a HEMOSPACE ``PathWaveField`` containing source U and A waves."""

    if not hasattr(path_waves, "matrix"):
        raise TypeError("path_waves must expose the HEMOSPACE PathWaveField contract")
    groups = tuple(path_waves.artery) if respect_artery_boundaries else None
    return lift_axisymmetric(
        path_waves.matrix("U"),
        path_waves.matrix("A"),
        path_waves.distance_m,
        radial_fraction=radial_fraction,
        radial_points=radial_points,
        groups=groups,
        subject_id=path_waves.subject_id,
        path_name=path_waves.path_name,
        source_artifacts=tuple(path_waves.source_artifacts),
    )


near_wall_vorticity = wall_vorticity

__all__ = [
    "KinematicLift",
    "LIFT_METHOD_ID",
    "WALL_VORTICITY_METHOD_ID",
    "WallVorticityResult",
    "lift_axisymmetric",
    "lift_path",
    "near_wall_vorticity",
    "radial_grid",
    "radius_from_area",
    "wall_vorticity",
]
