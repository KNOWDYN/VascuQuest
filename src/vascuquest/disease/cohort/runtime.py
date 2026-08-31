"""Streaming execution of frozen parameterized Virtual Disease cohort plans."""

from __future__ import annotations

import os
from pathlib import Path

from vascuquest.api import DatasetSession
from vascuquest.data import ArtifactAcquirer
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.model import DiseasePopulationRequest, DiseaseRunIdentity
from vascuquest.disease.runtime.materialize import materialize_subject
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.errors import IntegrityError

from .bundle import ParameterizedDiseaseCohortBundleWriter
from .model import DiseaseCohortAssignment, ParameterizedDiseaseCohortPlan

COHORT_RUNTIME_IDENTIFIER_PREFIX = "urn:vascuquest:virtual-disease-cohort:"


def cohort_runtime_dataset_identity(plan: ParameterizedDiseaseCohortPlan) -> DatasetIdentity:
    """Return the common content-addressed dataset identity for one cohort plan."""
    if not isinstance(plan, ParameterizedDiseaseCohortPlan):
        raise TypeError("plan must be a ParameterizedDiseaseCohortPlan")
    return DatasetIdentity(
        dataset_family="PWDB-VD",
        record_id=plan.run_id,
        persistent_identifier=f"{COHORT_RUNTIME_IDENTIFIER_PREFIX}{plan.run_id}",
        schema_version=plan.parent_dataset_identity.schema_version,
    )


def subject_disease_run_identity(
    plan: ParameterizedDiseaseCohortPlan,
    assignment: DiseaseCohortAssignment,
) -> DiseaseRunIdentity:
    """Build the exact deployed vd1 single-subject identity behind one assignment."""
    if assignment.canonical_subject_id not in plan.canonical_subject_ids:
        raise IntegrityError("assignment is not a member of the cohort plan")
    request = DiseasePopulationRequest(
        patients=1,
        age_group=assignment.age_years,
        specification=assignment.specification,
        seed=plan.request.seed,
    )
    return DiseaseRunIdentity(
        parent_dataset_identity=plan.parent_dataset_identity,
        canonical_subject_ids=(assignment.canonical_subject_id,),
        request=request,
    )


class ParameterizedDiseaseCohortGenerator:
    """Execute a frozen cohort plan one complete PWDB subject at a time.

    Existing Virtual Disease transformation and solver implementations are
    reused unchanged. Heavy subject state is persisted immediately and then
    released, so memory use is approximately independent of cohort size.
    """

    __slots__ = ("_assembler", "_options")

    def __init__(
        self,
        acquirer: ArtifactAcquirer,
        *,
        offline: bool = False,
        solver_options: SolverOptions | None = None,
    ) -> None:
        if not isinstance(acquirer, ArtifactAcquirer):
            raise TypeError("acquirer must be an ArtifactAcquirer")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        self._assembler = PWDBBaselineAssembler(acquirer, offline=offline)
        self._options = SolverOptions() if solver_options is None else solver_options
        if not isinstance(self._options, SolverOptions):
            raise TypeError("solver_options must be a SolverOptions or None")

    @property
    def solver_options(self) -> SolverOptions:
        return self._options

    def generate(
        self,
        session: DatasetSession,
        plan: ParameterizedDiseaseCohortPlan,
        destination: str | os.PathLike[str],
        *,
        resume: bool = False,
    ) -> Path:
        if not isinstance(session, DatasetSession):
            raise TypeError("session must be a DatasetSession")
        if not isinstance(plan, ParameterizedDiseaseCohortPlan):
            raise TypeError("plan must be a ParameterizedDiseaseCohortPlan")
        if session.identity != plan.parent_dataset_identity:
            raise IntegrityError("cohort plan parent dataset identity does not match opened dataset")
        if not isinstance(resume, bool):
            raise TypeError("resume must be a boolean")

        runtime_identity = cohort_runtime_dataset_identity(plan)
        writer = ParameterizedDiseaseCohortBundleWriter(
            destination,
            plan,
            runtime_identity,
            resume=resume,
        )

        for index, assignment in enumerate(plan.assignments, start=1):
            subject_id = assignment.canonical_subject_id
            if writer.subject_complete(subject_id):
                print(
                    f"[{index}/{plan.request.patients}] subject {subject_id}: "
                    "verified checkpoint, skipped",
                    flush=True,
                )
                continue
            subject_run = subject_disease_run_identity(plan, assignment)
            print(
                f"[{index}/{plan.request.patients}] subject {subject_id}: "
                f"{assignment.severity_parameter}={assignment.severity_value:.6g} solving",
                flush=True,
            )
            try:
                state = materialize_subject(
                    session,
                    runtime_identity=runtime_identity,
                    run_identity=subject_run,
                    subject_id=subject_id,
                    assembler=self._assembler,
                    solver_options=self._options,
                )
                writer.write_subject(
                    assignment,
                    state,
                    subject_disease_run_id=subject_run.run_id,
                )
            except Exception as exc:
                writer.record_failure(subject_id, exc)
                raise
            print(
                f"[{index}/{plan.request.patients}] subject {subject_id}: complete",
                flush=True,
            )

        return writer.finalize()


__all__ = [
    "COHORT_RUNTIME_IDENTIFIER_PREFIX",
    "ParameterizedDiseaseCohortGenerator",
    "cohort_runtime_dataset_identity",
    "subject_disease_run_identity",
]
