"""Unit tests for storage-independent scientific results and waveforms."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import (
    Coordinate,
    ScientificResult,
    ValidityState,
    ValueState,
    Waveform,
)


def _dataset(*, schema_version: str = "1", record_id: str = "3275625") -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id=record_id,
        persistent_identifier=f"10.5281/zenodo.{record_id}",
        schema_version=schema_version,
    )


def _quantity(*, schema_version: str = "1") -> QuantityDefinition:
    return QuantityDefinition(
        canonical_name="pressure",
        label="Pressure",
        description="Arterial pressure.",
        value_kind="numeric",
        schema_version=schema_version,
        physical_dimension="pressure",
        canonical_unit="mmHg",
        allowed_source_units=("Pa", "mmHg"),
        applicable_contexts=("measurement_site", "path_position"),
        source_aliases=("P",),
    )


def _subject(dataset: DatasetIdentity | None = None, subject_id: str = "1") -> SubjectKey:
    return SubjectKey(dataset or _dataset(), subject_id)


def _cohort(dataset: DatasetIdentity | None = None) -> Cohort:
    return Cohort(
        dataset_identity=dataset or _dataset(),
        canonical_subject_ids=("1", "2"),
        ordering_rule="canonical_subject_id_ascending",
    )


def _result(**overrides: object) -> ScientificResult:
    values: dict[str, object] = {
        "dataset_identity": _dataset(),
        "quantity": _quantity(),
        "values": 120.0,
        "provenance_ref": "provenance:result:1",
        "dimensions": (),
        "coordinates": (),
        "source_unit": "mmHg",
        "source_label": "P",
        "subject": _subject(),
        "location": MeasurementSite("site:aortic-root"),
        "evidence": EvidenceClass.SOURCE,
        "value_state": ValueState.PRESENT,
        "validity": ValidityState.NOT_EVALUATED,
        "warnings": (),
        "method_id": None,
    }
    values.update(overrides)
    return ScientificResult(**values)  # type: ignore[arg-type]


def test_result_preserves_scientific_context_and_canonical_unit() -> None:
    result = _result()

    assert result.dataset_identity == _dataset()
    assert result.quantity.canonical_name == "pressure"
    assert result.values == 120.0
    assert result.canonical_unit == "mmHg"
    assert result.physical_dimension == "pressure"
    assert result.source_unit == "mmHg"
    assert result.source_label == "P"
    assert result.evidence is EvidenceClass.SOURCE
    assert result.provenance_ref == "provenance:result:1"


def test_result_value_and_validity_states_are_independent_of_evidence() -> None:
    assert tuple(state.value for state in ValueState) == (
        "PRESENT",
        "MISSING",
        "UNAVAILABLE",
        "NOT_APPLICABLE",
    )
    assert {
        "INVALID",
        "NOT_EVALUATED",
        "VALID",
        "VALID_WITH_WARNING",
        "OUT_OF_DECLARED_DOMAIN",
        "INVALID_INPUT",
        "NUMERICAL_FAILURE",
    } == {state.value for state in ValidityState}

    result = _result(
        evidence=EvidenceClass.MODELLED,
        method_id="operator:model",
        value_state=ValueState.PRESENT,
        validity=ValidityState.OUT_OF_DECLARED_DOMAIN,
        warnings=("outside validated domain",),
    )
    assert result.evidence is EvidenceClass.MODELLED
    assert result.validity is ValidityState.OUT_OF_DECLARED_DOMAIN


def test_missing_unavailable_not_applicable_invalid_and_not_evaluated_remain_distinct() -> None:
    assert ValueState.MISSING is not ValueState.UNAVAILABLE
    assert ValueState.UNAVAILABLE is not ValueState.NOT_APPLICABLE
    assert ValidityState.INVALID is not ValidityState.NOT_EVALUATED


def test_result_requires_matching_schema_version() -> None:
    with pytest.raises(ValueError):
        _result(quantity=_quantity(schema_version="2"))


def test_result_requires_nonempty_provenance_reference() -> None:
    with pytest.raises(ValueError):
        _result(provenance_ref="")


def test_dimensions_and_coordinates_are_named_and_unique() -> None:
    time = Coordinate("time", (0.0, 0.01), "s")
    result = _result(dimensions=("time",), coordinates=(time,))
    assert result.dimensions == ("time",)
    assert result.coordinates[0].name == "time"

    with pytest.raises(ValueError):
        _result(dimensions=("time", "time"))

    with pytest.raises(ValueError):
        _result(coordinates=(time, Coordinate("time", (0.0, 0.01), "s")))


def test_coordinate_validates_name_and_optional_unit() -> None:
    with pytest.raises(ValueError):
        Coordinate(" time", (0.0,), "s")

    with pytest.raises(ValueError):
        Coordinate("time", (0.0,), " s")


def test_result_context_must_match_dataset_identity() -> None:
    other_dataset = _dataset(record_id="9999999")

    with pytest.raises(ValueError):
        _result(subject=_subject(other_dataset))

    with pytest.raises(ValueError):
        _result(subject=None, cohort=_cohort(other_dataset))


def test_subject_must_belong_to_cohort_when_both_are_supplied() -> None:
    with pytest.raises(ValueError):
        _result(subject=_subject(subject_id="3"), cohort=_cohort())

    result = _result(subject=_subject(subject_id="2"), cohort=_cohort())
    assert result.subject is not None
    assert result.subject.canonical_subject_id == "2"


def test_result_rejects_unsupported_context_and_state_types() -> None:
    with pytest.raises(TypeError):
        _result(location="aortic-root")

    with pytest.raises(TypeError):
        _result(evidence="SOURCE")

    with pytest.raises(TypeError):
        _result(value_state="PRESENT")

    with pytest.raises(TypeError):
        _result(validity="VALID")


def test_non_source_result_requires_method_identity() -> None:
    for evidence in (
        EvidenceClass.RECONSTRUCTED,
        EvidenceClass.DERIVED,
        EvidenceClass.INFERRED,
        EvidenceClass.MODELLED,
    ):
        with pytest.raises(ValueError):
            _result(evidence=evidence, method_id=None)

        result = _result(evidence=evidence, method_id="method:example")
        assert result.method_id == "method:example"


def test_result_wrapper_is_immutable_but_does_not_assume_value_storage_type() -> None:
    external_values = [1.0, 2.0]
    result = _result(values=external_values)

    assert result.values is external_values
    with pytest.raises(FrozenInstanceError):
        result.values = (3.0,)  # type: ignore[misc]


def _waveform(**overrides: object) -> Waveform:
    values: dict[str, object] = {
        "dataset_identity": _dataset(),
        "quantity": _quantity(),
        "values": (100.0, 110.0, 105.0),
        "provenance_ref": "provenance:waveform:1",
        "dimensions": ("time",),
        "coordinates": (Coordinate("time", (0.0, 0.01, 0.02), "s"),),
        "subject": _subject(),
        "location": MeasurementSite("site:aortic-root"),
        "evidence": EvidenceClass.SOURCE,
    }
    values.update(overrides)
    return Waveform(**values)  # type: ignore[arg-type]


def test_waveform_requires_explicit_time_subject_and_location_context() -> None:
    waveform = _waveform()
    assert waveform.time_coordinate.name == "time"
    assert waveform.time_coordinate.unit == "s"

    with pytest.raises(ValueError):
        _waveform(subject=None)

    with pytest.raises(ValueError):
        _waveform(location=None)

    with pytest.raises(ValueError):
        _waveform(dimensions=("sample",))

    with pytest.raises(ValueError):
        _waveform(coordinates=(Coordinate("sample", (0, 1, 2)),))


def test_waveform_can_retain_missing_and_padding_masks_without_defining_storage() -> None:
    missing_mask = (False, True, False)
    padding_mask = (False, False, True)
    waveform = _waveform(missing_mask=missing_mask, padding_mask=padding_mask)

    assert waveform.missing_mask is missing_mask
    assert waveform.padding_mask is padding_mask
