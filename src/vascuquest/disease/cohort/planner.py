"""Deterministic planning for parameterized Virtual Disease cohorts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Protocol

import numpy as np

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.baseline.model import BaselineCardiovascularState
from vascuquest.disease.physics import transform_disease
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.errors import AdmissibilityError, SelectionError

from .model import (
    DiseaseCohortAssignment,
    DiseaseCohortRejection,
    ParameterizedDiseaseCohortPlan,
    ParameterizedDiseaseCohortRequest,
)


class ParameterizedCohortSession(Protocol):
    @property
    def identity(self) -> DatasetIdentity:
        ...

    def subjects(self, *, where: object | None = None) -> tuple[object, ...]:
        ...

    def get(self, quantity: str, *, subjects: object | None = None, location: object | None = None) -> object:
        ...


class BaselineAssembler(Protocol):
    def assemble(self, session: object, subject_id: str) -> BaselineCardiovascularState:
        ...


@dataclass(frozen=True, slots=True)
class _Candidate:
    subject_id: str
    age_years: int
    canonical_index: int
    rank: bytes


def _rank(seed: int, namespace: str, token: str) -> bytes:
    return hashlib.sha256(f"{seed}\0{namespace}\0{token}".encode("utf-8")).digest()


def _unit_interval(seed: int, index: int) -> float:
    digest = _rank(seed, "severity", str(index))
    integer = int.from_bytes(digest[:8], "big", signed=False)
    return (integer + 0.5) / float(1 << 64)


def stratified_severity_design(request: ParameterizedDiseaseCohortRequest) -> tuple[float, ...]:
    """Return deterministic, interval-covering severity values for the requested N."""
    if not isinstance(request, ParameterizedDiseaseCohortRequest):
        raise TypeError("request must be a ParameterizedDiseaseCohortRequest")
    if math.isclose(request.severity_min, request.severity_max, rel_tol=0.0, abs_tol=0.0):
        return tuple(float(request.severity_min) for _ in range(request.patients))
    span = request.severity_max - request.severity_min
    values = []
    for index in range(request.patients):
        fraction = (index + _unit_interval(request.seed, index)) / request.patients
        values.append(request.severity_min + fraction * span)
    return tuple(values)


def _source_age_map(session: ParameterizedCohortSession) -> tuple[tuple[str, ...], dict[str, int]]:
    subjects = tuple(session.subjects())
    ids = tuple(str(getattr(item, "canonical_subject_id")) for item in subjects)
    if not ids or len(ids) != len(set(ids)):
        raise SelectionError("source dataset must expose unique canonical subject IDs")
    result = session.get("age")
    values = np.asarray(getattr(result, "values"), dtype=float).reshape(-1)
    if values.size != len(ids):
        raise SelectionError("source age vector does not align with canonical subject order")
    ages: dict[str, int] = {}
    for subject_id, raw in zip(ids, values, strict=True):
        if not np.isfinite(raw) or not math.isclose(float(raw), round(float(raw)), abs_tol=1e-9):
            raise SelectionError("parameterized disease cohorts require integer source age states")
        ages[subject_id] = int(round(float(raw)))
    return ids, ages


def _is_admissible(
    baseline: BaselineCardiovascularState,
    request: ParameterizedDiseaseCohortRequest,
    severity: float,
    options: SolverOptions,
) -> tuple[bool, str | None]:
    try:
        transform_disease(
            baseline,
            request.specification_for(severity),
            options=options,
        )
    except AdmissibilityError as exc:
        return False, str(exc)
    return True, None


def _lowest_admissible_remaining(
    baseline: BaselineCardiovascularState,
    request: ParameterizedDiseaseCohortRequest,
    remaining: list[tuple[int, float]],
    options: SolverOptions,
) -> tuple[int | None, str | None]:
    """Find the lowest remaining admissible severity using vdc1 monotonicity.

    For the four frozen vd1 interventions, admissibility is monotone with this
    cohort severity direction: stenosis anatomy is severity-independent for
    0<=s<1; a larger AAA target diameter cannot invalidate a smaller admissible
    dilation; and a larger stiffening cfPWV target cannot become softening.
    """
    if not remaining:
        return None, None
    highest_ok, highest_reason = _is_admissible(
        baseline, request, remaining[-1][1], options
    )
    if not highest_ok:
        return None, highest_reason

    lowest_ok, _ = _is_admissible(baseline, request, remaining[0][1], options)
    if lowest_ok:
        return 0, None

    left = 1
    right = len(remaining) - 1
    while left < right:
        middle = (left + right) // 2
        ok, _ = _is_admissible(baseline, request, remaining[middle][1], options)
        if ok:
            right = middle
        else:
            left = middle + 1
    ok, reason = _is_admissible(baseline, request, remaining[left][1], options)
    if not ok:
        raise RuntimeError(
            "internal cohort admissibility search violated the frozen vdc1 monotonicity contract"
        )
    return left, reason


def plan_parameterized_cohort(
    session: ParameterizedCohortSession,
    request: ParameterizedDiseaseCohortRequest,
    *,
    assembler: BaselineAssembler,
    solver_options: SolverOptions | None = None,
) -> ParameterizedDiseaseCohortPlan:
    """Plan a heterogeneous cohort without executing haemodynamic time integration.

    Candidate subjects are deterministically ranked. Exact requested severity
    values are tested against each subject's actual PWDB baseline by calling the
    frozen ``transform_disease`` implementation. A subject is matched to the
    lowest still-unassigned severity that it can accept. Values are never
    silently clamped, and candidates that cannot accept any remaining severity
    are retained with their exact disease-physics rejection reason.
    """
    if not isinstance(request, ParameterizedDiseaseCohortRequest):
        raise TypeError("request must be a ParameterizedDiseaseCohortRequest")
    identity = session.identity
    if not isinstance(identity, DatasetIdentity):
        raise TypeError("session.identity must be a DatasetIdentity")
    if not hasattr(assembler, "assemble"):
        raise TypeError("assembler must expose assemble(session, subject_id)")
    options = SolverOptions() if solver_options is None else solver_options
    if not isinstance(options, SolverOptions):
        raise TypeError("solver_options must be a SolverOptions or None")

    canonical_ids, age_by_id = _source_age_map(session)
    canonical_index = {subject_id: index for index, subject_id in enumerate(canonical_ids)}
    eligible = tuple(
        subject_id
        for subject_id in canonical_ids
        if request.age_min <= age_by_id[subject_id] <= request.age_max
    )
    if not eligible:
        raise SelectionError(
            f"no source PWDB subjects exist in requested age interval "
            f"[{request.age_min}, {request.age_max}]"
        )
    supported_ages = tuple(sorted({age_by_id[item] for item in eligible}))
    if request.patients > len(eligible):
        raise SelectionError(
            f"requested {request.patients} subjects but only {len(eligible)} source subjects "
            f"exist at supported ages {list(supported_ages)} inside the requested interval"
        )

    candidates = sorted(
        (
            _Candidate(
                subject_id=subject_id,
                age_years=age_by_id[subject_id],
                canonical_index=canonical_index[subject_id],
                rank=_rank(request.seed, "subject", subject_id),
            )
            for subject_id in eligible
        ),
        key=lambda item: (item.rank, item.subject_id),
    )
    remaining = list(enumerate(stratified_severity_design(request)))
    matched: dict[int, DiseaseCohortAssignment] = {}
    rejections: list[DiseaseCohortRejection] = []

    for candidate in candidates:
        if not remaining:
            break
        baseline = assembler.assemble(session, candidate.subject_id)
        if baseline.canonical_subject_id != candidate.subject_id:
            raise SelectionError("baseline assembler changed the canonical subject identity")
        if baseline.age_years != candidate.age_years:
            raise SelectionError("baseline age disagrees with source age selection")

        position, reason = _lowest_admissible_remaining(
            baseline,
            request,
            remaining,
            options,
        )
        if position is None:
            rejections.append(
                DiseaseCohortRejection(
                    canonical_subject_id=candidate.subject_id,
                    age_years=candidate.age_years,
                    reason=reason or "not admissible for any remaining designed severity",
                )
            )
            continue
        severity_index, severity = remaining.pop(position)
        matched[severity_index] = DiseaseCohortAssignment(
            canonical_subject_id=candidate.subject_id,
            age_years=candidate.age_years,
            severity_parameter=request.severity_parameter,
            severity_value=float(severity),
            specification=request.specification_for(severity),
        )

    if remaining:
        raise SelectionError(
            f"could not construct {request.patients} admissible subjects for "
            f"{request.condition.value} across requested severity range; "
            f"{len(remaining)} designed severity assignments remain unmatched after "
            f"exhausting {len(eligible)} eligible source subjects"
        )

    assignments = list(matched.values())
    assignments.sort(key=lambda item: canonical_index[item.canonical_subject_id])
    return ParameterizedDiseaseCohortPlan(
        parent_dataset_identity=identity,
        request=request,
        supported_ages=supported_ages,
        assignments=tuple(assignments),
        rejections=tuple(rejections),
    )


__all__ = [
    "BaselineAssembler",
    "ParameterizedCohortSession",
    "plan_parameterized_cohort",
    "stratified_severity_design",
]
