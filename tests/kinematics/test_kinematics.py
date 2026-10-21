import numpy as np
import pytest

from vascuquest.errors import AdmissibilityError
from vascuquest.kinematics import (
    certify_lift,
    lift_axisymmetric,
    spatial_derivatives,
    wall_vorticity,
)


def test_rigid_uniform_tube_recovers_parabolic_vorticity_exactly():
    z = np.linspace(0.0, 0.20, 9)
    t = np.linspace(0.0, 1.0, 16, endpoint=False)
    radius = 0.004
    mean = 0.35 + 0.08 * np.sin(2.0 * np.pi * t)
    u = np.repeat(mean[None, :], z.size, axis=0)
    area = np.full_like(u, np.pi * radius**2)

    field = lift_axisymmetric(u, area, z, radial_points=33)
    q = field.radial_fraction[None, None, :]
    expected = 4.0 * u[:, :, None] * q / radius

    assert np.allclose(field.radial_velocity_m_s, 0.0, atol=1e-12)
    assert np.allclose(field.azimuthal_vorticity_s_1, expected, atol=1e-10)
    assert np.allclose(field.wall_vorticity_s_1, 4.0 * u / radius, atol=1e-10)

    wall = wall_vorticity(u, area, z)
    assert np.allclose(wall.radial_motion_contribution_s_1, 0.0, atol=1e-12)
    assert np.allclose(wall.azimuthal_vorticity_s_1, 4.0 * u / radius, atol=1e-10)


def test_travelling_compliant_tube_satisfies_continuity_and_wall_motion():
    z = np.linspace(0.0, 0.20, 21)
    t = np.linspace(0.0, 0.40, 31)
    wave_speed = 0.20
    slope = 0.001
    radius = 0.004 + slope * (z[:, None] - wave_speed * t[None, :])
    u = np.full_like(radius, wave_speed)
    area = np.pi * radius**2

    field = lift_axisymmetric(u, area, z, radial_points=33)
    certificate = certify_lift(field, time_s=t)

    assert certificate.passed_structural_checks
    assert certificate.time_certificate_available
    assert certificate.continuity_max_abs is not None
    assert certificate.wall_motion_max_abs_error is not None
    assert certificate.continuity_max_abs < 1e-11
    assert certificate.wall_motion_max_abs_error < 1e-11
    assert np.allclose(field.radial_velocity_m_s[:, :, -1], -wave_speed * slope, atol=1e-12)


def test_wall_vorticity_matches_closed_form_for_quadratic_U_and_linear_R():
    z = np.linspace(0.0, 1.0, 17)
    u = 0.30 + 0.20 * z + 0.10 * z**2
    radius = 0.005 + 0.001 * z
    area = np.pi * radius**2

    result = wall_vorticity(u, area, z)
    uz = 0.20 + 0.20 * z
    uzz = np.full_like(z, 0.20)
    rz = 0.001
    expected = (
        4.0 * u / radius
        - 0.5 * radius * uzz
        - 2.0 * rz * uz
        + 3.0 * u * rz**2 / radius
    )

    assert np.allclose(result.azimuthal_vorticity_s_1[:, 0], expected, rtol=1e-10, atol=1e-10)


def test_derivative_contract_refuses_short_anatomical_runs():
    z = np.linspace(0.0, 1.0, 5)
    values = z**2
    with pytest.raises(AdmissibilityError, match="at least three stored path positions"):
        spatial_derivatives(values, z, groups=("a", "a", "b", "b", "b"))
