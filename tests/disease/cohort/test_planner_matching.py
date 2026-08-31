from __future__ import annotations

from types import SimpleNamespace

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.cohort import ParameterizedDiseaseCohortRequest, plan_parameterized_cohort
from vascuquest.disease.model import DiseaseCondition
from vascuquest.errors import AdmissibilityError


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)


class FakeSession:
    identity = IDENTITY

    def __init__(self):
        self._ids = ("1", "2", "3")
        self._ages = (55.0, 55.0, 55.0)

    def subjects(self, *, where=None):
        assert where is None
        return tuple(SimpleNamespace(canonical_subject_id=item) for item in self._ids)

    def get(self, quantity, *, subjects=None, location=None):
        assert quantity == "age"
        return SimpleNamespace(values=self._ages)


class FakeAssembler:
    def assemble(self, session, subject_id):
        return SimpleNamespace(canonical_subject_id=subject_id, age_years=55)


def test_planner_reuses_subject_at_higher_severity_instead_of_discarding_it(monkeypatch):
    from vascuquest.disease.cohort import planner

    def ordered_rank(seed, namespace, token):
        del seed, namespace
        return int(token).to_bytes(32, "big")

    def fake_transform(baseline, specification, *, options):
        del options
        severity = float(specification.parameter_mapping()["nascet_stenosis"])
        if baseline.canonical_subject_id == "1":
            raise AdmissibilityError("never admissible")
        if baseline.canonical_subject_id == "2" and severity < 0.55:
            raise AdmissibilityError("needs a higher severity assignment")
        return object()

    monkeypatch.setattr(planner, "_rank", ordered_rank)
    monkeypatch.setattr(planner, "transform_disease", fake_transform)
    request = ParameterizedDiseaseCohortRequest.from_mapping(
        patients=2,
        age_min=45,
        age_max=65,
        condition=DiseaseCondition.CAROTID_STENOSIS,
        severity_min=0.30,
        severity_max=0.80,
        fixed_parameters={
            "side": "left",
            "artery": "common_carotid",
            "lesion_length_m": 0.02,
        },
        seed=0,
    )
    plan = plan_parameterized_cohort(
        FakeSession(), request, assembler=FakeAssembler()
    )
    assigned = {item.canonical_subject_id: item.severity_value for item in plan.assignments}
    assert set(assigned) == {"2", "3"}
    assert assigned["2"] >= 0.55
    assert assigned["3"] < 0.55
    assert plan.rejections[0].canonical_subject_id == "1"
