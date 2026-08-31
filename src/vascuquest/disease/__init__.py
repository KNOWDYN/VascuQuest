"""First-party Virtual Disease v1 public surface.

The public surface exposes the frozen disease catalogue/request contracts,
causal runtime population generator, explicit portable bundle export, and the
modelled-evidence boundary. It does not imply clinical validation.
"""

from .api import generate_population
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
from .runtime import (
    RuntimeDiseaseDataset,
    RuntimeDiseaseStore,
    RuntimeGeometrySegment,
    RuntimeSubjectState,
    VirtualDiseasePopulationGenerator,
)
from .runtime.bundle import write_runtime_bundle
from .selection import DiseaseSelection, select_population

__all__ = [
    "DiseaseCondition",
    "DiseasePopulationRequest",
    "DiseaseQuantityStatus",
    "DiseaseRunIdentity",
    "DiseaseSelection",
    "DiseaseSpecification",
    "RuntimeDiseaseDataset",
    "RuntimeDiseaseStore",
    "RuntimeGeometrySegment",
    "RuntimeSubjectState",
    "VIRTUAL_DISEASE_CONTRACT_VERSION",
    "VirtualDiseasePopulationGenerator",
    "disease_vector_name",
    "generate_population",
    "preset",
    "presets",
    "select_population",
    "specification",
    "write_runtime_bundle",
]
