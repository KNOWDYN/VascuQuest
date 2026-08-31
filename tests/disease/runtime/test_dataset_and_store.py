from __future__ import annotations

import pytest

from vascuquest.disease.model import DiseaseQuantityStatus
from vascuquest.disease.runtime.store import RuntimeDiseaseStore
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.errors import CapabilityError, SelectionError


def test_runtime_dataset_preserves_parent_subject_number(runtime_dataset) -> None:
    assert runtime_dataset.parent_identity.dataset_family == "PWDB"
    assert runtime_dataset.identity.dataset_family == "PWDB-VD"
    assert runtime_dataset.subjects()[0].canonical_subject_id == "1"
    assert runtime_dataset.subject("1").canonical_subject_id == "1"
    assert runtime_dataset.run_identity.canonical_subject_ids == ("1",)


def test_runtime_scalar_uses_modelled_evidence_and_disease_vector_name(runtime_dataset) -> None:
    age = runtime_dataset.get("age", subjects="1")
    assert age.values == 50
    assert age.evidence.value == "MODELLED"
    assert age.source_label == "age__vd_large_artery_stiffening"
    assert runtime_dataset.quantity_status("age") is DiseaseQuantityStatus.UNCHANGED_CAUSAL_INPUT
    assert runtime_dataset.provenance(age.provenance_ref).record_id == age.provenance_ref


def test_runtime_dataset_rejects_unknown_subject(runtime_dataset) -> None:
    with pytest.raises(SelectionError):
        runtime_dataset.subject("999")


def test_runtime_dataset_fails_explicitly_for_unsupported_quantity(runtime_dataset) -> None:
    assert (
        runtime_dataset.quantity_status("photoplethysmogram")
        is DiseaseQuantityStatus.NOT_SUPPORTED
    )
    with pytest.raises(CapabilityError, match="NOT_SUPPORTED"):
        runtime_dataset.get("photoplethysmogram", subjects="1")
    with pytest.raises(CapabilityError, match="use waveform"):
        runtime_dataset.get("pressure", subjects="1")


def test_runtime_dataset_rejects_identity_not_derived_from_run(runtime_dataset) -> None:
    bad_identity = DatasetIdentity(
        dataset_family="PWDB-VD",
        record_id="wrong-run-id",
        persistent_identifier="urn:vascuquest:virtual-disease:wrong-run-id",
        schema_version="1",
    )
    bad_cohort = Cohort(
        dataset_identity=bad_identity,
        canonical_subject_ids=("1",),
        ordering_rule="canonical",
    )
    with pytest.raises(ValueError, match="derived from its DiseaseRunIdentity"):
        type(runtime_dataset)(
            identity=bad_identity,
            parent_identity=runtime_dataset.parent_identity,
            run_identity=runtime_dataset.run_identity,
            cohort=bad_cohort,
            subject_states=(runtime_dataset.state("1"),),
            quantity_statuses=runtime_dataset.quantity_statuses(),
        )


def test_runtime_store_is_content_addressed(runtime_dataset) -> None:
    store = RuntimeDiseaseStore()
    first = store.put(runtime_dataset)
    second = store.put(runtime_dataset)
    assert first is second
    assert store.get(runtime_dataset.run_id) is runtime_dataset
    assert store.run_ids() == (runtime_dataset.run_id,)
    store.clear()
    assert store.run_ids() == ()
