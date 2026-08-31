"""First-party Virtual Disease v1 public surface.

The public surface exposes the frozen disease catalogue/request contracts,
causal runtime population generator, explicit portable bundle export, and the
modelled-evidence boundary. It does not imply clinical validation.
"""

from .api import generate_population
from .catalogue import preset, presets, specification
from .cohort import (
    DiseaseCohortAssignment,
    DiseaseCohortRejection,
    PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION,
    ParameterizedDiseaseCohortGenerator,
    ParameterizedDiseaseCohortPlan,
    ParameterizedDiseaseCohortRequest,
    create_parameterized_cohort_plan,
    generate_parameterized_cohort,
    inspect_parameterized_cohort_bundle,
    read_cohort_plan,
    severity_parameter,
    verify_parameterized_cohort_bundle,
    write_cohort_plan,
)
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
    "DiseaseCohortAssignment",
    "DiseaseCohortRejection",
    "DiseaseCondition",
    "DiseasePopulationRequest",
    "DiseaseQuantityStatus",
    "DiseaseRunIdentity",
    "DiseaseSelection",
    "DiseaseSpecification",
    "PARAMETERIZED_DISEASE_COHORT_CONTRACT_VERSION",
    "ParameterizedDiseaseCohortGenerator",
    "ParameterizedDiseaseCohortPlan",
    "ParameterizedDiseaseCohortRequest",
    "RuntimeDiseaseDataset",
    "RuntimeDiseaseStore",
    "RuntimeGeometrySegment",
    "RuntimeSubjectState",
    "VIRTUAL_DISEASE_CONTRACT_VERSION",
    "VirtualDiseasePopulationGenerator",
    "create_parameterized_cohort_plan",
    "disease_vector_name",
    "generate_parameterized_cohort",
    "generate_population",
    "inspect_parameterized_cohort_bundle",
    "preset",
    "presets",
    "read_cohort_plan",
    "select_population",
    "severity_parameter",
    "specification",
    "verify_parameterized_cohort_bundle",
    "write_cohort_plan",
    "write_runtime_bundle",
]
