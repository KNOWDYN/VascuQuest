import math
import numpy as np
import pytest

pytest.importorskip("scipy")

from vascuquest.cardioacoustics import (
    CardioacousticSourceSpectrum,
    arterial_mode_spectrum,
    reflection_coefficient,
    wall_shear_traction_from_flow,
)


def test_source_amplitude_phase_roundtrip():
    f = np.array([20.0, 40.0, 80.0])
    amplitude = np.array([2.0, 1.0, 0.5])
    phase = np.array([0.0, 0.25, -0.5])
    source = CardioacousticSourceSpectrum.from_amplitude_phase(
        f, amplitude, phase, source_identity="manufactured"
    )
    assert np.allclose(source.amplitude_pa, amplitude)
    assert np.allclose(source.phase_rad, phase)


def test_lossless_mode_reduces_to_thin_wall_wave_speed():
    f = np.array([20.0, 50.0, 100.0])
    area = math.pi * (0.01 ** 2)
    beta = 2.0e5
    rho = 1060.0
    mode = arterial_mode_spectrum(
        f,
        area_m2=area,
        beta_pa=beta,
        gamma_pa_s_per_m=0.0,
        density_kg_per_m3=rho,
        viscosity_pa_s=0.004,
        viscous_blood=False,
    )
    expected_c = math.sqrt(beta / (2.0 * rho))
    assert np.allclose(mode.phase_speed_m_per_s, expected_c, rtol=1e-12)
    assert np.allclose(mode.attenuation_neper_per_m, 0.0, atol=1e-12)
    expected_z = rho * expected_c / area
    assert np.allclose(mode.characteristic_impedance_pa_s_per_m3.real, expected_z, rtol=1e-12)


def test_stiffening_changes_the_same_frequency_channel_without_changing_source():
    f = np.array([30.0, 60.0, 120.0])
    area = math.pi * (0.008 ** 2)
    kwargs = dict(
        frequency_hz=f,
        area_m2=area,
        gamma_pa_s_per_m=2.0e5,
        density_kg_per_m3=1060.0,
        viscosity_pa_s=0.004,
    )
    healthy = arterial_mode_spectrum(beta_pa=1.5e5, **kwargs)
    stiff = arterial_mode_spectrum(beta_pa=6.0e5, **kwargs)
    assert np.all(stiff.phase_speed_m_per_s > healthy.phase_speed_m_per_s)
    assert not np.allclose(
        stiff.characteristic_impedance_pa_s_per_m3,
        healthy.characteristic_impedance_pa_s_per_m3,
    )


def test_reflection_is_zero_for_identical_impedance():
    z = np.array([1.0 + 0.2j, 2.0 + 0.1j])
    assert np.allclose(reflection_coefficient(z, z), 0.0)


def test_low_womersley_shear_recovers_poiseuille_limit():
    f = np.array([0.001])
    radius = 1e-3
    mu = 0.004
    rho = 1060.0
    q = np.array([1e-9 + 0j])
    traction = wall_shear_traction_from_flow(
        f,
        q,
        radius_m=radius,
        density_kg_per_m3=rho,
        viscosity_pa_s=mu,
    )
    expected = 4.0 * mu * q[0] / (math.pi * radius ** 3)
    assert traction[0] == pytest.approx(expected, rel=2e-3)
