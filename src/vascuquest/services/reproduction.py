"""Strict reproduction for workflows that can be reconstructed unambiguously."""

from __future__ import annotations

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.domain.result import ScientificResult
from vascuquest.errors import ReproducibilityError
from vascuquest.provenance.model import ProvenanceRecord
from vascuquest.schema import CanonicalSchema, load_canonical_schema

from .retrieval import RetrievalService


class ReproductionService:
    """Reproduce only provenance records whose execution semantics are complete.

    Batch 10 can reproduce canonical SOURCE retrievals because their subject,
    cohort, location and canonical output identity are present in provenance.
    Non-source scientific workflows remain rejected until their later execution
    components and workflow-input binding are implemented and version-checked.
    """

    __slots__ = ("_retrieval", "_schema", "_identity")

    def __init__(
        self,
        retrieval: RetrievalService,
        identity: DatasetIdentity,
        *,
        schema: CanonicalSchema | None = None,
    ) -> None:
        if not isinstance(retrieval, RetrievalService):
            raise TypeError("retrieval must be a RetrievalService")
        if not isinstance(identity, DatasetIdentity):
            raise TypeError("identity must be a DatasetIdentity")
        resolved_schema = load_canonical_schema() if schema is None else schema
        if not isinstance(resolved_schema, CanonicalSchema):
            raise TypeError("schema must be a CanonicalSchema")
        self._retrieval = retrieval
        self._schema = resolved_schema
        self._identity = identity

    def reproduce(self, provenance: ProvenanceRecord) -> ScientificResult:
        if not isinstance(provenance, ProvenanceRecord):
            raise TypeError("provenance must be a ProvenanceRecord")
        if provenance.dataset_identity != self._identity:
            raise ReproducibilityError(
                "provenance dataset identity does not match the active session"
            )
        if provenance.evidence is not EvidenceClass.SOURCE:
            raise ReproducibilityError(
                "Batch 10 reproduces SOURCE retrievals only; derived/modelled/discovery "
                "workflow reproduction requires the exact later registered component and "
                "input-binding record"
            )
        if provenance.output_identity is None:
            raise ReproducibilityError("source provenance lacks an output identity")

        quantity_name = provenance.output_identity.split("@", 1)[0]
        try:
            quantity_schema = self._schema.quantity_schema(quantity_name)
        except KeyError as exc:
            raise ReproducibilityError(
                f"provenance output quantity {quantity_name!r} is absent from the active schema"
            ) from exc

        if quantity_schema.category == "waveform_signal":
            if provenance.subject is None or provenance.location is None:
                raise ReproducibilityError(
                    "waveform provenance must contain one subject and vascular location"
                )
            return self._retrieval.waveform(
                quantity_name,
                subject=provenance.subject,
                location=provenance.location,
            )

        if quantity_name == "vascular_geometry":
            if provenance.subject is None:
                raise ReproducibilityError("geometry provenance must contain one subject")
            return self._retrieval.geometry(
                subject=provenance.subject,
                location=provenance.location,
            )

        if provenance.subject is not None:
            subjects: object = provenance.subject
        else:
            subjects = provenance.cohort
        return self._retrieval.get(
            quantity_name,
            subjects=subjects,
            location=provenance.location,
        )


__all__ = ["ReproductionService"]
