"""Structured provenance construction and deterministic serialization."""

from .builder import ProvenanceBuilder
from .model import (
    CanonicalJSON,
    ComponentReference,
    ProvenanceRecord,
    SourceArtifactReference,
)
from .serialization import (
    provenance_from_dict,
    provenance_from_json,
    provenance_to_dict,
    provenance_to_json,
    result_metadata_from_dict,
    result_metadata_from_json,
    result_metadata_to_dict,
    result_metadata_to_json,
)

__all__ = [
    "CanonicalJSON",
    "ComponentReference",
    "ProvenanceBuilder",
    "ProvenanceRecord",
    "SourceArtifactReference",
    "provenance_from_dict",
    "provenance_from_json",
    "provenance_to_dict",
    "provenance_to_json",
    "result_metadata_from_dict",
    "result_metadata_from_json",
    "result_metadata_to_dict",
    "result_metadata_to_json",
]
