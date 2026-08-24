"""Public VascuQuest exception hierarchy.

The hierarchy is intentionally shallow. Low-level implementation exceptions
should be chained as causes while callers receive a stable VascuQuest-level
error describing the semantic failure.
"""


class VascuQuestError(Exception):
    """Base class for all expected public VascuQuest errors."""


class DatasetUnavailableError(VascuQuestError):
    """Raised when a requested dataset, source, or required artifact is unavailable."""


class IntegrityError(VascuQuestError):
    """Raised when source or persisted data fail integrity verification."""


class CapabilityError(VascuQuestError):
    """Raised when a requested scientific capability is unavailable."""


class SchemaError(VascuQuestError):
    """Raised when canonical scientific schema validation or mapping fails."""


class UnitError(VascuQuestError):
    """Raised when units or physical dimensions are incompatible or invalid."""


class SelectionError(VascuQuestError):
    """Raised when a subject, cohort, quantity, or location selection is invalid."""


class AdmissibilityError(VascuQuestError):
    """Raised when scientific inputs fall outside a method's admissible domain."""


class PluginError(VascuQuestError):
    """Raised when plugin discovery, loading, or activation fails."""


class PluginCompatibilityError(PluginError):
    """Raised when a plugin is incompatible with the active VascuQuest protocol."""


class ReproducibilityError(VascuQuestError):
    """Raised when a recorded workflow cannot be reproduced under current conditions."""


class VascuQuestInternalError(VascuQuestError):
    """Raised for unexpected internal VascuQuest failures exposed through the public API."""


__all__ = [
    "AdmissibilityError",
    "CapabilityError",
    "DatasetUnavailableError",
    "IntegrityError",
    "PluginCompatibilityError",
    "PluginError",
    "ReproducibilityError",
    "SchemaError",
    "SelectionError",
    "UnitError",
    "VascuQuestError",
    "VascuQuestInternalError",
]
