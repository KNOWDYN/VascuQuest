from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.baseline.model import (
    BaselineCardiovascularState,
    BaselineSegment,
    InflowWaveform,
    MMHG_TO_PA,
)
from vascuquest.domain.identity import DatasetIdentity


@pytest.fixture
def vascular_baseline() -> BaselineCardiovascularState:
    """Minimal connected tree carrying the frozen left carotid/femoral paths."""

    topology = (
        ("1", 1, 2, 0.060, 0.018206, 0.018004),
        ("2", 2, 3, 0.020, 0.015799, 0.015799),
        ("15", 3, 4, 0.139, 0.004532, 0.003950),
        ("14", 3, 5, 0.039, 0.015187, 0.015187),
        ("18", 5, 6, 0.052, 0.013472, 0.012235),
        ("27", 6, 7, 0.104, 0.010655, 0.008696),
        ("28", 7, 8, 0.053, 0.007471, 0.007471),
        ("35", 8, 9, 0.010, 0.007226, 0.007226),
        ("37", 9, 10, 0.010, 0.006981, 0.006981),
        ("39", 10, 11, 0.106, 0.006736, 0.006491),
        ("41", 11, 12, 0.010, 0.006369, 0.006124),
        ("42", 12, 13, 0.058, 0.004507, 0.004287),
        ("44", 13, 14, 0.144, 0.003429, 0.003307),
        ("46", 14, 15, 0.443, 0.003062, 0.002327),
    )
    terminal_ids = {"15", "46"}
    segments = tuple(
        BaselineSegment(
            segment_id=segment_id,
            inlet_node=inlet,
            outlet_node=outlet,
            length_m=length,
            inlet_radius_m=rin,
            outlet_radius_m=rout,
            peripheral_compliance_m3_per_pa=(1.0e-9 if segment_id in terminal_ids else 0.0),
            peripheral_resistance_pa_s_per_m3=(1.0e9 if segment_id in terminal_ids else 0.0),
        )
        for segment_id, inlet, outlet, length, rin, rout in topology
    )
    diastolic = 80.0 * MMHG_TO_PA
    inflow = InflowWaveform(
        time_s=np.asarray([0.0, 0.25, 0.50, 0.75]),
        flow_m3_per_s=np.zeros(4),
        source_identity="test:zero-inflow",
    )
    return BaselineCardiovascularState(
        dataset_identity=DatasetIdentity(
            dataset_family="PWDB",
            record_id="3275625",
            persistent_identifier="10.5281/zenodo.3275625",
            schema_version="1",
        ),
        canonical_subject_id="1",
        age_years=50,
        heart_rate_bpm=60.0,
        stroke_volume_ml=70.0,
        lvet_s=0.28,
        peak_flow_time_s=0.08,
        reverse_flow_volume_ml=0.0,
        diastolic_pressure_pa=diastolic,
        mean_pressure_pa=95.0 * MMHG_TO_PA,
        outlet_pressure_pa=diastolic,
        blood_density_kg_per_m3=1050.0,
        blood_viscosity_pa_s=0.004,
        momentum_correction_alpha=1.1,
        systemic_pvr_pa_s_per_m3=1.0e9,
        wall_gamma_b0_g_per_s=0.0,
        wall_gamma_b1_g_cm_per_s=0.0,
        stiffness_k1_g_per_s2_per_cm=1.0,
        stiffness_k2_per_cm=-1.0,
        stiffness_k3_g_per_s2_per_cm=1.0e6,
        segments=segments,
        aortic_inflow=inflow,
        source_configuration_member="synthetic_model_configs.csv",
        source_geometry_member="synthetic_geo.csv",
    )
