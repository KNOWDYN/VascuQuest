"""First-party Virtual Disease v1 contract surface.

PR 1 exposes only immutable request/catalogue/selection contracts. No disease
haemodynamics or runtime disease population can be generated yet.
"""

from .catalogue import preset, presets, specification
from .model import (
    DiseaseCondition,
    DiseasePopulationRequest,
    DiseaseQuantityStatus,
    DiseaseRunIdentity,
    DiseaseSpecification,
    VIRTUAL_DISEASE_CONTRACT_VERSION,
)
from .naming import disease_vector_name
from .selection import DiseaseSelection, select_population

__all__ = [
    "DiseaseCondition",
    "DiseasePopulationRequest",
    "DiseaseQuantityStatus",
    "DiseaseRunIdentity",
    "DiseaseSelection",
    "DiseaseSpecification",
    "VIRTUAL_DISEASE_CONTRACT_VERSION",
    "disease_vector_name",
    "preset",
    "presets",
    "select_population",
    "specification",
]
