"""Stable public Python surface for VascuQuest core v1."""

from ._version import __version__
from .api import DatasetSession
from .bootstrap import open_dataset, register_source
from .domain import (
    Cohort,
    DatasetIdentity,
    EvidenceClass,
    MeasurementSite,
    PathPosition,
    QuantityDefinition,
    ScientificResult,
    SegmentLocation,
    SubjectKey,
    VascularLocation,
    VirtualSubject,
    Waveform,
)
from .errors import (
    AdmissibilityError,
    CapabilityError,
    DatasetUnavailableError,
    IntegrityError,
    NumericalMethodError,
    PluginCompatibilityError,
    PluginError,
    ReproducibilityError,
    SchemaError,
    SelectionError,
    UnitError,
    VascuQuestError,
    VascuQuestInternalError,
)
from .provenance import ProvenanceRecord

__all__ = [
    "AdmissibilityError",
    "CapabilityError",
    "Cohort",
    "DatasetIdentity",
    "DatasetSession",
    "DatasetUnavailableError",
    "EvidenceClass",
    "IntegrityError",
    "MeasurementSite",
    "NumericalMethodError",
    "PathPosition",
    "PluginCompatibilityError",
    "PluginError",
    "ProvenanceRecord",
    "QuantityDefinition",
    "ReproducibilityError",
    "SchemaError",
    "ScientificResult",
    "SegmentLocation",
    "SelectionError",
    "SubjectKey",
    "UnitError",
    "VascularLocation",
    "VascuQuestError",
    "VascuQuestInternalError",
    "VirtualSubject",
    "Waveform",
    "__version__",
    "open_dataset",
    "register_source",
]
