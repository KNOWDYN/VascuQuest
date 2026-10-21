"""Machine-verifiable numerical certificate for the exact kinematic lift."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vascuquest.errors import AdmissibilityError

from .core import KinematicLift
from .derivatives import spatial_derivatives


@dataclass(frozen=True, slots=True)
class KinematicCertificate:
    qualified_path_points: int
    masked_path_points: int
    mean_velocity_max_abs_error: float
    axis_radial_velocity_max_abs: float
    axis_vorticity_max_abs: float
    wall_axial_velocity_max_abs: float
    divergence_max_abs: float
    curl_max_abs_error: float
    continuity_max_abs: float | None
    wall_motion_max_abs_error: float | None
    passed_structural_checks: bool
    time_certificate_available: bool
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "qualified_path_points": self.qualified_path_points,
            "masked_path_points": self.masked_path_points,
            "mean_velocity_max_abs_error": self.mean_velocity_max_abs_error,
            "axis_radial_velocity_max_abs": self.axis_radial_velocity_max_abs,
            "axis_vorticity_max_abs": self.axis_vorticity_max_abs,
            "wall_axial_velocity_max_abs": self.wall_axial_velocity_max_abs,
            "divergence_max_abs": self.divergence_max_abs,
            "curl_max_abs_error": self.curl_max_abs_error,
            "continuity_max_abs": self.continuity_max_abs,
            "wall_motion_max_abs_error": self.wall_motion_max_abs_error,
            "passed_structural_checks": self.passed_structural_checks,
            "time_certificate_available": self.time_certificate_available,
            "warnings": list(self.warnings),
        }


def _max_abs(values: np.ndarray) -> float:
    flat = np.asarray(values, dtype=float).reshape(-1)
    finite = flat[np.isfinite(flat)]
    return float(np.max(np.abs(finite))) if finite.size else 0.0


def certify_lift(
    field: KinematicLift,
    *,
    time_s: object | None = None,
    rtol: float = 2e-2,
    atol: float = 1e-9,
) -> KinematicCertificate:
    """Independently check discrete identities implied by the exact lift.

    The continuum identities are exact. This certificate checks the returned
    discretized arrays using independent quadrature and finite-difference curl/
    divergence evaluations. It therefore measures implementation/discretization
    consistency, not model-form uncertainty. Anatomically under-resolved path
    runs remain masked and are excluded from derivative-dependent residuals.
    """

    q = np.asarray(field.radial_fraction, dtype=float)
    z = np.asarray(field.distance_m, dtype=float)
    u = np.asarray(field.mean_velocity_m_s, dtype=float)
    radius = np.asarray(field.radius_m, dtype=float)
    uz = np.asarray(field.axial_velocity_m_s, dtype=float)
    ur = np.asarray(field.radial_velocity_m_s, dtype=float)
    omega = np.asarray(field.azimuthal_vorticity_s_1, dtype=float)
    valid = np.asarray(field.valid_path_mask, dtype=bool)
    groups = field.derivative_groups

    reconstructed_mean = 2.0 * np.trapezoid(uz * q[None, None, :], x=q, axis=2)
    mean_error = _max_abs(reconstructed_mean - u)
    axis_ur = _max_abs(ur[valid, :, 0])
    axis_omega = _max_abs(omega[valid, :, 0])
    wall_uz = _max_abs(uz[:, :, -1])

    radius3 = radius[:, :, None]
    q3 = q[None, None, :]
    rz = spatial_derivatives(radius, z, groups=groups).first[:, :, None]

    duz_dq = np.gradient(uz, q, axis=2, edge_order=2)
    dur_dq = np.gradient(ur, q, axis=2, edge_order=2)
    duz_dz_q = spatial_derivatives(uz, z, groups=groups).first
    dur_dz_q = spatial_derivatives(ur, z, groups=groups).first
    transform = q3 * rz / radius3
    duz_dz_r = duz_dz_q - transform * duz_dq
    dur_dz_r = dur_dz_q - transform * dur_dq
    duz_dr = duz_dq / radius3
    curl_numeric = dur_dz_r - duz_dr
    curl_error = _max_abs((curl_numeric - omega)[valid])

    physical_r = q3 * radius3
    r_ur = physical_r * ur
    d_rur_dq = np.gradient(r_ur, q, axis=2, edge_order=2)
    radial_divergence = d_rur_dq[:, :, 1:] / (q3[:, :, 1:] * radius3**2)
    divergence = radial_divergence + duz_dz_r[:, :, 1:]
    divergence_error = _max_abs(divergence[valid])

    structural_scale = max(
        1.0,
        _max_abs((u / radius)[valid]),
        _max_abs(spatial_derivatives(u, z, groups=groups).first[valid]),
    )
    passed = (
        mean_error <= atol + rtol * max(1.0, _max_abs(u))
        and axis_ur <= atol + rtol * max(1.0, _max_abs(ur[valid]))
        and axis_omega <= atol + rtol * max(1.0, _max_abs(omega[valid]))
        and wall_uz <= atol + rtol * max(1.0, _max_abs(uz))
        and divergence_error <= atol + rtol * structural_scale
        and curl_error <= atol + rtol * max(1.0, _max_abs(omega[valid]))
    )

    continuity_error: float | None = None
    wall_motion_error: float | None = None
    warnings = list(field.derivative_quality.warnings)
    if time_s is not None:
        t = np.asarray(time_s, dtype=float)
        if t.ndim != 1 or t.size != u.shape[1] or t.size < 3:
            raise AdmissibilityError(
                "time_s must be a finite vector aligned with the field time dimension and contain at least three samples"
            )
        if not np.all(np.isfinite(t)) or np.any(np.diff(t) <= 0):
            raise AdmissibilityError("time_s must be finite and strictly increasing")
        rt = np.gradient(radius, t, axis=1, edge_order=2)
        du = spatial_derivatives(u, z, groups=groups).first
        dr = spatial_derivatives(radius, z, groups=groups).first
        continuity = rt + u * dr + 0.5 * radius * du
        continuity_error = _max_abs(continuity[valid])
        wall_motion_error = _max_abs((ur[:, :, -1] - rt)[valid])
    else:
        warnings.append(
            "time_s was not supplied; the optional source-continuity and u_r(R)=R_t numerical certificate was not evaluated"
        )

    return KinematicCertificate(
        qualified_path_points=int(np.count_nonzero(valid)),
        masked_path_points=int(valid.size - np.count_nonzero(valid)),
        mean_velocity_max_abs_error=mean_error,
        axis_radial_velocity_max_abs=axis_ur,
        axis_vorticity_max_abs=axis_omega,
        wall_axial_velocity_max_abs=wall_uz,
        divergence_max_abs=divergence_error,
        curl_max_abs_error=curl_error,
        continuity_max_abs=continuity_error,
        wall_motion_max_abs_error=wall_motion_error,
        passed_structural_checks=bool(passed),
        time_certificate_available=time_s is not None,
        warnings=tuple(dict.fromkeys(warnings)),
    )


__all__ = ["KinematicCertificate", "certify_lift"]
