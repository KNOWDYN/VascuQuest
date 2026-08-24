"""Frozen capability identifiers and source mappings for PWDB 3275625."""

from __future__ import annotations

from types import MappingProxyType

from vascuquest.domain.location import MeasurementSite

DATASET_FAMILY = "PWDB"
CANONICAL_RECORD_ID = "3275625"
CANONICAL_DOI = "10.5281/zenodo.3275625"

PWDB_MEASUREMENT_SITE_IDS = (
    "AorticRoot",
    "ThorAorta",
    "AbdAorta",
    "IliacBif",
    "Carotid",
    "SupTemporal",
    "SupMidCerebral",
    "Brachial",
    "Radial",
    "Digital",
    "CommonIliac",
    "Femoral",
    "AntTibial",
)
PWDB_MEASUREMENT_SITES = tuple(
    MeasurementSite(site_id) for site_id in PWDB_MEASUREMENT_SITE_IDS
)

SOURCE_SCOPE_ARTIFACT_IDS = MappingProxyType(
    {
        "model_configurations": "model_configurations",
        "model_variations": "model_variations",
        "haemodynamic_parameters": "haemodynamic_parameters",
        "pulse_wave_indices": "pulse_wave_indices",
        "onset_times": "onset_times",
        "geometry": "geometry",
        "common_site_waveforms": "common_site_waveforms_csv",
    }
)

# Capability claims intentionally name only source classes that are exposed
# through the current canonical retrieval surface. The model-variations
# artifact is mapped above for future schema expansion, but is not advertised
# until its upper-case export header and canonical quantity semantics are
# implemented and tested explicitly.
BATCH6_CAPABILITIES = frozenset(
    {
        "subject_model_configuration",
        "haemodynamic_parameters",
        "pulse_wave_indices",
        "onset_times",
    }
)

BATCH7_CAPABILITIES = BATCH6_CAPABILITIES | frozenset(
    {
        "geometry",
        "common_site_waveforms:csv",
    }
)


def artifact_id_for_source_scope(source_scope: str) -> str:
    """Return the canonical manifest artifact supplying one source scope."""

    if not isinstance(source_scope, str) or not source_scope or source_scope != source_scope.strip():
        raise ValueError("source_scope must be a non-empty trimmed string")
    try:
        return SOURCE_SCOPE_ARTIFACT_IDS[source_scope]
    except KeyError as exc:
        raise KeyError(f"unsupported PWDB source scope {source_scope!r}") from exc


__all__ = [
    "BATCH6_CAPABILITIES",
    "BATCH7_CAPABILITIES",
    "CANONICAL_DOI",
    "CANONICAL_RECORD_ID",
    "DATASET_FAMILY",
    "PWDB_MEASUREMENT_SITE_IDS",
    "PWDB_MEASUREMENT_SITES",
    "SOURCE_SCOPE_ARTIFACT_IDS",
    "artifact_id_for_source_scope",
]
