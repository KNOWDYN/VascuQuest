"""Contract tests for provenance construction and result-metadata serialization."""

from __future__ import annotations

from dataclasses import fields
import math

import pytest

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, PathPosition
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, ValueState, Waveform
from vascuquest.errors import ReproducibilityError
from vascuquest.provenance import (
    CanonicalJSON,
    ComponentReference,
    ProvenanceBuilder,
    SourceArtifactReference,
    provenance_from_dict,
    provenance_from_json,
    provenance_to_dict,
    provenance_to_json,
    result_metadata_from_dict,
    result_metadata_from_json,
    result_metadata_to_dict,
    result_metadata_to_json,
)


def _dataset(*, record_id: str = "3275625") -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id=record_id,
        persistent_identifier=f"10.5281/zenodo.{record_id}",
        schema_version="1",
    )


def _quantity() -> QuantityDefinition:
    return QuantityDefinition(
        canonical_name="pressure",
        label="Pressure",
        description="Arterial pressure.",
        value_kind="numeric",
        schema_version="1",
        physical_dimension="pressure",
        canonical_unit="mmHg",
        allowed_source_units=("mmHg",),
        applicable_contexts=("measurement_site", "path_position"),
        source_aliases=("P",),
        default_evidence=EvidenceClass.SOURCE,
        citations=("doi:10.1152/ajpheart.00218.2019",),
    )


def _subject(dataset: DatasetIdentity | None = None, subject_id: str = "1") -> SubjectKey:
    return SubjectKey(dataset or _dataset(), subject_id)


def _cohort(dataset: DatasetIdentity | None = None) -> Cohort:
    return Cohort(
        dataset_identity=dataset or _dataset(),
        canonical_subject_ids=("1", "2"),
        ordering_rule="canonical_subject_id_ascending",
        selection_specification=("age=45",),
        inclusion_filters=("age=45",),
        exclusion_filters=(),
        plausibility_filter="source_plausible=true",
        creation_provenance_ref="provenance:selection:1",
    )


def _artifact(artifact_id: str = "common_site_waveforms_csv") -> SourceArtifactReference:
    return SourceArtifactReference(
        artifact_id=artifact_id,
        checksum_algorithm="md5",
        checksum_value="81067f96d6078bbbb5cd9fce5d73f5bd",
    )


def _component() -> ComponentReference:
    return ComponentReference(
        qualified_id="vascuquest:example",
        implementation_version="0.1.0.dev0",
        protocol_version=1,
        distribution_name="vascuquest",
        distribution_version="0.1.0.dev0",
    )


def _builder(dataset: DatasetIdentity | None = None) -> ProvenanceBuilder:
    return ProvenanceBuilder(
        dataset or _dataset(),
        environment={"python": "3.13", "vascuquest": "0.1.0.dev0"},
    )


def _source_record() -> object:
    dataset = _dataset()
    return _builder(dataset).build(
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.VALID,
        source_artifacts=(_artifact(),),
        subject=_subject(dataset),
        cohort=_cohort(dataset),
        location=MeasurementSite("site:aortic-root"),
        source_fields=("P",),
        component=_component(),
        parameters={"representation": "csv"},
        assumptions=("lossless source parsing",),
        citations=("doi:10.1152/ajpheart.00218.2019",),
        warnings=(),
        output_identity="result:pressure:1",
    )


def test_canonical_json_normalizes_mapping_order_and_round_trips() -> None:
    left = CanonicalJSON.from_mapping({"b": 2, "a": [1, True, None]})
    right = CanonicalJSON.from_mapping({"a": [1, True, None], "b": 2})

    assert left == right
    assert left.text == '{"a":[1,true,null],"b":2}'
    assert left.value() == {"a": [1, True, None], "b": 2}


def test_canonical_json_rejects_non_json_and_nonfinite_values() -> None:
    with pytest.raises(TypeError):
        CanonicalJSON.from_value(object())

    with pytest.raises(TypeError):
        CanonicalJSON.from_value({"x": math.nan})

    with pytest.raises(ValueError):
        CanonicalJSON("NaN")


def test_source_artifact_reference_contains_scientific_identity_not_storage_location() -> None:
    names = {field.name for field in fields(SourceArtifactReference)}

    assert names == {"artifact_id", "checksum_algorithm", "checksum_value"}
    assert "path" not in names
    assert "url" not in names
    assert "locator" not in names


def test_builder_is_deterministic_for_equivalent_normalized_facts() -> None:
    builder = _builder()
    artifact_a = _artifact("a")
    artifact_b = SourceArtifactReference("b", "md5", "0123456789abcdef0123456789abcdef")

    left = builder.build(
        evidence=EvidenceClass.DERIVED,
        source_artifacts=(artifact_b, artifact_a),
        source_fields=("U", "A"),
        method_id="vascuquest:derived-example",
        parameters={"beta": 2, "alpha": 1},
        assumptions=("second", "first"),
        citations=("citation:b", "citation:a"),
        warnings=("warning:b", "warning:a"),
    )
    right = builder.build(
        evidence=EvidenceClass.DERIVED,
        source_artifacts=(artifact_a, artifact_b),
        source_fields=("A", "U"),
        method_id="vascuquest:derived-example",
        parameters={"alpha": 1, "beta": 2},
        assumptions=("first", "second"),
        citations=("citation:a", "citation:b"),
        warnings=("warning:a", "warning:b"),
    )

    assert left.record_id == right.record_id
    assert left == right
    assert left.record_id.startswith("sha256:")


def test_builder_identity_changes_when_material_parameter_or_random_state_changes() -> None:
    builder = _builder()
    first = builder.build(
        evidence=EvidenceClass.MODELLED,
        method_id="operator:model",
        parameters={"alpha": 1},
        random_state={"seed": 7},
    )
    changed_parameter = builder.build(
        evidence=EvidenceClass.MODELLED,
        method_id="operator:model",
        parameters={"alpha": 2},
        random_state={"seed": 7},
    )
    changed_seed = builder.build(
        evidence=EvidenceClass.MODELLED,
        method_id="operator:model",
        parameters={"alpha": 1},
        random_state={"seed": 8},
    )

    assert first.record_id != changed_parameter.record_id
    assert first.record_id != changed_seed.record_id


def test_builder_preserves_complete_scientific_context() -> None:
    record = _source_record()

    assert record.dataset_identity == _dataset()
    assert record.schema_version == "1"
    assert record.subject == _subject()
    assert record.cohort == _cohort()
    assert record.location == MeasurementSite("site:aortic-root")
    assert record.source_fields == ("P",)
    assert record.evidence is EvidenceClass.SOURCE
    assert record.validity is ValidityState.VALID
    assert record.value_state is ValueState.PRESENT
    assert record.source_artifacts == (_artifact(),)
    assert record.component == _component()
    assert record.parameters.value() == {"representation": "csv"}
    assert record.assumptions == ("lossless source parsing",)
    assert record.citations == ("doi:10.1152/ajpheart.00218.2019",)
    assert record.environment.value()["vascuquest"] == "0.1.0.dev0"
    assert record.output_identity == "result:pressure:1"


def test_builder_rejects_malformed_artifact_and_input_iterables_cleanly() -> None:
    builder = _builder()

    with pytest.raises(TypeError):
        builder.build(evidence=EvidenceClass.SOURCE, source_artifacts=(object(),))

    with pytest.raises(TypeError):
        builder.build(evidence=EvidenceClass.SOURCE, inputs=(object(),))


def test_non_source_provenance_requires_method_identity() -> None:
    for evidence in (
        EvidenceClass.RECONSTRUCTED,
        EvidenceClass.DERIVED,
        EvidenceClass.INFERRED,
        EvidenceClass.MODELLED,
    ):
        with pytest.raises(ValueError):
            _builder().build(evidence=evidence)


def test_input_lineage_must_use_same_dataset_identity_in_v1() -> None:
    other = _builder(_dataset(record_id="9999999")).build(evidence=EvidenceClass.SOURCE)

    with pytest.raises(ValueError):
        _builder().build(
            evidence=EvidenceClass.DERIVED,
            method_id="method:combine",
            inputs=(other,),
        )


def test_provenance_json_round_trip_is_deterministic_and_semantically_exact() -> None:
    source = _source_record()
    root = _builder().build(
        evidence=EvidenceClass.DERIVED,
        validity=ValidityState.VALID_WITH_WARNING,
        inputs=(source,),
        method_id="method:feature",
        component=_component(),
        parameters={"window": 5},
        warnings=("example warning",),
        output_identity="result:feature:1",
    )

    encoded = provenance_to_json(root)
    restored = provenance_from_json(encoded)

    assert restored == root
    assert provenance_to_json(restored) == encoded
    assert provenance_from_dict(provenance_to_dict(root)) == root


def test_shared_lineage_is_serialized_once_as_a_dag() -> None:
    base = _builder().build(evidence=EvidenceClass.SOURCE)
    left = _builder().build(
        evidence=EvidenceClass.DERIVED,
        method_id="method:left",
        inputs=(base,),
    )
    right = _builder().build(
        evidence=EvidenceClass.DERIVED,
        method_id="method:right",
        inputs=(base,),
    )
    root = _builder().build(
        evidence=EvidenceClass.DERIVED,
        method_id="method:root",
        inputs=(left, right),
    )

    document = provenance_to_dict(root)
    records = document["records"]
    assert isinstance(records, list)
    assert len(records) == 4
    assert sum(record["record_id"] == base.record_id for record in records) == 1


def test_serialized_cycle_and_dangling_input_are_rejected() -> None:
    base = _builder().build(evidence=EvidenceClass.SOURCE)
    root = _builder().build(
        evidence=EvidenceClass.DERIVED,
        method_id="method:root",
        inputs=(base,),
    )

    cyclic = provenance_to_dict(root)
    records = cyclic["records"]
    assert isinstance(records, list)
    root_node = next(record for record in records if record["record_id"] == root.record_id)
    base_node = next(record for record in records if record["record_id"] == base.record_id)
    root_node["input_record_ids"] = [base.record_id]
    base_node["input_record_ids"] = [root.record_id]
    with pytest.raises(ReproducibilityError, match="cyclic"):
        provenance_from_dict(cyclic)

    dangling = provenance_to_dict(root)
    dangling_records = dangling["records"]
    assert isinstance(dangling_records, list)
    dangling_root = next(
        record for record in dangling_records if record["record_id"] == root.record_id
    )
    dangling_root["input_record_ids"] = ["missing:record"]
    with pytest.raises(ReproducibilityError, match="missing"):
        provenance_from_dict(dangling)


def test_provenance_serialization_does_not_add_storage_locations_or_result_arrays() -> None:
    encoded = provenance_to_json(_source_record())

    assert "source_locator" not in encoded
    assert "local_path" not in encoded
    assert "/tmp/" not in encoded
    assert '"values"' not in encoded
    assert '"samples"' not in encoded


def test_scientific_result_metadata_round_trip_preserves_context_without_copying_values() -> None:
    provenance = _source_record()
    external_values = [120.0, 121.0]
    result = ScientificResult(
        dataset_identity=_dataset(),
        quantity=_quantity(),
        values=external_values,
        provenance_ref=provenance.record_id,
        dimensions=("subject",),
        coordinates=(Coordinate("subject", ("1", "2")),),
        source_unit="mmHg",
        source_label="P",
        cohort=_cohort(),
        location=MeasurementSite("site:aortic-root"),
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.VALID_WITH_WARNING,
        warnings=("example warning",),
    )

    payload = result_metadata_to_dict(result)
    assert "values" not in payload
    assert all("values" not in coordinate for coordinate in payload["coordinates"])

    external_coordinate = ("1", "2")
    restored = result_metadata_from_dict(
        payload,
        values=external_values,
        coordinate_values={"subject": external_coordinate},
    )

    assert restored.values is external_values
    assert restored.coordinates[0].values is external_coordinate
    assert restored.dataset_identity == result.dataset_identity
    assert restored.quantity == result.quantity
    assert restored.provenance_ref == provenance.record_id
    assert restored.cohort == result.cohort
    assert restored.location == result.location
    assert restored.evidence is result.evidence
    assert restored.validity is result.validity
    assert restored.warnings == result.warnings


def test_waveform_metadata_round_trip_preserves_masks_and_time_context_externally() -> None:
    provenance = _source_record()
    samples = [100.0, 110.0, 105.0]
    times = [0.0, 0.01, 0.02]
    missing = [False, True, False]
    padding = [False, False, True]
    waveform = Waveform(
        dataset_identity=_dataset(),
        quantity=_quantity(),
        values=samples,
        provenance_ref=provenance.record_id,
        dimensions=("time",),
        coordinates=(Coordinate("time", times, "s"),),
        subject=_subject(),
        location=MeasurementSite("site:aortic-root"),
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.VALID,
        missing_mask=missing,
        padding_mask=padding,
    )

    encoded = result_metadata_to_json(waveform)
    assert "100.0" not in encoded
    assert "0.01" not in encoded

    restored = result_metadata_from_json(
        encoded,
        values=samples,
        coordinate_values={"time": times},
        missing_mask=missing,
        padding_mask=padding,
    )

    assert isinstance(restored, Waveform)
    assert restored.values is samples
    assert restored.time_coordinate.values is times
    assert restored.missing_mask is missing
    assert restored.padding_mask is padding
    assert restored.subject == waveform.subject
    assert restored.location == waveform.location


def test_result_metadata_requires_exact_external_coordinate_and_mask_contract() -> None:
    waveform = Waveform(
        dataset_identity=_dataset(),
        quantity=_quantity(),
        values=(1.0, 2.0),
        provenance_ref="provenance:waveform:1",
        dimensions=("time",),
        coordinates=(Coordinate("time", (0.0, 1.0), "s"),),
        subject=_subject(),
        location=PathPosition("path:aorta-finger", 0),
        missing_mask=(False, False),
    )
    payload = result_metadata_to_dict(waveform)

    with pytest.raises(ReproducibilityError, match="coordinate_values"):
        result_metadata_from_dict(
            payload,
            values=(1.0, 2.0),
            coordinate_values={},
            missing_mask=(False, False),
        )

    with pytest.raises(ReproducibilityError, match="missing-mask"):
        result_metadata_from_dict(
            payload,
            values=(1.0, 2.0),
            coordinate_values={"time": (0.0, 1.0)},
            missing_mask=None,
        )
