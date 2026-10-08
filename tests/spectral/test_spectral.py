import numpy as np
import pytest
from vascuquest.domain import Coordinate, DatasetIdentity, EvidenceClass, MeasurementSite, QuantityDefinition, SubjectKey, Waveform
from vascuquest.spectral import harmonic_amplitude, impedance, stft_magnitude, wave_intensity

pytest.importorskip("scipy")


def _wave(name, unit, values, t, subject, location, dimension):
    q = QuantityDefinition(name, name, name, "waveform", subject.dataset_identity.schema_version, dimension, unit)
    return Waveform(subject.dataset_identity, q, values, f"prov:{name}", ("time",), (Coordinate("time", t, "s"),), subject=subject, location=location, evidence=EvidenceClass.SOURCE)


def test_known_first_harmonic_and_impedance():
    identity = DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "v1")
    subject = SubjectKey(identity, "1"); location = MeasurementSite("AorticRoot")
    t = np.linspace(0.0, 1.0, 256, endpoint=False)
    p = _wave("pressure", "Pa", 10000.0 + 2000.0*np.sin(2*np.pi*t), t, subject, location, "pressure")
    q = _wave("flow", "m^3/s", 5e-5 + 2e-5*np.sin(2*np.pi*t), t, subject, location, "flow")
    u = _wave("velocity", "m/s", 0.5 + 0.2*np.sin(2*np.pi*t), t, subject, location, "velocity")
    amps = harmonic_amplitude(p, n_harmonics=3)
    assert amps.values[0] == pytest.approx(2000.0, rel=1e-10)
    zmag, _ = impedance(p, q, n_harmonics=1)
    assert zmag.values[0] == pytest.approx(1e8, rel=1e-10)
    assert stft_magnitude(p, nperseg=64).values.ndim == 2
    net, forward, backward = wave_intensity(p, u, wave_speed_m_s=5.0)
    assert net.values.shape == forward.values.shape == backward.values.shape == p.values.shape
