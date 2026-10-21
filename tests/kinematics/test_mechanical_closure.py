import numpy as np

from vascuquest.kinematics import (
    certify_mechanical_state,
    closure_comparison,
    lift_axisymmetric,
    mechanical_state,
    spatial_derivatives,
)


RHO = 1050.0
MU = 0.004


def _poiseuille_state(radius_m: float, mean_velocity_m_s: float):
    z = np.linspace(0.0, 0.20, 9)
    time = np.linspace(0.0, 1.0, 5)
    u = np.full((z.size, time.size), mean_velocity_m_s)
    area = np.full_like(u, np.pi * radius_m**2)
    field = lift_axisymmetric(u, area, z, radial_points=65)
    dp_dz = -8.0 * MU * mean_velocity_m_s / radius_m**2
    pressure = (13000.0 + dp_dz * z)[:, None] * np.ones((1, time.size))
    state = mechanical_state(
        field,
        pressure,
        time,
        RHO,
        MU,
        velocity_scale_m_s=0.30,
        length_scale_m=0.004,
        thickness_fraction=0.10,
    )
    return z, time, state


def test_poiseuille_exact_topology_charge_crocco_and_wall_traction():
    _, _, state = _poiseuille_state(0.004, 0.30)

    assert np.nanmax(np.abs(state.topology.q_invariant_s_2)) < 1e-10
    assert np.allclose(state.wall_traction.magnitude_pa, 1.20, atol=1e-12)
    assert np.nanmax(np.abs(state.lamb.charge_identity_residual_s_2)) < 1e-8
    residual = np.sqrt(
        state.crocco.residual_r_m_s2**2 + state.crocco.residual_z_m_s2**2
    )
    assert np.nanmax(residual) < 1e-9

    certificate = certify_mechanical_state(state)
    assert certificate.passed
    assert certificate.charge_identity_max_normalized_residual < 1e-10
    assert certificate.crocco_max_normalized_residual < 1e-10


def test_poiseuille_near_wall_lamb_load_matches_closed_form():
    _, _, state = _poiseuille_state(0.004, 0.30)
    eps = 0.10
    expected = (
        8.0
        * RHO
        * 0.30**2
        * eps**2
        / 15.0
        * (15.0 - 25.0 * eps + 15.0 * eps**2 - 3.0 * eps**3)
    )
    assert np.allclose(state.lamb_load.wall_normal_component_pa, expected, atol=1e-11)
    assert np.allclose(state.lamb_load.wall_normal_absolute_pa, expected, atol=1e-10)


def test_exact_shear_equivalent_poiseuille_pair_is_mechanically_distinct():
    z, time, a = _poiseuille_state(0.004, 0.30)
    _, _, b = _poiseuille_state(0.008, 0.60)

    assert np.allclose(a.wall_traction.magnitude_pa, b.wall_traction.magnitude_pa, atol=1e-12)
    assert np.allclose(
        b.lamb_load.wall_normal_component_pa,
        4.0 * a.lamb_load.wall_normal_component_pa,
        rtol=1e-12,
        atol=1e-12,
    )

    comparison = closure_comparison(
        a,
        b,
        tau_scale_pa=1.20,
        wall_weights=np.ones((z.size, time.size)),
        volume_weights=np.ones(a.q_star.shape),
        epsilon_tau=1e-9,
        epsilon_mechanical=1e-6,
    )
    assert comparison.shear_distance < 1e-12
    assert comparison.mechanical_distance > 0.1
    assert comparison.hydrodynamic_degeneracy is True


def test_mechanical_derivative_qualification_can_require_four_points():
    z = np.linspace(0.0, 1.0, 7)
    values = z**3
    result = spatial_derivatives(
        values,
        z,
        groups=("short", "short", "short", "long", "long", "long", "long"),
        minimum_points=4,
    )
    assert result.valid_mask.tolist() == [False, False, False, True, True, True, True]
    assert np.all(np.isnan(result.first[:3]))
    assert np.all(np.isfinite(result.first[3:]))
