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
from .geometry_reader import GeometryCSVArchiveReader, GeometrySegment, GeometrySource
from .waveform_reader import SAMPLE_RATE_HZ, WaveformCSVArchiveReader, WaveformSeries

__all__ = [
    "ArtifactResolver",
    "BATCH6_CAPABILITIES",
    "BATCH7_CAPABILITIES",
    "CANONICAL_DOI",
    "CANONICAL_RECORD_ID",
    "DATASET_FAMILY",
    "GeometryCSVArchiveReader",
    "GeometrySegment",
    "GeometrySource",
    "PWDB3275625Backend",
    "PWDB_MEASUREMENT_SITE_IDS",
    "PWDB_MEASUREMENT_SITES",
    "SAMPLE_RATE_HZ",
    "WaveformCSVArchiveReader",
    "WaveformSeries",
    "artifact_id_for_source_scope",
]
