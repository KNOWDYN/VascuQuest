"""Contract tests for storage-independent backend/method/exporter ports."""

from __future__ import annotations

import pytest

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite
from vascuquest.ports import (
    ExecutionContext,
    GeometryRequest,
    InputRequirement,
    ParameterSpec,
    QuantityRequest,
    WaveformRequest,
)


def _dataset(record_id: str = "3275625") -> DatasetIdentity:
    return DatasetIdentity(
        dataset_family="PWDB",
        record_id=record_id,
        persistent_identifier=f"10.5281/zenodo.{record_id}",
        schema_version="1",
    )


def _subject(subject_id: str = "1", dataset: DatasetIdentity | None = None) -> SubjectKey:
    return SubjectKey(dataset or _dataset(), subject_id)


def _cohort() -> Cohort:
    return Cohort(
        dataset_identity=_dataset(),
        canonical_subject_ids=("1", "2"),
        ordering_rule="canonical_subject_id_ascending",
    )


def test_quantity_request_preserves_canonical_context() -> None:
    request = QuantityRequest(
        "pressure",
        subject=_subject(),
        cohort=_cohort(),
        location=MeasurementSite("site:aortic-root"),
    )

    assert request.quantity == "pressure"
    assert request.subject == _subject()
    assert request.location == MeasurementSite("site:aortic-root")


def test_quantity_request_rejects_cross_dataset_or_nonmember_subject_context() -> None:
    other = _dataset("9999999")
    with pytest.raises(ValueError):
        QuantityRequest("pressure", subject=_subject(dataset=other), cohort=_cohort())

    with pytest.raises(ValueError):
        QuantityRequest("pressure", subject=_subject("3"), cohort=_cohort())


def test_backend_requests_reject_noncanonical_location_objects() -> None:
    with pytest.raises(TypeError):
        QuantityRequest("pressure", location="aortic-root")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        WaveformRequest("pressure", _subject(), "aortic-root")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        GeometryRequest(location="aortic-root")  # type: ignore[arg-type]


def test_waveform_request_requires_subject_and_signal_identity() -> None:
    location = MeasurementSite("site:aortic-root")
    request = WaveformRequest("pressure", _subject(), location)
    assert request.signal == "pressure"
    assert request.subject == _subject()

    with pytest.raises(ValueError):
        WaveformRequest(" pressure", _subject(), location)
    with pytest.raises(TypeError):
        WaveformRequest("pressure", "1", location)  # type: ignore[arg-type]


def test_parameter_spec_accepts_nontext_allowed_values_without_serialization_lockin() -> None:
    spec = ParameterSpec(
        name="order",
        kind="integer",
        description="Example integer parameter.",
        default=2,
        allowed_values=(1, 2, 3),
    )
    assert spec.allowed_values == (1, 2, 3)

    with pytest.raises(ValueError):
        ParameterSpec(
            name="alpha",
            kind="float",
            description="Required alpha.",
            required=True,
            default=1.0,
        )


def test_input_requirement_requires_canonical_quantity_or_category() -> None:
    requirement = InputRequirement(
        name="pressure_input",
        quantity="pressure",
        accepted_units=("mmHg",),
        physical_dimension="pressure",
        required_coordinates=("time",),
        location_kind="measurement_site",
        accepted_evidence=(EvidenceClass.SOURCE, EvidenceClass.RECONSTRUCTED),
    )
    assert requirement.quantity == "pressure"

    with pytest.raises(ValueError):
        InputRequirement(name="unnamed_science")
    with pytest.raises(TypeError):
        InputRequirement(name="bad", quantity="pressure", accepted_evidence=("SOURCE",))  # type: ignore[arg-type]


def test_execution_context_emits_only_through_explicit_warning_sink() -> None:
    messages: list[str] = []
    context = ExecutionContext("0.1.0.dev0", random_state={"seed": 7}, warning_sink=messages.append)
    context.emit_warning("outside reference range")
    assert messages == ["outside reference range"]

    silent = ExecutionContext("0.1.0.dev0")
    silent.emit_warning("still valid")

    with pytest.raises(TypeError):
        ExecutionContext("0.1.0.dev0", warning_sink="stderr")  # type: ignore[arg-type]
