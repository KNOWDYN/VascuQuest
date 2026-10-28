import numpy as np
import pytest

pyva = pytest.importorskip("pyva")
pytest.importorskip("scipy")

from vascuquest.cardioacoustics import (
    CardioacousticSourceSpectrum,
    arterial_mode_spectrum,
    solve_pyva_network,
)
from vascuquest.disease.baseline.model import (
    BaselineCardiovascularState,
    BaselineSegment,
    InflowWaveform,
)
from vascuquest.disease.solver.model import SegmentMesh
from vascuquest.disease.solver.network import NetworkDiscretization
from vascuquest.domain import DatasetIdentity


def _baseline():
    identity = DatasetIdentity("PWDB", "test", "urn:test:cardioacoustics", "v1")
    segment = BaselineSegment("1", 1, 2, 0.1, 0.005, 0.005, 1e-10, 1e8)
    t = np.linspace(0.0, 1.0, 16, endpoint=False)
    inflow = InflowWaveform(t, np.full_like(t, 1e-5), "manufactured")
    return BaselineCardiovascularState(
        dataset_identity=identity,
        canonical_subject_id="1",
        age_years=40,
        heart_rate_bpm=60.0,
        stroke_volume_ml=70.0,
        lvet_s=0.3,
        peak_flow_time_s=0.1,
        reverse_flow_volume_ml=0.0,
        diastolic_pressure_pa=10000.0,
        mean_pressure_pa=12000.0,
        outlet_pressure_pa=9000.0,
        blood_density_kg_per_m3=1060.0,
        blood_viscosity_pa_s=0.004,
        momentum_correction_alpha=1.0,
        systemic_pvr_pa_s_per_m3=1e8,
        wall_gamma_b0_g_per_s=1.0,
        wall_gamma_b1_g_cm_per_s=1.0,
        stiffness_k1_g_per_s2_per_cm=1.0,
        stiffness_k2_per_cm=0.0,
        stiffness_k3_g_per_s2_per_cm=1e6,
        segments=(segment,),
        aortic_inflow=inflow,
        source_configuration_member="manufactured",
        source_geometry_member="manufactured",
    )


def test_single_segment_matched_network_accepts_prescribed_root_pressure():
    baseline = _baseline()
    area = np.pi * 0.005**2
    network = NetworkDiscretization(
        (
            SegmentMesh(
                segment_id="1",
                x_m=np.array([0.05]),
                dx_m=np.array([0.1]),
                reference_area_m2=np.array([area]),
                beta_pa=np.array([2e5]),
                source_gamma_pa_s_per_m=np.array([0.0]),
            ),
        )
    )
    source = CardioacousticSourceSpectrum.from_amplitude_phase(
        [30.0, 60.0], [1.0, 1.0], [0.0, 0.0], source_identity="manufactured"
    )
    solved = solve_pyva_network(baseline, source, network=network)
    root_index = solved.node_ids.index(1)
    assert np.allclose(solved.node_pressure_pa[:, root_index], source.pressure_pa)
    distal_index = solved.node_ids.index(2)
    mode = arterial_mode_spectrum(
        source.frequency_hz,
        area_m2=area,
        beta_pa=2e5,
        gamma_pa_s_per_m=0.0,
        density_kg_per_m3=baseline.blood_density_kg_per_m3,
        viscosity_pa_s=baseline.blood_viscosity_pa_s,
    )
    expected_distal = source.pressure_pa * np.exp(-1j * mode.wavenumber_per_m * 0.1)
    assert np.allclose(solved.node_pressure_pa[:, distal_index], expected_distal, rtol=1e-6, atol=1e-9)
    assert len(solved.cells) == 1
    assert np.all(np.isfinite(solved.cells[0].load.pressure_pa))
