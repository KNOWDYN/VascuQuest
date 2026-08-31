"""Content-addressed runtime dataset identity for Virtual Disease v1."""

from __future__ import annotations

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.model import DiseaseRunIdentity

RUNTIME_DATASET_FAMILY = "PWDB-VD"
RUNTIME_IDENTIFIER_PREFIX = "urn:vascuquest:virtual-disease:"


def runtime_dataset_identity(run_identity: DiseaseRunIdentity) -> DatasetIdentity:
    """Return the exact in-memory dataset identity for one disease run."""

    if not isinstance(run_identity, DiseaseRunIdentity):
        raise TypeError("run_identity must be a DiseaseRunIdentity")
    return DatasetIdentity(
        dataset_family=RUNTIME_DATASET_FAMILY,
        record_id=run_identity.run_id,
        persistent_identifier=f"{RUNTIME_IDENTIFIER_PREFIX}{run_identity.run_id}",
        schema_version=run_identity.parent_dataset_identity.schema_version,
    )


__all__ = [
    "RUNTIME_DATASET_FAMILY",
    "RUNTIME_IDENTIFIER_PREFIX",
    "runtime_dataset_identity",
]
