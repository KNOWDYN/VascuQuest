"""Canonical backend for PWDB Zenodo record 3275625.

The backend is assembled incrementally. This package-level surface exposes
stable source/capability identities without performing data acquisition at
import time.
"""

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
    "BATCH6_CAPABILITIES",
    "BATCH7_CAPABILITIES",
    "CANONICAL_DOI",
    "CANONICAL_RECORD_ID",
    "DATASET_FAMILY",
    "PWDB_MEASUREMENT_SITE_IDS",
    "PWDB_MEASUREMENT_SITES",
    "artifact_id_for_source_scope",
]
