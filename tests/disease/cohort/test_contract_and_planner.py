from __future__ import annotations

from types import SimpleNamespace

import pytest

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.cohort import (
    ParameterizedDiseaseCohortPlan,
    ParameterizedDiseaseCohortRequest,
    plan_parameterized_cohort,
    severity_parameter,
    stratified_severity_design,
)
from vascuquest.disease.model import DiseaseCondition
from vascuquest.errors import AdmissibilityError


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)


def carotid_request(**overrides):
    values = {
        "patients": 3,
        "age_min": 40,
        "age_max": 70,
        "condition": DiseaseCondition.CAROTID_STENOSIS,
        "severity_min": 0.30,
        "severity_max": 0.80,
        "fixed_parameters": {
            "side": "left",
            "artery": "common_carotid",
            "lesion_length_m": 0.02,
        },
        "seed": 17,
    }
    values.update(overrides)
    return ParameterizedDiseaseCohortRequest.from_mapping(**values)


def test_contract_has_one_condition_specific_severity_parameter_and_rejects_duplication():
    request = carotid_request()
    assert request.severity_parameter == "nascet_stenosis"
    assert severity_parameter(DiseaseCondition.ILIAC_STENOSIS) == "diameter_stenosis"
    assert severity_parameter(DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM) == "maximum_diameter_m"
    assert severity_parameter(DiseaseCondition.LARGE_ARTERY_STIFFENING) == "target_cfpwv_m_per_s"

    with pytest.raises(AdmissibilityError):
        carotid_request(
            fixed_parameters={
                "side": "left",
                "artery": "common_carotid",
                "lesion_length_m": 0.02,
                "nascet_stenosis": 0.50,
            }
        )


def test_stratified_design_is_deterministic_bounded_and_covers_interval():
    request = carotid_request(patients=10)
    first = stratified_severity_design(request)
    second = stratified_severity_design(request)
    assert first == second
    assert len(first) == 10
    assert all(request.severity_min <= value <= request.severity_max for value in first)
    assert tuple(sorted(first)) == first
    width = (request.severity_max - request.severity_min) / request.patients
    for index, value in enumerate(first):
        assert request.severity_min + index * width <= value
        assert value <= request.severity_min + (index + 1) * width


class FakeSession:
    identity = IDENTITY

    def __init__(self):
        self._ids = ("1", "2", "3", "4", "5")
        self._ages = (25.0, 45.0, 55.0, 65.0, 75.0)

    def subjects(self, *, where=None):
        assert where is None
        return tuple(SimpleNamespace(canonical_subject_id=item) for item in self._ids)

    def get(self, quantity, *, subjects=None, location=None):
        assert quantity == "age"
        assert subjects is None
        assert location is None
        return SimpleNamespace(values=self._ages)


class FakeAssembler:
    def assemble(self, session, subject_id):
        age = dict(zip(session._ids, session._ages, strict=True))[subject_id]
        return SimpleNamespace(canonical_subject_id=subject_id, age_years=int(age))


def test_planner_uses_source_age_states_preserves_ids_and_records_physics_rejections(monkeypatch):
    from vascuquest.disease.cohort import planner

    calls = []

    def fake_transform(baseline, specification, *, options):
        severity = float(specification.parameter_mapping()["nascet_stenosis"])
        calls.append((baseline.canonical_subject_id, severity))
        if baseline.canonical_subject_id == "3":
            raise AdmissibilityError("subject-specific lesion does not fit")
        return object()

    monkeypatch.setattr(planner, "transform_disease", fake_transform)
    request = carotid_request(patients=2)
    plan = plan_parameterized_cohort(
        FakeSession(),
        request,
        assembler=FakeAssembler(),
    )

    assert plan.supported_ages == (45, 55, 65)
    assert len(plan.assignments) == 2
    assert len(set(plan.canonical_subject_ids)) == 2
    assert all(item.canonical_subject_id in {"2", "3", "4"} for item in plan.assignments)
    assert all(item.age_years in plan.supported_ages for item in plan.assignments)
    assert all(
        item.specification.parameter_mapping()["nascet_stenosis"] == item.severity_value
        for item in plan.assignments
    )
    assert any(item.canonical_subject_id == "3" for item in plan.rejections) == any(
        subject_id == "3" for subject_id, _ in calls
    )

    restored = ParameterizedDiseaseCohortPlan.from_dict(plan.to_dict())
    assert restored.run_id == plan.run_id
    assert restored.canonical_subject_ids == plan.canonical_subject_ids


def test_run_identity_changes_with_seeded_assignment_content(monkeypatch):
    from vascuquest.disease.cohort import planner

    monkeypatch.setattr(planner, "transform_disease", lambda *args, **kwargs: object())
    first = plan_parameterized_cohort(
        FakeSession(), carotid_request(patients=2, seed=17), assembler=FakeAssembler()
    )
    second = plan_parameterized_cohort(
        FakeSession(), carotid_request(patients=2, seed=18), assembler=FakeAssembler()
    )
    assert first.run_id != second.run_id
