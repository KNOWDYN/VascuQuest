"""Top-level public surface for VascuQuest.

Only stable, dependency-light symbols are exposed at import time during the
initial implementation stage. Dataset sessions and other research-facing API
objects will be added here only when their implementation batches are complete.
"""

from ._version import __version__
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

__all__ = [
    "AdmissibilityError",
    "CapabilityError",
    "DatasetUnavailableError",
    "IntegrityError",
    "NumericalMethodError",
    "PluginCompatibilityError",
    "PluginError",
    "ReproducibilityError",
    "SchemaError",
    "SelectionError",
    "UnitError",
    "VascuQuestError",
    "VascuQuestInternalError",
    "__version__",
]
