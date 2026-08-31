from __future__ import annotations

import numpy as np

from vascuquest.disease.solver import SolverOptions, ThinWallLaw, build_network, wall_eh_n_per_m


def test_pwdb_wall_law_round_trip(one_segment_baseline) -> None:
    options = SolverOptions(target_dx_m=0.05, minimum_cells_per_segment=2)
    network = build_network(one_segment_baseline, options)
    mesh = network.mesh("1")
    pressure = ThinWallLaw.pressure_pa(
        mesh.reference_area_m2,
        mesh.reference_area_m2,
        mesh.beta_pa,
        one_segment_baseline.diastolic_pressure_pa,
    )
    restored = ThinWallLaw.area_from_pressure(
        pressure,
        mesh.reference_area_m2,
        mesh.beta_pa,
        one_segment_baseline.diastolic_pressure_pa,
    )
    assert np.allclose(pressure, one_segment_baseline.diastolic_pressure_pa)
    assert np.allclose(restored, mesh.reference_area_m2)
    assert np.all(wall_eh_n_per_m(one_segment_baseline, 0.005) > 0)
    assert np.all(mesh.source_gamma_pa_s_per_m == 0.0)


def test_tapered_reference_state_has_uniform_reference_pressure(one_segment_baseline) -> None:
    segment = one_segment_baseline.segments[0]
    tapered = type(segment)(
        segment_id=segment.segment_id,
        inlet_node=segment.inlet_node,
        outlet_node=segment.outlet_node,
        length_m=segment.length_m,
        inlet_radius_m=0.0055,
        outlet_radius_m=0.0045,
        peripheral_compliance_m3_per_pa=segment.peripheral_compliance_m3_per_pa,
        peripheral_resistance_pa_s_per_m3=segment.peripheral_resistance_pa_s_per_m3,
    )
    state = type(one_segment_baseline)(
        dataset_identity=one_segment_baseline.dataset_identity,
        canonical_subject_id=one_segment_baseline.canonical_subject_id,
        age_years=one_segment_baseline.age_years,
        heart_rate_bpm=one_segment_baseline.heart_rate_bpm,
        stroke_volume_ml=one_segment_baseline.stroke_volume_ml,
        lvet_s=one_segment_baseline.lvet_s,
        peak_flow_time_s=one_segment_baseline.peak_flow_time_s,
        reverse_flow_volume_ml=one_segment_baseline.reverse_flow_volume_ml,
        diastolic_pressure_pa=one_segment_baseline.diastolic_pressure_pa,
        mean_pressure_pa=one_segment_baseline.mean_pressure_pa,
        outlet_pressure_pa=one_segment_baseline.outlet_pressure_pa,
        blood_density_kg_per_m3=one_segment_baseline.blood_density_kg_per_m3,
        blood_viscosity_pa_s=one_segment_baseline.blood_viscosity_pa_s,
        momentum_correction_alpha=one_segment_baseline.momentum_correction_alpha,
        systemic_pvr_pa_s_per_m3=one_segment_baseline.systemic_pvr_pa_s_per_m3,
        wall_gamma_b0_g_per_s=one_segment_baseline.wall_gamma_b0_g_per_s,
        wall_gamma_b1_g_cm_per_s=one_segment_baseline.wall_gamma_b1_g_cm_per_s,
        stiffness_k1_g_per_s2_per_cm=one_segment_baseline.stiffness_k1_g_per_s2_per_cm,
        stiffness_k2_per_cm=one_segment_baseline.stiffness_k2_per_cm,
        stiffness_k3_g_per_s2_per_cm=one_segment_baseline.stiffness_k3_g_per_s2_per_cm,
        segments=(tapered,),
        aortic_inflow=one_segment_baseline.aortic_inflow,
        source_configuration_member=one_segment_baseline.source_configuration_member,
        source_geometry_member=one_segment_baseline.source_geometry_member,
    )
    mesh = build_network(state, SolverOptions(target_dx_m=0.02)).mesh("1")
    pressure = ThinWallLaw.pressure_pa(
        mesh.reference_area_m2,
        mesh.reference_area_m2,
        mesh.beta_pa,
        state.diastolic_pressure_pa,
    )
    assert np.allclose(pressure, state.diastolic_pressure_pa)
