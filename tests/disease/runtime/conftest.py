from __future__ import annotations

import numpy as np
import pytest

from vascuquest.disease.baseline.model import (
    BaselineCardiovascularState,
    BaselineSegment,
    InflowWaveform,
    MMHG_TO_PA,
)
from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import DiseasePopulationRequest, DiseaseRunIdentity
from vascuquest.disease.physics.model import DiseasePhysicsModel
from vascuquest.disease.runtime.dataset import RuntimeDiseaseDataset
from vascuquest.disease.runtime.identity import runtime_dataset_identity
from vascuquest.disease.runtime.materialize import RuntimeSubjectState
from vascuquest.disease.runtime.quantities import (
    canonical_quantity,
    runtime_quantity_statuses,
)
from vascuquest.disease.solver.model import (
    ForwardSolution,
    SegmentSolution,
    SolverDiagnostics,
    SolverOptions,
)
from vascuquest.disease.solver.network import build_network
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.result import ScientificResult, ValidityState, ValueState
from vascuquest.domain.subject import VirtualSubject
from vascuquest.provenance import ProvenanceBuilder


@pytest.fixture
def runtime_dataset() -> RuntimeDiseaseDataset:
    parent_identity = DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )
    diastolic = 80.0 * MMHG_TO_PA
    baseline = BaselineCardiovascularState(
        dataset_identity=parent_identity,
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
        segments=(
            BaselineSegment(
                segment_id="1",
                inlet_node=1,
                outlet_node=2,
                length_m=0.10,
                inlet_radius_m=0.005,
                outlet_radius_m=0.005,
                peripheral_compliance_m3_per_pa=1.0e-9,
                peripheral_resistance_pa_s_per_m3=1.0e9,
            ),
        ),
        aortic_inflow=InflowWaveform(
            time_s=np.asarray([0.0, 0.5]),
            flow_m3_per_s=np.zeros(2),
            source_identity="synthetic:Q",
        ),
        source_configuration_member="synthetic_model_configs.csv",
        source_geometry_member="synthetic_geo.csv",
    )
    spec = specification("large_artery_stiffening", {"target_cfpwv_m_per_s": 12.0})
    request = DiseasePopulationRequest(1, 50, spec, 0)
    run_identity = DiseaseRunIdentity(parent_identity, ("1",), request)
    identity = runtime_dataset_identity(run_identity)
    options = SolverOptions(target_dx_m=0.05, minimum_cells_per_segment=2)
    network = build_network(baseline, options)
    physics = DiseasePhysicsModel(
        baseline=baseline,
        specification=spec,
        network=network,
        pressure_losses=(),
        modified_segment_ids=(),
        assumptions=("synthetic test",),
        citations=("doi:10.1152/ajpheart.00218.2019",),
    )
    mesh = network.mesh("1")
    area = np.vstack((mesh.reference_area_m2, mesh.reference_area_m2))
    flow = np.zeros_like(area)
    pressure = np.full_like(area, diastolic)
    solution = ForwardSolution(
        time_s=np.asarray([0.0, 1.0]),
        segments=(
            SegmentSolution(
                segment_id="1",
                x_m=mesh.x_m,
                area_m2=area,
                flow_m3_per_s=flow,
                pressure_pa=pressure,
            ),
        ),
        diagnostics=SolverDiagnostics(
            cycles_completed=3,
            periodicity_error=0.0,
            converged=True,
            minimum_area_ratio=1.0,
            maximum_cfl=0.1,
            maximum_diffusion_number=0.0,
            terminal_mass_balance_relative_error=0.0,
        ),
    )
    subject = VirtualSubject(SubjectKey(identity, "1"))
    provenance = ProvenanceBuilder(identity).build(
        evidence=EvidenceClass.MODELLED,
        validity=ValidityState.NOT_EVALUATED,
        value_state=ValueState.PRESENT,
        subject=subject.key,
        method_id="test-runtime",
        parameters={"parent_subject": "1"},
        output_identity="age@subject:1",
    )
    age = ScientificResult(
        dataset_identity=identity,
        quantity=canonical_quantity("age"),
        values=50,
        provenance_ref=provenance.record_id,
        source_unit="years",
        source_label="age__vd_large_artery_stiffening",
        subject=subject.key,
        evidence=EvidenceClass.MODELLED,
        value_state=ValueState.PRESENT,
        validity=ValidityState.NOT_EVALUATED,
        method_id="test-runtime",
    )
    state = RuntimeSubjectState(
        subject=subject,
        baseline=baseline,
        physics=physics,
        solution=solution,
        results=(age,),
        provenance_records=(provenance,),
    )
    cohort = Cohort(
        dataset_identity=identity,
        canonical_subject_ids=("1",),
        ordering_rule="canonical",
    )
    return RuntimeDiseaseDataset(
        identity=identity,
        parent_identity=parent_identity,
        run_identity=run_identity,
        cohort=cohort,
        subject_states=(state,),
        quantity_statuses=runtime_quantity_statuses(spec.condition),
    )
