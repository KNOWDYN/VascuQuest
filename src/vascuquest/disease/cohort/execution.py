"""Numerical execution identity for parameterized Virtual Disease cohorts.

A cohort plan identifies the scientific counterfactual design. Solver backend
and time-integration scheme are execution facts and must not change that plan
identity, but they must participate in bundle resume and verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Mapping

from vascuquest.disease.solver.execution import (
    JAX_SPLIT_SCHEME_ID,
    NUMPY_REFERENCE_SCHEME_ID,
    SOLVER_EXECUTION_CONTRACT_VERSION,
    solver_execution_descriptor,
)
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.errors import IntegrityError

from .bundle import (
    ParameterizedDiseaseCohortBundleWriter,
    _sha256,
    _write_json,
    inspect_parameterized_cohort_bundle,
    verify_parameterized_cohort_bundle as _verify_base_bundle,
)


def _validated_execution(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise IntegrityError("cohort bundle lacks a valid solver_execution descriptor")
    item = dict(payload)
    if item.get("contract_version") != SOLVER_EXECUTION_CONTRACT_VERSION:
        raise IntegrityError("unsupported cohort solver execution contract")
    try:
        backend = str(item["solver_backend"])
        options_raw = item["solver_options"]
        if not isinstance(options_raw, Mapping):
            raise TypeError("solver_options is not an object")
        options = SolverOptions(**dict(options_raw))
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrityError("invalid cohort solver execution descriptor") from exc
    expected = solver_execution_descriptor(backend, options)
    if item != expected:
        raise IntegrityError("cohort solver execution descriptor/hash is inconsistent")
    return expected


class ExecutionAwareCohortBundleWriter(ParameterizedDiseaseCohortBundleWriter):
    """Persist and enforce a numerical execution fingerprint during resume."""

    def __init__(
        self,
        destination,
        plan,
        runtime_identity,
        *,
        execution: Mapping[str, object],
        resume: bool = False,
    ) -> None:
        self.execution = _validated_execution(execution)
        self._pending_execution_subject_id: str | None = None
        super().__init__(
            destination,
            plan,
            runtime_identity,
            resume=resume,
        )

    def _base_manifest(self, static_hashes):
        payload = super()._base_manifest(static_hashes)
        payload["solver_execution"] = dict(self.execution)
        return payload

    def _load_and_validate_existing(self) -> None:
        """Reject execution mismatches before base resume performs any mutation."""

        if not self.manifest_path.exists():
            raise IntegrityError("resume destination lacks manifest.json")
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityError("invalid cohort bundle manifest during resume") from exc
        existing = _validated_execution(payload.get("solver_execution"))
        if existing != self.execution:
            raise IntegrityError(
                "resume bundle solver execution does not match the requested backend/scheme/options"
            )
        super()._load_and_validate_existing()

    def _write_manifest(self) -> None:
        """Attach execution identity before a completed subject is checkpointed.

        The base writer first atomically installs the subject directory and only
        then commits its hash to the top-level manifest.  While a subject write
        is pending, add the execution descriptor and refresh that hash before
        the top-level checkpoint is written.  A crash before this method
        completes therefore leaves an unacknowledged subject that resume will
        recompute rather than a falsely completed execution-aware checkpoint.
        """

        subject_id = self._pending_execution_subject_id
        if subject_id is not None:
            subject_manifests = dict(self._manifest.get("subject_manifests", {}))
            if subject_id in subject_manifests:
                subject_manifest_path = self.subjects_root / subject_id / "subject_manifest.json"
                try:
                    payload = json.loads(subject_manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise IntegrityError(
                        f"invalid subject manifest while checkpointing solver execution: {subject_id}"
                    ) from exc
                payload["solver_execution"] = dict(self.execution)
                _write_json(subject_manifest_path, payload)
                subject_manifests[subject_id] = _sha256(subject_manifest_path)
                self._manifest["subject_manifests"] = subject_manifests
        super()._write_manifest()

    def subject_complete(self, subject_id: str) -> bool:
        """Require both base integrity and the exact execution fingerprint."""

        if not super().subject_complete(subject_id):
            return False
        path = self.subjects_root / subject_id / "subject_manifest.json"
        try:
            subject_manifest = json.loads(path.read_text(encoding="utf-8"))
            execution = _validated_execution(subject_manifest.get("solver_execution"))
        except (OSError, json.JSONDecodeError, IntegrityError):
            return False
        return execution == self.execution

    def write_subject(self, assignment, state, *, subject_disease_run_id: str) -> None:
        self._pending_execution_subject_id = assignment.canonical_subject_id
        try:
            super().write_subject(
                assignment,
                state,
                subject_disease_run_id=subject_disease_run_id,
            )
        finally:
            self._pending_execution_subject_id = None


def verify_execution_aware_cohort_bundle(source) -> dict[str, object]:
    """Verify normal bundle integrity plus numerical execution consistency.

    Newly generated PR-20 bundles require a solver-execution descriptor. Legacy
    bundles created before this execution contract remain verifiable through the
    base verifier and are reported with ``solver_execution = None``.
    """

    result = _verify_base_bundle(source)
    manifest = inspect_parameterized_cohort_bundle(source)
    raw_execution = manifest.get("solver_execution")
    if raw_execution is None:
        result["solver_execution"] = None
        return result
    execution = _validated_execution(raw_execution)

    root = Path(source).expanduser()
    for subject_id in result.get("canonical_subject_ids", []):
        path = root / "subjects" / str(subject_id) / "subject_manifest.json"
        try:
            subject_manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityError(
                f"invalid subject manifest while verifying solver execution: {subject_id}"
            ) from exc
        subject_execution = _validated_execution(subject_manifest.get("solver_execution"))
        if subject_execution != execution:
            raise IntegrityError(
                f"subject solver execution does not match cohort manifest: {subject_id}"
            )

    result["solver_execution"] = execution
    return result


__all__ = [
    "ExecutionAwareCohortBundleWriter",
    "JAX_SPLIT_SCHEME_ID",
    "NUMPY_REFERENCE_SCHEME_ID",
    "SOLVER_EXECUTION_CONTRACT_VERSION",
    "solver_execution_descriptor",
    "verify_execution_aware_cohort_bundle",
]
