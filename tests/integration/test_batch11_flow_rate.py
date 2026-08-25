from __future__ import annotations

import numpy as np
import pytest

import vascuquest as vq
from vascuquest.bootstrap import _compose_session
from vascuquest.domain import (
    Coordinate,
    MeasurementSite,
    PathPosition,
    SubjectKey,
    VirtualSubject,
    Waveform,
)
from vascuquest.errors import AdmissibilityError, CapabilityError
from vascuquest.methods import (
    FLOW_RATE_RECONSTRUCTION_ID,
    create_flow_rate_reconstruction,
)
from vascuquest.plugins.descriptor import (
    ComponentDescriptor,
    ComponentKind,
    SUPPORTED_PROTOCOL_VERSION,
)
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.backend import GeometryRequest, QuantityRequest, WaveformRequest
from vascuquest.schema import load_canonical_schema


class FlowRateFixtureBackend:
    def __init__(self) -> None:
        self.schema = load_canonical_schema()
        self._identity = vq.DatasetIdentity(
            dataset_family=self.schema.dataset_family,
            record_id=self.schema.canonical_record_id,
            persistent_identifier=self.schema.canonical_doi,
            schema_version=self.schema.schema_version,
        )
        self._site = MeasurementSite("AorticRoot")
        self._descriptor = ComponentDescriptor(
            kind=ComponentKind.BACKEND,
            name="Batch 11 flow-rate fixture backend",
            qualified_id="tests:batch11-flow-rate-backend",
            implementation_version="1",
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="tests",
            distribution_version="1",
            summary="Deterministic common-site waveform fixture for Batch 11 integration.",
        )

    @property
    def descriptor(self) -> ComponentDescriptor:
        return self._descriptor

    def identity(self):
        return self._identity

    def capabilities(self):
        return frozenset({"common_site_waveforms:csv"})

    def subjects(self, request=None):
        assert request is None
        return (VirtualSubject(SubjectKey(self._identity, "1")),)

    def locations(self, request=None):
        assert request is None
        return (self._site,)

    def get_quantity(self, request: QuantityRequest):
        raise CapabilityError(
            f"Batch 11 fixture exposes waveform inputs only, not {request.quantity!r}"
        )

    def get_waveform(self, request: WaveformRequest):
        if request.signal == "flow_velocity":
            values = (1.0, 2.0, -1.0)
        elif request.signal == "luminal_area":
            values = (0.01, 0.02, 0.03)
        else:
            raise CapabilityError(request.signal)
        return Waveform(
            dataset_identity=self._identity,
            quantity=self.schema.quantity(request.signal),
            values=np.asarray(values, dtype=float),
            provenance_ref=(
                f"fixture:{request.signal}:{request.subject.canonical_subject_id}:"
                f"{type(request.location).__name__}"
            ),
            dimensions=("time",),
            coordinates=(
                Coordinate("time", np.asarray((0.0, 0.002, 0.004)), unit="s"),
            ),
            subject=request.subject,
            location=request.location,
        )

    def geometry(self, request: GeometryRequest):
        raise CapabilityError("geometry is not required by the Batch 11 fixture")


def _session():
    backend = FlowRateFixtureBackend()
    registry = PluginRegistry()
    registry.register_factory(
        lambda: backend,
        expected_kind=ComponentKind.BACKEND,
        built_in=True,
    )
    registry.register_factory(
        create_flow_rate_reconstruction,
        expected_kind=ComponentKind.DERIVATION,
        built_in=True,
    )
    return _compose_session(backend, registry=registry)


def test_session_derive_resolves_authoritative_common_site_inputs() -> None:
    session = _session()
    result = session.derive(
        FLOW_RATE_RECONSTRUCTION_ID,
        subjects="1",
        location=MeasurementSite("AorticRoot"),
    )

    np.testing.assert_allclose(result.values, np.asarray((0.01, 0.04, -0.03)))
    assert result.quantity.canonical_name == "flow_rate"
    assert result.quantity.canonical_unit == "m^3/s"
    assert result.evidence is vq.EvidenceClass.RECONSTRUCTED
    assert result.method_id == FLOW_RATE_RECONSTRUCTION_ID
    assert result.subject == SubjectKey(session.identity, "1")
    assert result.location == MeasurementSite("AorticRoot")


def test_public_plugin_catalog_exposes_builtin_flow_rate_reconstruction() -> None:
    descriptors = vq.plugins.list(ComponentKind.DERIVATION)
    ids = {descriptor.qualified_id for descriptor in descriptors}
    assert FLOW_RATE_RECONSTRUCTION_ID in ids

    descriptor = vq.plugins.describe(
        FLOW_RATE_RECONSTRUCTION_ID,
        kind=ComponentKind.DERIVATION,
    )
    assert descriptor.kind is ComponentKind.DERIVATION
    assert descriptor.citations


def test_session_derive_rejects_path_position_instead_of_substituting_site_data() -> None:
    session = _session()
    with pytest.raises(AdmissibilityError, match="incompatible location kind"):
        session.derive(
            FLOW_RATE_RECONSTRUCTION_ID,
            subjects="1",
            location=PathPosition("aorta_foot", 0),
        )


def test_session_derive_requires_single_subject_for_automatic_waveform_resolution() -> None:
    session = _session()
    cohort = session.select(subject_ids=("1",))
    with pytest.raises(CapabilityError, match="exactly one virtual subject"):
        session.derive(
            FLOW_RATE_RECONSTRUCTION_ID,
            subjects=cohort,
            location=MeasurementSite("AorticRoot"),
        )
