from __future__ import annotations

import hashlib
import json

import pytest

from vascuquest.domain.identity import DatasetIdentity
from vascuquest.disease.cohort import (
    DiseaseCohortAssignment,
    ParameterizedDiseaseCohortPlan,
    ParameterizedDiseaseCohortRequest,
    cohort_runtime_dataset_identity,
)
from vascuquest.disease.cohort.execution import (
    ExecutionAwareCohortBundleWriter,
    JAX_SPLIT_SCHEME_ID,
    NUMPY_REFERENCE_SCHEME_ID,
    solver_execution_descriptor,
)
from vascuquest.disease.model import DiseaseCondition
from vascuquest.disease.runtime.provenance import _solver_execution
from vascuquest.disease.solver.model import SolverDiagnostics, SolverOptions
from vascuquest.errors import IntegrityError


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)


def _make_plan() -> ParameterizedDiseaseCohortPlan:
    request = ParameterizedDiseaseCohortRequest.from_mapping(
        patients=1,
        age_min=45,
        age_max=65,
        condition=DiseaseCondition.CAROTID_STENOSIS,
        severity_min=0.40,
        severity_max=0.70,
        fixed_parameters={
            "side": "left",
            "artery": "common_carotid",
            "lesion_length_m": 0.02,
        },
        seed=9,
    )
    severity = 0.55
    assignment = DiseaseCohortAssignment(
        canonical_subject_id="431",
        age_years=55,
        severity_parameter=request.severity_parameter,
        severity_value=severity,
        specification=request.specification_for(severity),
    )
    return ParameterizedDiseaseCohortPlan(
        parent_dataset_identity=IDENTITY,
        request=request,
        supported_ages=(45, 55, 65),
        assignments=(assignment,),
    )


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _diagnostics(mode: str) -> SolverDiagnostics:
    return SolverDiagnostics(
        cycles_completed=3,
        periodicity_error=1e-5,
        converged=True,
        minimum_area_ratio=0.9,
        maximum_cfl=0.45,
        maximum_diffusion_number=1.0,
        terminal_mass_balance_relative_error=1e-4,
        wall_viscoelasticity_mode=mode,
    )


def test_solver_execution_identity_separates_backend_from_scientific_plan() -> None:
    options = SolverOptions()
    numpy_execution = solver_execution_descriptor("numpy", options)
    jax_execution = solver_execution_descriptor("jax", options)
    assert numpy_execution["numerical_scheme_id"] == NUMPY_REFERENCE_SCHEME_ID
    assert jax_execution["numerical_scheme_id"] == JAX_SPLIT_SCHEME_ID
    assert numpy_execution["solver_execution_id"] != jax_execution["solver_execution_id"]
    assert numpy_execution["solver_options"] == jax_execution["solver_options"]


def test_solver_execution_identity_is_deterministic_and_option_sensitive() -> None:
    first = solver_execution_descriptor("jax", SolverOptions())
    second = solver_execution_descriptor(" JAX ", SolverOptions())
    changed = solver_execution_descriptor("jax", SolverOptions(cfl=0.40))
    assert first == second
    assert first["solver_execution_id"] != changed["solver_execution_id"]


def test_runtime_provenance_uses_the_canonical_execution_descriptor() -> None:
    options = SolverOptions()
    assert _solver_execution(
        _diagnostics("pwdb_voigt_gamma_rkc2_global_split"), options
    ) == solver_execution_descriptor("jax", options)
    assert _solver_execution(
        _diagnostics("pwdb_voigt_gamma_explicit"), options
    ) == solver_execution_descriptor("numpy", options)


def test_subject_checkpoint_is_not_complete_without_execution_descriptor(tmp_path) -> None:
    plan = _make_plan()
    runtime = cohort_runtime_dataset_identity(plan)
    execution = solver_execution_descriptor("jax", SolverOptions())
    writer = ExecutionAwareCohortBundleWriter(
        tmp_path / "bundle",
        plan,
        runtime,
        execution=execution,
    )

    subject_id = "431"
    subject_root = writer.subjects_root / subject_id
    subject_root.mkdir()
    subject_manifest_path = subject_root / "subject_manifest.json"
    subject_manifest_path.write_text(
        json.dumps(
            {
                "canonical_subject_id": subject_id,
                "full_network_segment_count": 116,
                "files": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (subject_root / "COMPLETE").write_text("complete\n", encoding="utf-8")

    writer._manifest["subject_manifests"] = {
        subject_id: _sha256(subject_manifest_path)
    }
    assert writer.subject_complete(subject_id) is False

    writer._pending_execution_subject_id = subject_id
    writer._write_manifest()
    writer._pending_execution_subject_id = None

    subject_manifest = json.loads(subject_manifest_path.read_text(encoding="utf-8"))
    persisted_manifest = json.loads(writer.manifest_path.read_text(encoding="utf-8"))
    assert subject_manifest["solver_execution"] == execution
    assert persisted_manifest["subject_manifests"][subject_id] == _sha256(
        subject_manifest_path
    )
    assert writer.subject_complete(subject_id) is True


def test_execution_mismatch_resume_is_read_only(tmp_path) -> None:
    plan = _make_plan()
    runtime = cohort_runtime_dataset_identity(plan)
    bundle = tmp_path / "bundle"
    ExecutionAwareCohortBundleWriter(
        bundle,
        plan,
        runtime,
        execution=solver_execution_descriptor("jax", SolverOptions()),
    )
    before = _snapshot(bundle)

    with pytest.raises(IntegrityError, match="solver execution does not match"):
        ExecutionAwareCohortBundleWriter(
            bundle,
            plan,
            runtime,
            execution=solver_execution_descriptor("numpy", SolverOptions()),
            resume=True,
        )

    assert _snapshot(bundle) == before
