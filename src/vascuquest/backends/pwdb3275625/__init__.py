"""Canonical backend for PWDB Zenodo record 3275625."""

from .backend import ArtifactResolver, PWDB3275625Backend
from .capabilities import (
    BATCH6_CAPABILITIES,
    BATCH7_CAPABILITIES,
    CANONICAL_DOI,
    CANONICAL_RECORD_ID,
    DATASET_FAMILY,
    PWDB_MEASUREMENT_SITE_IDS,
    PWDB_MEASUREMENT_SITES,
    artifact_id_for_source_scope,
)

__all__ = [
    "ArtifactResolver",
    "BATCH6_CAPABILITIES",
    "BATCH7_CAPABILITIES",
    "CANONICAL_DOI",
    "CANONICAL_RECORD_ID",
    "DATASET_FAMILY",
    "PWDB3275625Backend",
    "PWDB_MEASUREMENT_SITE_IDS",
    "PWDB_MEASUREMENT_SITES",
    "artifact_id_for_source_scope",
]
