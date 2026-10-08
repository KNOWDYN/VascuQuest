import numpy as np
import pytest
from vascuquest.domain import Coordinate, DatasetIdentity, EvidenceClass, MeasurementSite, QuantityDefinition, SubjectKey, Waveform
from vascuquest.mechanics import area_compliance, area_distensibility, area_strain, bramwell_hill_wave_speed


def _wave(name, unit, values, t, subject, location, dimension):
    q = QuantityDefinition(name, name, name, "waveform", subject.dataset_identity.schema_version, dimension, unit)
    return Waveform(subject.dataset_identity, q, values, f"prov:{name}", ("time",), (Coordinate("time", t, "s"),), subject=subject, location=location, evidence=EvidenceClass.SOURCE)


def test_pressure_area_mechanics_known_waveforms():
    identity = DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "v1")
    subject = SubjectKey(identity, "1")
    location = MeasurementSite("AorticRoot")
    t = np.linspace(0.0, 1.0, 256, endpoint=False)
    pressure = _wave("pressure", "mmHg", 100.0 + 20.0*np.sin(2*np.pi*t), t, subject, location, "pressure")
    area = _wave("area", "m^2", 1e-4*(1.0 + 0.08*np.sin(2*np.pi*t)), t, subject, location, "area")
    assert area_strain(area).values > 0
    assert area_compliance(pressure, area).values > 0
    assert area_distensibility(pressure, area).values > 0
    assert bramwell_hill_wave_speed(pressure, area).values > 0


def test_no_silent_resampling():
    identity = DatasetIdentity("PWDB", "3275625", "10.5281/zenodo.3275625", "v1")
    subject = SubjectKey(identity, "1"); location = MeasurementSite("AorticRoot")
    t = np.linspace(0.0, 1.0, 64, endpoint=False)
    p = _wave("p", "mmHg", np.ones(64)*100, t, subject, location, "pressure")
    a = _wave("a", "m^2", np.ones(63)*1e-4, t[:-1], subject, location, "area")
    with pytest.raises(Exception): area_compliance(p, a)
