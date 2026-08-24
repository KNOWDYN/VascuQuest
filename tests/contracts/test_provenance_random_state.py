"""Focused regression for reproducible random-state provenance."""

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.provenance import ProvenanceBuilder, provenance_from_json, provenance_to_json


def test_random_state_survives_deterministic_provenance_serialization() -> None:
    dataset = DatasetIdentity(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
        schema_version="1",
    )
    record = ProvenanceBuilder(dataset).build(
        evidence=EvidenceClass.MODELLED,
        method_id="operator:random-example",
        parameters={"alpha": 1.0},
        random_state={"seed": 7, "generator": "example"},
    )

    restored = provenance_from_json(provenance_to_json(record))

    assert restored == record
    assert restored.random_state is not None
    assert restored.random_state.value() == {"generator": "example", "seed": 7}
