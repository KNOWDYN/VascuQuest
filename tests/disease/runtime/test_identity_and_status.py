from __future__ import annotations

from vascuquest.disease.catalogue import specification
from vascuquest.disease.model import (
    DiseaseCondition,
    DiseasePopulationRequest,
    DiseaseQuantityStatus,
    DiseaseRunIdentity,
)
from vascuquest.disease.runtime.identity import runtime_dataset_identity
from vascuquest.disease.runtime.quantities import runtime_quantity_statuses
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.schema import load_canonical_schema


def _run(condition: DiseaseCondition) -> DiseaseRunIdentity:
    if condition is DiseaseCondition.CAROTID_STENOSIS:
        spec = specification(
            condition,
            {
                "side": "left",
                "artery": "common_carotid",
                "nascet_stenosis": 0.5,
                "lesion_length_m": 0.02,
            },
        )
    elif condition is DiseaseCondition.ILIAC_STENOSIS:
        spec = specification(
            condition,
            {
                "side": "left",
                "artery": "common_iliac",
                "diameter_stenosis": 0.5,
                "lesion_length_m": 0.02,
            },
        )
    elif condition is DiseaseCondition.FUSIFORM_ABDOMINAL_AORTIC_ANEURYSM:
        spec = specification(
            condition,
            {"maximum_diameter_m": 0.03, "aneurysm_length_m": 0.10},
        )
    else:
        spec = specification(condition, {"target_cfpwv_m_per_s": 12.0})
    parent = DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )
    request = DiseasePopulationRequest(
        patients=1,
        age_group=50,
        specification=spec,
        seed=7,
    )
    return DiseaseRunIdentity(parent, ("101",), request)


def test_runtime_identity_is_content_addressed_and_preserves_schema() -> None:
    run = _run(DiseaseCondition.CAROTID_STENOSIS)
    identity = runtime_dataset_identity(run)
    assert identity.dataset_family == "PWDB-VD"
    assert identity.record_id == run.run_id
    assert identity.schema_version == run.parent_dataset_identity.schema_version
    assert run.run_id in identity.persistent_identifier


def test_runtime_status_policy_covers_every_public_quantity_plus_flow_rate() -> None:
    canonical = {item.definition.canonical_name for item in load_canonical_schema().quantities}
    expected = canonical | {"flow_rate"}
    for condition in DiseaseCondition:
        statuses = dict(runtime_quantity_statuses(condition))
        assert set(statuses) == expected
        assert statuses["photoplethysmogram"] is DiseaseQuantityStatus.NOT_SUPPORTED
        assert statuses["pressure"] is DiseaseQuantityStatus.RECOMPUTED
        assert statuses["flow_rate"] is DiseaseQuantityStatus.DERIVED_FROM_RECOMPUTED
        assert statuses["age"] is DiseaseQuantityStatus.UNCHANGED_CAUSAL_INPUT
        assert statuses["vascular_geometry"] is DiseaseQuantityStatus.MODEL_PARAMETER_MODIFIED


def test_stiffening_runtime_vascular_state_is_modified_even_with_unchanged_radii() -> None:
    statuses = dict(runtime_quantity_statuses(DiseaseCondition.LARGE_ARTERY_STIFFENING))
    assert statuses["vascular_geometry"] is DiseaseQuantityStatus.MODEL_PARAMETER_MODIFIED
