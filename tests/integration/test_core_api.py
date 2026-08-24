from __future__ import annotations

import pytest

import vascuquest as vq
from vascuquest.bootstrap import _compose_session
from vascuquest.domain import (
    Coordinate,
    MeasurementSite,
    PathPosition,
    ScientificResult,
    SubjectKey,
    VirtualSubject,
    Waveform,
)
from vascuquest.errors import CapabilityError, PluginError, ReproducibilityError
from vascuquest.plugins.descriptor import (
    ComponentDescriptor,
    ComponentKind,
    SUPPORTED_PROTOCOL_VERSION,
)
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.backend import GeometryRequest, QuantityRequest, WaveformRequest
from vascuquest.provenance import ProvenanceRecord
from vascuquest.schema import load_canonical_schema


class FakeCoreBackend:
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
            name="Fake core backend",
            qualified_id="tests:fake-core",
            implementation_version="1",
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="tests",
            distribution_version="1",
            summary="Deterministic Batch-10 integration backend.",
        )

    @property
    def descriptor(self) -> ComponentDescriptor:
        return self._descriptor

    def identity(self):
        return self._identity

    def capabilities(self):
        return frozenset({"subject_model_configuration", "geometry", "common_site_waveforms:csv"})

    def subjects(self, request=None):
        assert request is None
        return tuple(
            VirtualSubject(SubjectKey(self._identity, subject_id))
            for subject_id in ("1", "2")
        )

    def locations(self, request=None):
        assert request is None
        return (self._site,)

    def get_quantity(self, request: QuantityRequest):
        if request.quantity != "age":
            raise CapabilityError(request.quantity)
        values_by_subject = {"1": 25.0, "2": 55.0}
        if request.subject is not None:
            ids = (request.subject.canonical_subject_id,)
            values = values_by_subject[ids[0]]
            dimensions = ()
            coordinates = ()
            subject = request.subject
            cohort = None
        elif request.cohort is not None:
            ids = request.cohort.canonical_subject_ids
            values = tuple(values_by_subject[item] for item in ids)
            dimensions = ("subject",)
            coordinates = (Coordinate("subject", ids),)
            subject = None
            cohort = request.cohort
        else:
            ids = ("1", "2")
            values = (25.0, 55.0)
            dimensions = ("subject",)
            coordinates = (Coordinate("subject", ids),)
            subject = None
            cohort = None
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=self.schema.quantity_schema("age").definition,
            values=values,
            provenance_ref="fake-age",
            dimensions=dimensions,
            coordinates=coordinates,
            subject=subject,
            cohort=cohort,
        )

    def get_waveform(self, request: WaveformRequest):
        if isinstance(request.location, PathPosition):
            raise CapabilityError("path-resolved waveform support is not validated")
        return Waveform(
            dataset_identity=self._identity,
            quantity=self.schema.quantity_schema("pressure").definition,
            values=(80.0, 120.0),
            provenance_ref="fake-waveform",
            dimensions=("time",),
            coordinates=(Coordinate("time", (0.0, 0.002), unit="s"),),
            subject=request.subject,
            location=request.location,
        )

    def geometry(self, request: GeometryRequest):
        if request.subject is None:
            raise CapabilityError("subject required")
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=self.schema.quantity_schema("vascular_geometry").definition,
            values=(("1", 0.1),),
            provenance_ref="fake-geometry",
            dimensions=("segment",),
            coordinates=(Coordinate("segment", ("1",)),),
            subject=request.subject,
            location=request.location,
        )


def fake_session():
    backend = FakeCoreBackend()
    registry = PluginRegistry()
    registry.register_factory(
        lambda: backend,
        expected_kind=ComponentKind.BACKEND,
        built_in=True,
    )
    return _compose_session(backend, registry=registry), backend


def test_open_dataset_is_lightweight_and_reports_path_deferred():
    session = vq.open_dataset(offline=True)
    assert session.identity.record_id == "3275625"
    status = session.status()
    assert status.path_resolved_supported is False
    assert status.path_validation_state == "unavailable_pending_batch8_tier3_validation"


def test_core_session_routes_subject_selection_retrieval_and_source_reproduction():
    session, backend = fake_session()
    assert session.identity == backend.identity()
    assert session.subject("1").canonical_subject_id == "1"
    assert tuple(item.canonical_subject_id for item in session.subjects()) == ("1", "2")

    cohort = session.select(where={"age": 55.0})
    assert cohort.canonical_subject_ids == ("2",)
    age = session.get("age", subjects=cohort)
    assert age.values == (55.0,)

    waveform = session.waveform(
        "pressure",
        subject="1",
        location=MeasurementSite("AorticRoot"),
    )
    assert waveform.values == (80.0, 120.0)
    assert waveform.time_coordinate.unit == "s"

    geometry = session.geometry(subject="1")
    assert geometry.quantity.canonical_name == "vascular_geometry"

    provenance = ProvenanceRecord(
        record_id="source-age-1",
        dataset_identity=session.identity,
        schema_version=session.identity.schema_version,
        evidence=vq.EvidenceClass.SOURCE,
        subject=SubjectKey(session.identity, "1"),
        output_identity="age",
    )
    reproduced = session.reproduce(provenance)
    assert reproduced.values == 25.0


def test_unimplemented_components_fail_clearly_and_path_is_never_substituted():
    session, _ = fake_session()
    with pytest.raises(PluginError):
        session.derive("missing:derivation", subjects="1")
    with pytest.raises(PluginError):
        session.model("missing:operator", subjects="1")
    with pytest.raises(PluginError):
        session.discover("missing:discovery", cohort=session.select(subject_ids=("1",)))

    result = session.get("age", subjects="1")
    with pytest.raises(PluginError):
        session.export(result, "missing:exporter", object())

    with pytest.raises(CapabilityError, match="path-resolved"):
        session.waveform(
            "pressure",
            subject="1",
            location=PathPosition("aorta_foot", 0),
        )

    non_source = ProvenanceRecord(
        record_id="derived-age",
        dataset_identity=session.identity,
        schema_version=session.identity.schema_version,
        evidence=vq.EvidenceClass.DERIVED,
        method_id="missing:derivation",
        output_identity="age",
    )
    with pytest.raises(ReproducibilityError, match="SOURCE retrievals only"):
        session.reproduce(non_source)
