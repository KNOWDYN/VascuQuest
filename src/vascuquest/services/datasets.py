"""Dataset inspection services for the storage-independent public facade."""

from __future__ import annotations

from dataclasses import dataclass

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.domain.location import VascularLocation
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.subject import VirtualSubject
from vascuquest.errors import SelectionError
from vascuquest.ports.backend import CapabilitySet, DatasetBackend
from vascuquest.schema import CanonicalSchema, load_canonical_schema


@dataclass(frozen=True, slots=True)
class DatasetStatus:
    """Lightweight capability status that never triggers large acquisition."""

    identity: DatasetIdentity
    capabilities: CapabilitySet
    path_resolved_supported: bool
    path_validation_state: str


class DatasetService:
    """Expose dataset identity, schema definitions, subjects and locations."""

    __slots__ = ("_backend", "_schema")

    def __init__(
        self,
        backend: DatasetBackend,
        *,
        schema: CanonicalSchema | None = None,
    ) -> None:
        if not isinstance(backend, DatasetBackend):
            raise TypeError("backend must conform to DatasetBackend")
        resolved_schema = load_canonical_schema() if schema is None else schema
        if not isinstance(resolved_schema, CanonicalSchema):
            raise TypeError("schema must be a CanonicalSchema")
        identity = backend.identity()
        if (
            resolved_schema.dataset_family != identity.dataset_family
            or resolved_schema.canonical_record_id != identity.record_id
            or resolved_schema.canonical_doi != identity.persistent_identifier
            or resolved_schema.schema_version != identity.schema_version
        ):
            raise ValueError("schema identity does not match backend dataset identity")
        self._backend = backend
        self._schema = resolved_schema

    @property
    def identity(self) -> DatasetIdentity:
        return self._backend.identity()

    def status(self) -> DatasetStatus:
        capabilities = self.capabilities()
        path_supported = any(
            capability.startswith("path_resolved_waveforms")
            for capability in capabilities
        )
        return DatasetStatus(
            identity=self.identity,
            capabilities=capabilities,
            path_resolved_supported=path_supported,
            path_validation_state=(
                "validated_and_available"
                if path_supported
                else "unavailable_not_in_release_scope"
            ),
        )

    def capabilities(self) -> CapabilitySet:
        return self._backend.capabilities()

    def quantities(self) -> tuple[QuantityDefinition, ...]:
        """Return canonical definitions without acquiring source artifacts."""

        return tuple(item.definition for item in self._schema.quantities)

    def subjects(self) -> tuple[VirtualSubject, ...]:
        return self._backend.subjects()

    def subject(self, subject_id: str) -> VirtualSubject:
        if not isinstance(subject_id, str) or not subject_id or subject_id != subject_id.strip():
            raise SelectionError("subject_id must be a non-empty trimmed string")
        for subject in self.subjects():
            if subject.canonical_subject_id == subject_id:
                return subject
        raise SelectionError(f"unknown subject {subject_id!r} for {self.identity.record_id}")

    def locations(self) -> tuple[VascularLocation, ...]:
        return self._backend.locations()


__all__ = ["DatasetService", "DatasetStatus"]