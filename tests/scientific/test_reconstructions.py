from __future__ import annotations

import numpy as np
import pytest

from vascuquest.domain import (
    Coordinate,
    DatasetIdentity,
    EvidenceClass,
    MeasurementSite,
    SubjectKey,
    ValidityState,
    Waveform,
)
from vascuquest.errors import AdmissibilityError
from vascuquest.methods import FLOW_RATE_RECONSTRUCTION_ID, FlowRateReconstruction
from vascuquest.ports.methods import Derivation, ExecutionContext
from vascuquest.schema import load_canonical_schema


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)
SUBJECT = SubjectKey(IDENTITY, "1")
SITE = MeasurementSite("AorticRoot")
TIME = (0.0, 0.002, 0.004)


def _waveform(
    quantity: str,
    values: tuple[float, ...],
    *,
    time: tuple[float, ...] = TIME,
    evidence: EvidenceClass = EvidenceClass.SOURCE,
    missing_mask: object | None = None,
    padding_mask: object | None = None,
    validity: ValidityState = ValidityState.VALID,
) -> Waveform:
    definition = load_canonical_schema().quantity(quantity)
    return Waveform(
        dataset_identity=IDENTITY,
        quantity=definition,
        values=np.asarray(values, dtype=float),
        provenance_ref=f"source:{quantity}:subject-1:aortic-root",
        dimensions=("time",),
        coordinates=(Coordinate("time", np.asarray(time, dtype=float), unit="s"),),
        subject=SUBJECT,
        location=SITE,
        evidence=evidence,
        validity=validity,
        method_id=None if evidence is EvidenceClass.SOURCE else "tests:fixture",
        missing_mask=missing_mask,
        padding_mask=padding_mask,
    )


def test_flow_rate_component_declares_authoritative_reconstruction_contract() -> None:
    method = FlowRateReconstruction()
    assert isinstance(method, Derivation)
    assert method.descriptor.qualified_id == FLOW_RATE_RECONSTRUCTION_ID
    assert method.output_evidence is EvidenceClass.RECONSTRUCTED
    assert method.output_quantity.canonical_name == "flow_rate"
    assert method.output_quantity.physical_dimension == "volume_flow_rate"
    assert method.output_quantity.canonical_unit == "m^3/s"
    assert method.output_quantity.default_evidence is EvidenceClass.RECONSTRUCTED
    assert method.parameter_specs == ()
    assert method.deterministic is True
    assert "Q=U*A" in method.validation_scope
    assert any("export_pwdb.m" in citation for citation in method.citations)


def test_flow_rate_reconstruction_matches_manual_reference_identity() -> None:
    method = FlowRateReconstruction()
    velocity = _waveform("flow_velocity", (1.0, 2.0, -1.0))
    area = _waveform("luminal_area", (0.01, 0.02, 0.03))

    result = method.run(
        inputs={"flow_velocity": velocity, "luminal_area": area},
        parameters={},
        context=ExecutionContext(runtime_version="test"),
    )

    np.testing.assert_allclose(result.values, np.array((0.01, 0.04, -0.03)))
    assert result.evidence is EvidenceClass.RECONSTRUCTED
    assert result.method_id == FLOW_RATE_RECONSTRUCTION_ID
    assert result.subject == SUBJECT
    assert result.location == SITE
    assert result.time_coordinate.unit == "s"
    assert result.validity is ValidityState.VALID
    assert result.provenance_ref.startswith("sha256:")
    assert result.values.flags.writeable is False


def test_flow_rate_reconstruction_is_deterministic_and_propagates_masks() -> None:
    method = FlowRateReconstruction()
    velocity = _waveform(
        "flow_velocity",
        (1.0, np.nan, 3.0),
        missing_mask=(False, True, False),
        padding_mask=(False, False, True),
    )
    area = _waveform(
        "luminal_area",
        (0.01, 0.02, 0.03),
        missing_mask=(False, False, True),
        padding_mask=(False, True, False),
    )

    first = method.run(
        inputs={"flow_velocity": velocity, "luminal_area": area},
        parameters={},
        context=ExecutionContext(runtime_version="test"),
    )
    second = method.run(
        inputs={"flow_velocity": velocity, "luminal_area": area},
        parameters={},
        context=ExecutionContext(runtime_version="test"),
    )

    assert first.provenance_ref == second.provenance_ref
    assert np.isnan(first.values[1])
    np.testing.assert_array_equal(first.missing_mask, np.array((False, True, True)))
    np.testing.assert_array_equal(first.padding_mask, np.array((False, True, True)))
    assert first.missing_mask.flags.writeable is False
    assert first.padding_mask.flags.writeable is False


def test_flow_rate_reconstruction_rejects_implicit_time_alignment() -> None:
    method = FlowRateReconstruction()
    velocity = _waveform("flow_velocity", (1.0, 2.0, 3.0))
    area = _waveform(
        "luminal_area",
        (0.01, 0.02, 0.03),
        time=(0.0, 0.0021, 0.004),
    )

    with pytest.raises(AdmissibilityError, match="not exactly aligned"):
        method.run(
            inputs={"flow_velocity": velocity, "luminal_area": area},
            parameters={},
            context=ExecutionContext(runtime_version="test"),
        )


def test_flow_rate_reconstruction_rejects_non_source_inputs_and_parameters() -> None:
    method = FlowRateReconstruction()
    reconstructed_velocity = _waveform(
        "flow_velocity",
        (1.0, 2.0, 3.0),
        evidence=EvidenceClass.RECONSTRUCTED,
    )
    area = _waveform("luminal_area", (0.01, 0.02, 0.03))

    with pytest.raises(AdmissibilityError, match="SOURCE evidence"):
        method.run(
            inputs={"flow_velocity": reconstructed_velocity, "luminal_area": area},
            parameters={},
            context=ExecutionContext(runtime_version="test"),
        )

    velocity = _waveform("flow_velocity", (1.0, 2.0, 3.0))
    with pytest.raises(AdmissibilityError, match="declares no parameters"):
        method.run(
            inputs={"flow_velocity": velocity, "luminal_area": area},
            parameters={"scale": 1.0},
            context=ExecutionContext(runtime_version="test"),
        )
