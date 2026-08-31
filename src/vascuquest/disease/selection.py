"""Deterministic age-group population selection for Virtual Disease v1."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.errors import SelectionError

from .model import DiseasePopulationRequest, DiseaseRunIdentity


class DiseaseSelectionSession(Protocol):
    """Minimal session surface required by the contract-only selector."""

    @property
    def identity(self) -> DatasetIdentity:
        ...

    def select(
        self,
        *,
        subject_ids: object | None = None,
        where: object | None = None,
    ) -> Cohort:
        ...


@dataclass(frozen=True, slots=True)
class DiseaseSelection:
    """Selected healthy baseline cohort plus its deterministic run identity."""

    cohort: Cohort
    run_identity: DiseaseRunIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.cohort, Cohort):
            raise TypeError("cohort must be a Cohort")
        if not isinstance(self.run_identity, DiseaseRunIdentity):
            raise TypeError("run_identity must be a DiseaseRunIdentity")
        if self.cohort.dataset_identity != self.run_identity.parent_dataset_identity:
            raise ValueError("selection cohort identity must match run parent identity")
        if self.cohort.canonical_subject_ids != self.run_identity.canonical_subject_ids:
            raise ValueError("selection cohort subject IDs must match run identity")


def _selection_rank(seed: int, subject_id: str) -> bytes:
    payload = f"{seed}\0{subject_id}".encode("utf-8")
    return hashlib.sha256(payload).digest()


def select_population(
    session: DiseaseSelectionSession,
    request: DiseasePopulationRequest,
) -> DiseaseSelection:
    """Select a reproducible age-matched baseline population without replacement.

    Eligible subjects come from the active VascuQuest age quantity. SHA-256 is
    used only to rank eligible subject IDs reproducibly; selected IDs are then
    restored to their canonical VascuQuest cohort order.
    """

    if not isinstance(request, DiseasePopulationRequest):
        raise TypeError("request must be a DiseasePopulationRequest")
    identity = session.identity
    if not isinstance(identity, DatasetIdentity):
        raise TypeError("session.identity must be a DatasetIdentity")

    eligible = session.select(where={"age": request.age_group})
    if not isinstance(eligible, Cohort):
        raise TypeError("session.select must return a Cohort")
    if eligible.dataset_identity != identity:
        raise SelectionError("eligible cohort dataset identity does not match the session")

    eligible_ids = eligible.canonical_subject_ids
    if request.patients > len(eligible_ids):
        raise SelectionError(
            f"requested {request.patients} patients at age {request.age_group}, "
            f"but only {len(eligible_ids)} eligible PWDB subjects are available"
        )

    ranked = sorted(
        eligible_ids,
        key=lambda subject_id: (_selection_rank(request.seed, subject_id), subject_id),
    )
    chosen = frozenset(ranked[: request.patients])
    selected_ids = tuple(subject_id for subject_id in eligible_ids if subject_id in chosen)

    cohort = Cohort(
        dataset_identity=identity,
        canonical_subject_ids=selected_ids,
        ordering_rule=eligible.ordering_rule,
        selection_specification=eligible.selection_specification
        + (
            f"disease_patients={request.patients}",
            f"disease_seed={request.seed}",
        ),
        inclusion_filters=eligible.inclusion_filters,
        exclusion_filters=eligible.exclusion_filters,
        plausibility_filter=eligible.plausibility_filter,
        creation_provenance_ref=eligible.creation_provenance_ref,
    )
    run_identity = DiseaseRunIdentity(
        parent_dataset_identity=identity,
        canonical_subject_ids=selected_ids,
        request=request,
    )
    return DiseaseSelection(cohort=cohort, run_identity=run_identity)


__all__ = ["DiseaseSelection", "DiseaseSelectionSession", "select_population"]
