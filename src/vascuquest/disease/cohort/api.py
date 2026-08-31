"""Public convenience API for parameterized Virtual Disease cohorts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vascuquest.bootstrap import open_dataset
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.model import DiseaseCondition
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.errors import DatasetUnavailableError

from .model import ParameterizedDiseaseCohortPlan, ParameterizedDiseaseCohortRequest
from .planner import plan_parameterized_cohort
from .runtime import ParameterizedDiseaseCohortGenerator


def _acquisition_context(source: str | Path | None) -> tuple[ArtifactAcquirer, Path | None]:
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    source_path = None
    if source is not None:
        source_path = Path(source).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise DatasetUnavailableError(
                f"source must identify an existing local PWDB directory: {source_path}"
            )
        try:
            registry.register_local(source_path)
        except ValueError as exc:
            raise DatasetUnavailableError(str(exc)) from exc
    return ArtifactAcquirer(paths, registry), source_path


def create_parameterized_cohort_plan(
    *,
    patients: int,
    age_min: int,
    age_max: int,
    condition: DiseaseCondition | str,
    severity_min: float,
    severity_max: float,
    fixed_parameters: Mapping[str, object] | None = None,
    seed: int = 0,
    dataset: str = "pwdb:3275625",
    source: str | Path | None = None,
    offline: bool = False,
    solver_options: SolverOptions | None = None,
) -> ParameterizedDiseaseCohortPlan:
    """Create a frozen subject/severity plan without running disease time integration."""
    request = ParameterizedDiseaseCohortRequest.from_mapping(
        patients=patients,
        age_min=age_min,
        age_max=age_max,
        condition=condition,
        severity_min=severity_min,
        severity_max=severity_max,
        fixed_parameters=fixed_parameters,
        seed=seed,
    )
    session = open_dataset(dataset, source=source, offline=offline)
    acquirer, _ = _acquisition_context(source)
    assembler = PWDBBaselineAssembler(acquirer, offline=offline)
    return plan_parameterized_cohort(
        session,
        request,
        assembler=assembler,
        solver_options=solver_options,
    )


def generate_parameterized_cohort(
    plan: ParameterizedDiseaseCohortPlan,
    *,
    destination: str | Path,
    dataset: str = "pwdb:3275625",
    source: str | Path | None = None,
    offline: bool = False,
    solver_options: SolverOptions | None = None,
    resume: bool = False,
) -> Path:
    """Execute and persist one frozen parameterized cohort plan subject-by-subject."""
    if not isinstance(plan, ParameterizedDiseaseCohortPlan):
        raise TypeError("plan must be a ParameterizedDiseaseCohortPlan")
    session = open_dataset(dataset, source=source, offline=offline)
    acquirer, _ = _acquisition_context(source)
    generator = ParameterizedDiseaseCohortGenerator(
        acquirer,
        offline=offline,
        solver_options=solver_options,
    )
    return generator.generate(session, plan, destination, resume=resume)


__all__ = ["create_parameterized_cohort_plan", "generate_parameterized_cohort"]
