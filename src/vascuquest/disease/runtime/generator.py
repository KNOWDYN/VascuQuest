"""Generate complete in-memory Virtual Disease populations from canonical PWDB."""

from __future__ import annotations

from vascuquest.api import DatasetSession
from vascuquest.data import ArtifactAcquirer
from vascuquest.domain.cohort import Cohort
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.model import DiseasePopulationRequest
from vascuquest.disease.selection import select_population
from vascuquest.disease.solver.model import SolverOptions

from .dataset import RuntimeDiseaseDataset
from .identity import runtime_dataset_identity
from .materialize import materialize_subject
from .quantities import runtime_quantity_statuses
from .store import RuntimeDiseaseStore


class VirtualDiseasePopulationGenerator:
    """Execute the PR-4 runtime population pipeline without mutating PWDB."""

    __slots__ = ("_assembler", "_options", "_store")

    def __init__(
        self,
        acquirer: ArtifactAcquirer,
        *,
        offline: bool = False,
        solver_options: SolverOptions | None = None,
        store: RuntimeDiseaseStore | None = None,
    ) -> None:
        if not isinstance(acquirer, ArtifactAcquirer):
            raise TypeError("acquirer must be an ArtifactAcquirer")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        self._assembler = PWDBBaselineAssembler(acquirer, offline=offline)
        self._options = SolverOptions() if solver_options is None else solver_options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("solver_options must be a SolverOptions or None")
        self._store = RuntimeDiseaseStore() if store is None else store
        if not isinstance(self._store, RuntimeDiseaseStore):
            raise TypeError("store must be a RuntimeDiseaseStore or None")

    @property
    def store(self) -> RuntimeDiseaseStore:
        return self._store

    @property
    def solver_options(self) -> SolverOptions:
        return self._options

    def generate(
        self,
        session: DatasetSession,
        request: DiseasePopulationRequest,
    ) -> RuntimeDiseaseDataset:
        """Generate or retrieve one deterministic disease-population runtime dataset."""

        if not isinstance(session, DatasetSession):
            raise TypeError("session must be a DatasetSession")
        if not isinstance(request, DiseasePopulationRequest):
            raise TypeError("request must be a DiseasePopulationRequest")

        selection = select_population(session, request)
        run_identity = selection.run_identity
        if self._store.contains(run_identity.run_id):
            return self._store.get(run_identity.run_id)

        identity = runtime_dataset_identity(run_identity)
        runtime_cohort = Cohort(
            dataset_identity=identity,
            canonical_subject_ids=run_identity.canonical_subject_ids,
            ordering_rule=selection.cohort.ordering_rule,
            selection_specification=selection.cohort.selection_specification
            + (
                f"virtual_disease_condition={request.specification.condition.value}",
                f"virtual_disease_run_id={run_identity.run_id}",
                f"parent_dataset={session.identity.dataset_family}:{session.identity.record_id}",
            ),
            inclusion_filters=selection.cohort.inclusion_filters,
            exclusion_filters=selection.cohort.exclusion_filters,
            plausibility_filter=selection.cohort.plausibility_filter,
        )

        states = tuple(
            materialize_subject(
                session,
                runtime_identity=identity,
                run_identity=run_identity,
                subject_id=subject_id,
                assembler=self._assembler,
                solver_options=self._options,
            )
            for subject_id in run_identity.canonical_subject_ids
        )
        dataset = RuntimeDiseaseDataset(
            identity=identity,
            parent_identity=session.identity,
            run_identity=run_identity,
            cohort=runtime_cohort,
            subject_states=states,
            quantity_statuses=runtime_quantity_statuses(
                request.specification.condition
            ),
        )
        return self._store.put(dataset)


__all__ = ["VirtualDiseasePopulationGenerator"]
