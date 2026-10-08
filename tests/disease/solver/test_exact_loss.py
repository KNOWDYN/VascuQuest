from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.solver.exact_loss import exact_local_pressure_loss_flow


def _step(q, dt, *, linear=8.0e6, quadratic=3.0e11):
    return exact_local_pressure_loss_flow(
        q,
        2.5e-5,
        linear,
        quadratic,
        density_kg_per_m3=1060.0,
        dt_s=dt,
    )


def test_exact_loss_zero_and_zero_time_are_noops() -> None:
    q = np.asarray([-2e-5, 0.0, 3e-5])
    np.testing.assert_array_equal(_step(q, 0.0), q)
    result = exact_local_pressure_loss_flow(
        q,
        np.full_like(q, 2.5e-5),
        0.0,
        0.0,
        density_kg_per_m3=1060.0,
        dt_s=1.0,
    )
    np.testing.assert_array_equal(result, q)


def test_exact_loss_preserves_sign_and_is_dissipative() -> None:
    q = np.asarray([-4e-5, -1e-7, 0.0, 1e-7, 4e-5])
    result = _step(q, 0.25)
    np.testing.assert_array_equal(np.sign(result), np.sign(q))
    assert np.all(np.abs(result) <= np.abs(q))
    assert np.all(np.abs(result[q != 0.0]) < np.abs(q[q != 0.0]))


def test_exact_loss_has_semigroup_property() -> None:
    q = np.linspace(-5e-5, 5e-5, 17)
    once = _step(q, 0.37)
    split = _step(_step(q, 0.11), 0.26)
    np.testing.assert_allclose(split, once, rtol=2e-13, atol=1e-18)


def test_exact_loss_linear_and_quadratic_limits() -> None:
    q = np.asarray([-3e-5, 2e-5])
    area = 2.5e-5
    rho = 1060.0
    dt = 0.2
    linear = 8.0e6
    result_linear = exact_local_pressure_loss_flow(
        q, area, linear, 0.0, density_kg_per_m3=rho, dt_s=dt
    )
    expected_linear = q * np.exp(-(area / rho * linear) * dt)
    np.testing.assert_allclose(result_linear, expected_linear, rtol=2e-14, atol=1e-20)

    quadratic = 3.0e11
    result_quadratic = exact_local_pressure_loss_flow(
        q, area, 0.0, quadratic, density_kg_per_m3=rho, dt_s=dt
    )
    b = area / rho * quadratic
    expected_quadratic = np.sign(q) * np.abs(q) / (1.0 + b * np.abs(q) * dt)
    np.testing.assert_allclose(result_quadratic, expected_quadratic, rtol=2e-14, atol=1e-20)


def test_exact_loss_rejects_nonzero_inertance() -> None:
    with pytest.raises(ValueError, match="zero excess inertance"):
        exact_local_pressure_loss_flow(
            1e-5,
            2.5e-5,
            1.0,
            1.0,
            density_kg_per_m3=1060.0,
            dt_s=0.1,
            inertance_density_pa_s2_per_m4=1.0,
        )
