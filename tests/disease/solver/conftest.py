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
def one_segment_baseline() -> BaselineCardiovascularState:
    diastolic = 80.0 * MMHG_TO_PA
    inflow = InflowWaveform(
        time_s=np.asarray([0.0, 0.25, 0.50, 0.75]),
        flow_m3_per_s=np.zeros(4),
        source_identity="test:zero-inflow",
    )
    segment = BaselineSegment(
        segment_id="1",
        inlet_node=1,
        outlet_node=2,
        length_m=0.10,
        inlet_radius_m=0.005,
        outlet_radius_m=0.005,
        peripheral_compliance_m3_per_pa=1.0e-9,
        peripheral_resistance_pa_s_per_m3=1.0e9,
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
        segments=(segment,),
        aortic_inflow=inflow,
        source_configuration_member="synthetic_model_configs.csv",
        source_geometry_member="synthetic_geo.csv",
    )
