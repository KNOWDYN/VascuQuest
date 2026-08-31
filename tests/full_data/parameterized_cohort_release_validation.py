"""Real-PWDB qualification for the Parameterized Virtual Disease Cohort Engine.

This harness intentionally validates the merged public cohort surface against the
canonical PWDB source rather than test doubles. It does not establish clinical
validation of the disease models. It establishes that cohort planning is
reproducible and source-faithful, that subject-specific disease assignments are
admissible under the deployed Virtual Disease physics, that the existing full
116-segment solver completes for representative heterogeneous cohorts, and that
persistent bundles/resume/integrity behave as specified.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

import numpy as np

import vascuquest as vq
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.schema import load_manifest


REQUIRED_ARTIFACTS = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
)
EXPECTED_SOURCE_AGES = (25, 35, 45, 55, 65, 75)
QUALIFICATION_AGE_RANGE = (45, 75)
EXECUTION_PATIENTS = 3
SEED = 17031

CASES = (
    {
        "condition": "carotid_stenosis",
        "severity_min": 0.30,
        "severity_max": 0.80,
        "fixed_parameters": {
            "side": "left",
            "artery": "common_carotid",
            "lesion_length_m": 0.020,
            "lesion_center_fraction": 0.50,
        },
    },
    {
        "condition": "iliac_stenosis",
        "severity_min": 0.25,
        "severity_max": 0.70,
        "fixed_parameters": {
            "side": "right",
            "artery": "common_iliac",
            "lesion_length_m": 0.030,
            "lesion_center_fraction": 0.50,
        },
    },
    {
        "condition": "fusiform_abdominal_aortic_aneurysm",
        "severity_min": 0.025,
        "severity_max": 0.040,
        "fixed_parameters": {
            "aneurysm_length_m": 0.100,
            "aneurysm_center_fraction": 0.50,
        },
    },
    {
        "condition": "large_artery_stiffening",
        "severity_min": 10.0,
        "severity_max": 15.0,
        "fixed_parameters": {},
    },
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def acquire_sources() -> tuple[dict[str, Path], list[dict[str, object]]]:
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry)
    manifest = load_manifest()
    acquired: dict[str, Path] = {}
    records: list[dict[str, object]] = []

    for artifact_id in REQUIRED_ARTIFACTS:
        started = time.monotonic()
        path = acquirer.acquire(artifact_id, offline=False)
        artifact = manifest.artifact(artifact_id)
        inspection = verify_artifact(path, artifact)
        require(inspection.state.value == "verified", f"{artifact_id} is not verified")
        require(
            inspection.observed_checksum == artifact.checksum_value,
            f"{artifact_id} checksum mismatch",
        )
        acquired[artifact_id] = path
        records.append(
            {
                "artifact_id": artifact_id,
                "filename": artifact.filename,
                "size_bytes": inspection.size_bytes,
                "checksum_algorithm": artifact.checksum_algorithm,
                "expected_checksum": artifact.checksum_value,
                "observed_checksum": inspection.observed_checksum,
                "acquire_and_verify_seconds": round(time.monotonic() - started, 6),
            }
        )
    return acquired, records


def scalar_value(result: object) -> float:
    values = np.asarray(getattr(result, "values"), dtype=float)
    require(values.size == 1, "expected one scalar value")
    return float(values.reshape(-1)[0])


def validate_plan_case(session: object, case: dict[str, object], case_seed: int):
    kwargs = {
        "patients": EXECUTION_PATIENTS,
        "age_min": QUALIFICATION_AGE_RANGE[0],
        "age_max": QUALIFICATION_AGE_RANGE[1],
        "condition": case["condition"],
        "severity_min": case["severity_min"],
        "severity_max": case["severity_max"],
        "fixed_parameters": case["fixed_parameters"],
        "seed": case_seed,
        "offline": True,
    }
    started = time.monotonic()
    first = vq.disease.create_parameterized_cohort_plan(**kwargs)
    second = vq.disease.create_parameterized_cohort_plan(**kwargs)
    elapsed = time.monotonic() - started

    require(first.run_id == second.run_id, "identical plan request changed run_id")
    require(first.to_dict() == second.to_dict(), "identical plan request changed content")
    require(
        first.supported_ages == (45, 55, 65, 75),
        f"unexpected source-supported age filter: {first.supported_ages}",
    )
    require(len(first.assignments) == EXECUTION_PATIENTS, "planned patient count mismatch")
    require(
        len(first.canonical_subject_ids) == len(set(first.canonical_subject_ids)),
        "planner produced duplicate canonical subject IDs",
    )

    severity_values: list[float] = []
    assignment_rows: list[dict[str, object]] = []
    for assignment in first.assignments:
        source_age = scalar_value(
            session.get("age", subjects=assignment.canonical_subject_id)
        )
        require(
            source_age == float(assignment.age_years),
            f"subject {assignment.canonical_subject_id} source age changed in plan",
        )
        require(
            assignment.age_years in first.supported_ages,
            "assignment age is not source-supported",
        )
        require(
            float(case["severity_min"]) <= assignment.severity_value <= float(case["severity_max"]),
            "assignment severity is outside request bounds",
        )
        require(
            assignment.severity_parameter
            == vq.disease.severity_parameter(str(case["condition"])),
            "assignment severity parameter does not match disease preset",
        )
        params = assignment.specification.parameter_mapping()
        require(
            np.isclose(
                float(params[assignment.severity_parameter]),
                assignment.severity_value,
                rtol=0.0,
                atol=1e-15,
            ),
            "assignment specification does not preserve its exact severity",
        )
        severity_values.append(assignment.severity_value)
        assignment_rows.append(
            {
                "canonical_subject_id": assignment.canonical_subject_id,
                "source_age_years": assignment.age_years,
                "severity_parameter": assignment.severity_parameter,
                "severity_value": assignment.severity_value,
                "parameters": dict(assignment.specification.parameters),
            }
        )

    require(
        max(severity_values) > min(severity_values),
        "parameterized plan did not create heterogeneous severity values",
    )

    return first, {
        "condition": case["condition"],
        "run_id": first.run_id,
        "supported_ages": list(first.supported_ages),
        "canonical_subject_ids": list(first.canonical_subject_ids),
        "assignments": assignment_rows,
        "rejections": [item.to_dict() for item in first.rejections],
        "planner_seconds_for_two_identical_plans": round(elapsed, 6),
        "determinism": "PASS",
        "source_age_identity": "PASS",
        "subject_specific_admissibility": "PASS_BY_DEPLOYED_TRANSFORM",
    }


def validate_full_network_subject(subject_root: Path, subject_id: str) -> dict[str, object]:
    subject_manifest = json_read(subject_root / "subject_manifest.json")
    require(
        subject_manifest["canonical_subject_id"] == subject_id,
        "subject manifest changed canonical subject ID",
    )
    diagnostics = json_read(subject_root / "diagnostics.json")
    require(bool(diagnostics.get("converged")), f"subject {subject_id} did not converge")

    network_index = json_read(subject_root / "full_network_index.json")
    segment_ids = tuple(str(item) for item in network_index["segment_ids"])
    require(network_index["segment_count"] == 116, "full-network index is not 116 segments")
    require(len(segment_ids) == 116, "full-network segment list is not 116 entries")
    require(len(set(segment_ids)) == 116, "full-network segment IDs are not unique")

    result_files = tuple((subject_root / "results").glob("*.json"))
    require(len(result_files) == 58, f"subject {subject_id} does not contain 58 materialised results")

    with np.load(subject_root / "full_network.npz", allow_pickle=False) as payload:
        time_s = np.asarray(payload["time_s"], dtype=float)
        require(time_s.ndim == 1 and time_s.size >= 2, "invalid final-cycle time coordinate")
        require(np.all(np.isfinite(time_s)), "non-finite final-cycle time coordinate")
        require(np.all(np.diff(time_s) > 0), "final-cycle time coordinate is not strictly increasing")

        min_area = float("inf")
        maximum_abs_velocity = 0.0
        for segment_id in segment_ids:
            prefix = f"segment_{segment_id}"
            x = np.asarray(payload[f"{prefix}__x_m"], dtype=float)
            area = np.asarray(payload[f"{prefix}__area_m2"], dtype=float)
            flow = np.asarray(payload[f"{prefix}__flow_m3_per_s"], dtype=float)
            pressure = np.asarray(payload[f"{prefix}__pressure_pa"], dtype=float)
            require(x.ndim == 1 and x.size >= 1, f"segment {segment_id} has invalid x grid")
            require(np.all(np.isfinite(x)), f"segment {segment_id} has non-finite x")
            require(
                area.shape == flow.shape == pressure.shape == (time_s.size, x.size),
                f"segment {segment_id} history shape mismatch",
            )
            require(np.all(np.isfinite(area)), f"segment {segment_id} has non-finite area")
            require(np.all(np.isfinite(flow)), f"segment {segment_id} has non-finite flow")
            require(np.all(np.isfinite(pressure)), f"segment {segment_id} has non-finite pressure")
            require(np.all(area > 0), f"segment {segment_id} has non-positive area")
            velocity = flow / area
            require(np.all(np.isfinite(velocity)), f"segment {segment_id} produced non-finite U=Q/A")
            min_area = min(min_area, float(np.min(area)))
            maximum_abs_velocity = max(maximum_abs_velocity, float(np.max(np.abs(velocity))))

    return {
        "canonical_subject_id": subject_id,
        "source_age_years": subject_manifest["source_age_years"],
        "severity_parameter": subject_manifest["severity_parameter"],
        "severity_value": subject_manifest["severity_value"],
        "subject_disease_run_id": subject_manifest["subject_disease_run_id"],
        "solver_diagnostics": diagnostics,
        "materialised_results": len(result_files),
        "full_network_segments": len(segment_ids),
        "minimum_area_m2": min_area,
        "maximum_absolute_mean_velocity_m_per_s": maximum_abs_velocity,
    }


def validate_execution_case(
    plan: object,
    case: dict[str, object],
    workspace: Path,
) -> dict[str, object]:
    condition = str(case["condition"])
    bundle = workspace / condition
    started = time.monotonic()
    generated = vq.disease.generate_parameterized_cohort(
        plan,
        destination=bundle,
        offline=True,
        resume=False,
    )
    generation_seconds = time.monotonic() - started
    require(generated == bundle, "generator returned an unexpected bundle path")

    verification = vq.disease.verify_parameterized_cohort_bundle(bundle)
    require(verification["valid"] is True, "bundle verification did not return valid=True")
    require(verification["status"] == "COMPLETE", "generated bundle is not COMPLETE")
    require(
        verification["subjects_verified"] == EXECUTION_PATIENTS,
        "bundle verification subject count mismatch",
    )
    require(
        tuple(verification["canonical_subject_ids"]) == plan.canonical_subject_ids,
        "bundle verification changed canonical subject ordering",
    )
    require(
        verification["full_network_segment_count_per_completed_subject"] == 116,
        "bundle verification does not report 116 segments",
    )
    require(verification["evidence"] == "MODELLED", "cohort evidence boundary changed")
    require(verification["clinical_validation"] is False, "clinical validation was incorrectly asserted")

    manifest = vq.disease.inspect_parameterized_cohort_bundle(bundle)
    require(manifest["cohort_run_id"] == plan.run_id, "bundle run identity differs from plan")
    require(manifest["status"] == "COMPLETE", "bundle manifest is not COMPLETE")
    require(
        tuple(manifest["canonical_subject_ids"]) == plan.canonical_subject_ids,
        "bundle manifest changed original subject IDs",
    )
    require(
        manifest["population_interpretation"] == "designed_counterfactual_not_epidemiological",
        "population interpretation boundary changed",
    )

    subject_summaries = []
    checkpoint_hashes_before: dict[str, dict[str, str]] = {}
    for assignment in plan.assignments:
        subject_id = assignment.canonical_subject_id
        subject_root = bundle / "subjects" / subject_id
        subject_summaries.append(validate_full_network_subject(subject_root, subject_id))
        checkpoint_hashes_before[subject_id] = {
            "subject_manifest": sha256(subject_root / "subject_manifest.json"),
            "full_network": sha256(subject_root / "full_network.npz"),
        }

    resume_started = time.monotonic()
    resumed = vq.disease.generate_parameterized_cohort(
        plan,
        destination=bundle,
        offline=True,
        resume=True,
    )
    resume_seconds = time.monotonic() - resume_started
    require(resumed == bundle, "resume returned an unexpected bundle path")

    for assignment in plan.assignments:
        subject_id = assignment.canonical_subject_id
        subject_root = bundle / "subjects" / subject_id
        require(
            sha256(subject_root / "subject_manifest.json")
            == checkpoint_hashes_before[subject_id]["subject_manifest"],
            f"resume rewrote completed subject manifest {subject_id}",
        )
        require(
            sha256(subject_root / "full_network.npz")
            == checkpoint_hashes_before[subject_id]["full_network"],
            f"resume recomputed or rewrote completed full-network solution {subject_id}",
        )

    verification_after_resume = vq.disease.verify_parameterized_cohort_bundle(bundle)
    require(verification_after_resume["valid"] is True, "resumed bundle failed verification")
    require(verification_after_resume["status"] == "COMPLETE", "resumed bundle lost COMPLETE state")

    return {
        "condition": condition,
        "run_id": plan.run_id,
        "generation_seconds": round(generation_seconds, 6),
        "resume_seconds": round(resume_seconds, 6),
        "bundle_verification": verification_after_resume,
        "subjects": subject_summaries,
        "resume_checkpoint_immutability": "PASS",
        "full_network_persistence": "PASS",
    }


def run_validation(report_path: Path, code_revision: str, workspace: Path) -> dict[str, object]:
    started = time.monotonic()
    acquired, source_records = acquire_sources()
    session = vq.open_dataset(offline=True)

    all_source_ages = tuple(
        sorted(
            {
                int(round(float(value)))
                for value in np.asarray(session.get("age").values, dtype=float)
            }
        )
    )
    require(all_source_ages == EXPECTED_SOURCE_AGES, f"unexpected PWDB age states: {all_source_ages}")

    plans: dict[str, object] = {}
    planner_reports: list[dict[str, object]] = []
    for index, case in enumerate(CASES):
        plan, summary = validate_plan_case(session, case, SEED + index)
        plans[str(case["condition"])] = plan
        planner_reports.append(summary)

    execution_root = workspace / "cohorts"
    execution_root.mkdir(parents=True, exist_ok=True)
    execution_reports = []
    for case in CASES:
        plan = plans[str(case["condition"])]
        execution_reports.append(validate_execution_case(plan, case, execution_root))

    report = {
        "format": "vascuquest-parameterized-cohort-real-source-qualification",
        "format_version": 1,
        "status": "PASSED",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": code_revision,
        "vascuquest_version": vq.__version__,
        "python": sys.version,
        "platform": platform.platform(),
        "source_dataset": {
            "dataset_family": session.identity.dataset_family,
            "record_id": session.identity.record_id,
            "persistent_identifier": session.identity.persistent_identifier,
            "schema_version": session.identity.schema_version,
            "age_states": list(all_source_ages),
            "artifacts": source_records,
            "managed_paths": {key: str(value) for key, value in acquired.items()},
        },
        "qualification_scope": {
            "patients_per_condition": EXECUTION_PATIENTS,
            "conditions": [str(case["condition"]) for case in CASES],
            "requested_age_range_years": list(QUALIFICATION_AGE_RANGE),
            "planner_determinism": True,
            "source_subject_identity": True,
            "subject_specific_admissibility": True,
            "full_116_segment_execution": True,
            "portable_bundle_integrity": True,
            "completed_checkpoint_resume": True,
            "clinical_validation": False,
            "population_epidemiological_representativeness": False,
        },
        "planner": planner_reports,
        "execution": execution_reports,
        "elapsed_seconds": round(time.monotonic() - started, 6),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def write_failure(report_path: Path, code_revision: str, exc: BaseException) -> None:
    payload = {
        "format": "vascuquest-parameterized-cohort-real-source-qualification",
        "format_version": 1,
        "status": "FAILED",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": code_revision,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "clinical_validation": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    args.workspace.mkdir(parents=True, exist_ok=True)
    try:
        report = run_validation(args.report, args.code_revision, args.workspace)
    except Exception as exc:
        write_failure(args.report, args.code_revision, exc)
        traceback.print_exc()
        return 1

    print(json.dumps({
        "status": report["status"],
        "report": str(args.report),
        "conditions": report["qualification_scope"]["conditions"],
        "patients_per_condition": report["qualification_scope"]["patients_per_condition"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
