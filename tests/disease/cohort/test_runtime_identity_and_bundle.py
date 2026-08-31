from __future__ import annotations

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.cohort import (
    DiseaseCohortAssignment,
    ParameterizedDiseaseCohortBundleWriter,
    ParameterizedDiseaseCohortPlan,
    ParameterizedDiseaseCohortRequest,
    cohort_runtime_dataset_identity,
    inspect_parameterized_cohort_bundle,
    read_cohort_plan,
    subject_disease_run_identity,
    verify_parameterized_cohort_bundle,
    write_cohort_plan,
)
from vascuquest.disease.model import DiseaseCondition


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)


def make_plan():
    request = ParameterizedDiseaseCohortRequest.from_mapping(
        patients=1,
        age_min=45,
        age_max=65,
        condition=DiseaseCondition.CAROTID_STENOSIS,
        severity_min=0.40,
        severity_max=0.70,
        fixed_parameters={
            "side": "left",
            "artery": "common_carotid",
            "lesion_length_m": 0.02,
        },
        seed=9,
    )
    severity = 0.55
    assignment = DiseaseCohortAssignment(
        canonical_subject_id="431",
        age_years=55,
        severity_parameter=request.severity_parameter,
        severity_value=severity,
        specification=request.specification_for(severity),
    )
    return ParameterizedDiseaseCohortPlan(
        parent_dataset_identity=IDENTITY,
        request=request,
        supported_ages=(45, 55, 65),
        assignments=(assignment,),
    )


def test_cohort_and_subject_run_identities_preserve_pwdb_subject_number():
    plan = make_plan()
    runtime = cohort_runtime_dataset_identity(plan)
    subject_run = subject_disease_run_identity(plan, plan.assignments[0])
    assert runtime.dataset_family == "PWDB-VD"
    assert runtime.record_id == plan.run_id
    assert subject_run.canonical_subject_ids == ("431",)
    assert subject_run.request.age_group == 55
    assert subject_run.request.specification.parameter_mapping()["nascet_stenosis"] == 0.55


def test_plan_and_incomplete_bundle_roundtrip_and_integrity(tmp_path):
    plan = make_plan()
    plan_path = write_cohort_plan(plan, tmp_path / "plan.json")
    restored = read_cohort_plan(plan_path)
    assert restored.run_id == plan.run_id

    runtime = cohort_runtime_dataset_identity(plan)
    bundle = tmp_path / "bundle"
    ParameterizedDiseaseCohortBundleWriter(bundle, plan, runtime)
    manifest = inspect_parameterized_cohort_bundle(bundle)
    assert manifest["status"] == "INCOMPLETE"
    assert manifest["canonical_subject_ids"] == ["431"]
    verified = verify_parameterized_cohort_bundle(bundle)
    assert verified["valid"] is True
    assert verified["subjects_verified"] == 0
    assert verified["patients_planned"] == 1
