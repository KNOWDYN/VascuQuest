"""Checkpointed Colab/manual qualification for parameterized Virtual Disease cohorts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

import vascuquest as vq
from vascuquest.schema import load_manifest


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

REQUIRED_ARTIFACT_IDS = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
)
SUPPORTED_AGES = (45, 55, 65, 75)
AGE_MIN = 45
AGE_MAX = 75
BASE_SEED = 17031
SUBJECT_LINE = re.compile(
    r"\[\d+/\d+\]\s+subject\s+([^:]+):\s+"
    r"(complete|verified checkpoint, skipped)"
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return _digest(path, "sha256")


def _find_unique(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected exactly one {filename!r} below {root}; found {len(matches)}"
        )
    return matches[0]


def _copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(destination.name + ".partial")
    temporary.unlink(missing_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, temporary.open("wb") as dst:
        while True:
            block = src.read(8 * 1024 * 1024)
            if not block:
                break
            dst.write(block)
    temporary.replace(destination)


def stage_sources(drive_root: Path, local_source: Path, output_root: Path):
    manifest = load_manifest()
    local_source.mkdir(parents=True, exist_ok=True)
    records = []
    for artifact_id in REQUIRED_ARTIFACT_IDS:
        artifact = manifest.artifact(artifact_id)
        drive_file = _find_unique(drive_root, artifact.filename)
        expected = artifact.checksum_value
        algorithm = artifact.checksum_algorithm
        drive_hash = _digest(drive_file, algorithm)
        if drive_hash != expected:
            raise RuntimeError(f"Drive checksum mismatch for {artifact.filename}")
        local_file = local_source / artifact.filename
        if not local_file.exists() or _digest(local_file, algorithm) != expected:
            _copy(drive_file, local_file)
        local_hash = _digest(local_file, algorithm)
        if local_hash != expected:
            raise RuntimeError(f"local checksum mismatch for {artifact.filename}")
        records.append(
            {
                "artifact_id": artifact_id,
                "filename": artifact.filename,
                "bytes": local_file.stat().st_size,
                "checksum_algorithm": algorithm,
                "checksum": local_hash,
            }
        )
    _write_json(output_root / "source_artifacts.json", records)
    return records


def _scalar(result: object) -> float:
    values = np.asarray(getattr(result, "values"), dtype=float).reshape(-1)
    if values.size != 1:
        raise AssertionError("expected exactly one scalar source value")
    return float(values[0])


def create_plan(
    *,
    session: object,
    case: dict[str, object],
    patients: int,
    seed: int,
    source: Path,
    root: Path,
):
    kwargs = {
        "patients": patients,
        "age_min": AGE_MIN,
        "age_max": AGE_MAX,
        "condition": case["condition"],
        "severity_min": case["severity_min"],
        "severity_max": case["severity_max"],
        "fixed_parameters": case["fixed_parameters"],
        "seed": seed,
        "source": source,
        "offline": True,
    }
    first = vq.disease.create_parameterized_cohort_plan(**kwargs)
    second = vq.disease.create_parameterized_cohort_plan(**kwargs)
    if first.run_id != second.run_id or first.to_dict() != second.to_dict():
        raise AssertionError("identical plan request is not deterministic")
    if first.supported_ages != SUPPORTED_AGES:
        raise AssertionError(f"unexpected source-supported ages: {first.supported_ages}")
    if len(first.assignments) != patients:
        raise AssertionError("planned patient count mismatch")
    if len(set(first.canonical_subject_ids)) != patients:
        raise AssertionError("planned canonical subject IDs are not unique")

    severities = []
    for assignment in first.assignments:
        source_age = _scalar(
            session.get("age", subjects=assignment.canonical_subject_id)
        )
        if source_age != float(assignment.age_years):
            raise AssertionError("planned age differs from canonical PWDB source age")
        if assignment.age_years not in SUPPORTED_AGES:
            raise AssertionError("planner introduced a non-source-supported age")
        if not (
            float(case["severity_min"])
            <= assignment.severity_value
            <= float(case["severity_max"])
        ):
            raise AssertionError("assigned severity lies outside request bounds")
        severities.append(float(assignment.severity_value))

    if patients > 1 and not max(severities) > min(severities):
        raise AssertionError("three-subject qualification plan is not heterogeneous")

    plan_path = root / "cohort_plan.json"
    vq.disease.write_cohort_plan(first, plan_path, overwrite=True)
    return first, plan_path


def validate_subject(subject_root: Path, subject_id: str):
    subject_manifest = json.loads(
        (subject_root / "subject_manifest.json").read_text(encoding="utf-8")
    )
    diagnostics = json.loads(
        (subject_root / "diagnostics.json").read_text(encoding="utf-8")
    )
    network_index = json.loads(
        (subject_root / "full_network_index.json").read_text(encoding="utf-8")
    )
    if subject_manifest["canonical_subject_id"] != subject_id:
        raise AssertionError("runtime changed the canonical PWDB subject ID")
    if not bool(diagnostics.get("converged")):
        raise AssertionError(f"subject {subject_id} did not converge")

    segment_ids = tuple(str(value) for value in network_index["segment_ids"])
    if network_index["segment_count"] != 116:
        raise AssertionError("full-network index is not 116 segments")
    if len(segment_ids) != 116 or len(set(segment_ids)) != 116:
        raise AssertionError("full-network segment inventory is not 116 unique segments")

    result_files = tuple((subject_root / "results").glob("*.json"))
    if len(result_files) != 58:
        raise AssertionError(
            f"subject {subject_id} has {len(result_files)} materialised results"
        )

    minimum_area = math.inf
    maximum_abs_velocity = 0.0
    with np.load(subject_root / "full_network.npz", allow_pickle=False) as payload:
        time_s = np.asarray(payload["time_s"], dtype=float)
        if (
            time_s.ndim != 1
            or time_s.size < 2
            or not np.all(np.isfinite(time_s))
            or not np.all(np.diff(time_s) > 0)
        ):
            raise AssertionError("invalid final-cycle time coordinate")

        for segment_id in segment_ids:
            prefix = f"segment_{segment_id}"
            x = np.asarray(payload[f"{prefix}__x_m"], dtype=float)
            area = np.asarray(payload[f"{prefix}__area_m2"], dtype=float)
            flow = np.asarray(payload[f"{prefix}__flow_m3_per_s"], dtype=float)
            pressure = np.asarray(payload[f"{prefix}__pressure_pa"], dtype=float)
            expected_shape = (time_s.size, x.size)
            if (
                x.ndim != 1
                or x.size < 1
                or area.shape != expected_shape
                or flow.shape != expected_shape
                or pressure.shape != expected_shape
            ):
                raise AssertionError(f"shape mismatch in segment {segment_id}")
            if (
                not np.all(np.isfinite(x))
                or not np.all(np.isfinite(area))
                or not np.all(np.isfinite(flow))
                or not np.all(np.isfinite(pressure))
            ):
                raise AssertionError(f"non-finite state in segment {segment_id}")
            if not np.all(area > 0):
                raise AssertionError(f"non-positive area in segment {segment_id}")
            velocity = flow / area
            if not np.all(np.isfinite(velocity)):
                raise AssertionError(f"non-finite U=Q/A in segment {segment_id}")
            minimum_area = min(minimum_area, float(np.min(area)))
            maximum_abs_velocity = max(
                maximum_abs_velocity,
                float(np.max(np.abs(velocity))),
            )

    return {
        "canonical_subject_id": subject_id,
        "source_age_years": subject_manifest["source_age_years"],
        "severity_parameter": subject_manifest["severity_parameter"],
        "severity_value": subject_manifest["severity_value"],
        "subject_disease_run_id": subject_manifest["subject_disease_run_id"],
        "solver_diagnostics": diagnostics,
        "materialised_results": len(result_files),
        "full_network_segments": len(segment_ids),
        "minimum_area_m2": minimum_area,
        "maximum_absolute_mean_velocity_m_per_s": maximum_abs_velocity,
        "subject_manifest_sha256": _sha256(subject_root / "subject_manifest.json"),
        "full_network_sha256": _sha256(subject_root / "full_network.npz"),
    }


def execute_plan(
    *,
    plan: object,
    plan_path: Path,
    bundle: Path,
    source: Path,
    root: Path,
    label: str,
):
    command = [
        sys.executable,
        "-m",
        "vascuquest",
        "disease",
        "cohort",
        "generate",
        "--plan",
        str(plan_path),
        "--bundle",
        str(bundle),
        "--source",
        str(source),
        "--offline",
        "--yes",
        "--format",
        "json",
        "--output",
        str(root / f"{label}_output.json"),
    ]
    if bundle.exists():
        command.append("--resume")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    verified: dict[str, object] = {}
    assert process.stdout is not None
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            match = SUBJECT_LINE.search(line)
            if match is None:
                continue
            subject_id = match.group(1).strip()
            record = validate_subject(bundle / "subjects" / subject_id, subject_id)
            check = vq.disease.verify_parameterized_cohort_bundle(bundle)
            if check["valid"] is not True:
                raise AssertionError("public cohort verifier returned valid != true")
            if subject_id not in check["canonical_subject_ids"]:
                raise AssertionError(
                    f"public verifier did not include completed subject {subject_id}"
                )
            verified[subject_id] = record
            _write_json(
                root / f"{label}_progress.json",
                {
                    "status": "IN_PROGRESS",
                    "cohort_run_id": plan.run_id,
                    "subjects_verified": [
                        verified[sid]
                        for sid in plan.canonical_subject_ids
                        if sid in verified
                    ],
                    "updated_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            print(
                f"  -> immediate persisted-subject verification PASS: {subject_id}",
                flush=True,
            )
    except Exception:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"native cohort generator exited with {return_code}")

    final = vq.disease.verify_parameterized_cohort_bundle(bundle)
    if final["valid"] is not True or final["status"] != "COMPLETE":
        raise AssertionError("final cohort bundle verification failed")
    if tuple(final["canonical_subject_ids"]) != plan.canonical_subject_ids:
        raise AssertionError("final bundle changed canonical subject ordering")
    if final["subjects_verified"] != plan.request.patients:
        raise AssertionError("final verified subject count mismatch")
    if final["full_network_segment_count_per_completed_subject"] != 116:
        raise AssertionError("final verifier segment-count mismatch")
    if final["evidence"] != "MODELLED":
        raise AssertionError("evidence boundary changed")
    if final["clinical_validation"] is not False:
        raise AssertionError("clinical validation was incorrectly asserted")

    for subject_id in plan.canonical_subject_ids:
        if subject_id not in verified:
            verified[subject_id] = validate_subject(
                bundle / "subjects" / subject_id,
                subject_id,
            )

    return final, tuple(verified[sid] for sid in plan.canonical_subject_ids)


def run_case(
    *,
    phase: str,
    case: dict[str, object],
    patients: int,
    seed: int,
    source: Path,
    output_root: Path,
    session: object,
):
    root = output_root / phase / str(case["condition"])
    root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    plan, plan_path = create_plan(
        session=session,
        case=case,
        patients=patients,
        seed=seed,
        source=source,
        root=root,
    )
    bundle = root / f"bundle_{plan.run_id}"
    verification, subjects = execute_plan(
        plan=plan,
        plan_path=plan_path,
        bundle=bundle,
        source=source,
        root=root,
        label="generation",
    )

    before = {
        sid: {
            "subject_manifest": _sha256(
                bundle / "subjects" / sid / "subject_manifest.json"
            ),
            "full_network": _sha256(
                bundle / "subjects" / sid / "full_network.npz"
            ),
        }
        for sid in plan.canonical_subject_ids
    }

    execute_plan(
        plan=plan,
        plan_path=plan_path,
        bundle=bundle,
        source=source,
        root=root,
        label="resume",
    )

    after = {
        sid: {
            "subject_manifest": _sha256(
                bundle / "subjects" / sid / "subject_manifest.json"
            ),
            "full_network": _sha256(
                bundle / "subjects" / sid / "full_network.npz"
            ),
        }
        for sid in plan.canonical_subject_ids
    }
    if before != after:
        raise AssertionError("resume rewrote a completed subject")

    record = {
        "status": "PASS",
        "phase": phase,
        "condition": case["condition"],
        "patients": patients,
        "seed": seed,
        "run_id": plan.run_id,
        "supported_ages": list(plan.supported_ages),
        "canonical_subject_ids": list(plan.canonical_subject_ids),
        "assignments": [item.to_dict() for item in plan.assignments],
        "rejections": [item.to_dict() for item in plan.rejections],
        "subjects": list(subjects),
        "bundle_verification": verification,
        "resume_checkpoint_immutability": "PASS",
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "bundle_path": str(bundle),
    }
    _write_json(root / "case_result.json", record)
    return record


def run_phase(
    *,
    phase: str,
    drive_pwdb_root: Path,
    local_source: Path,
    output_root: Path,
    code_revision: str,
):
    if phase == "smoke":
        patients = 1
        phase_name = "smoke_1_subject"
        seed_offset = 0
        result_path = output_root / "smoke_results.json"
    elif phase == "full":
        smoke = json.loads(
            (output_root / "smoke_results.json").read_text(encoding="utf-8")
        )
        if smoke.get("status") != "PASS" or smoke.get("cases_completed") != 4:
            raise RuntimeError("full phase is blocked until smoke qualification passes")
        patients = 3
        phase_name = "full_3_subjects"
        seed_offset = 100
        result_path = output_root / "full_results.json"
    else:
        raise ValueError(f"unsupported phase {phase!r}")

    source_records = stage_sources(drive_pwdb_root, local_source, output_root)
    session = vq.open_dataset(
        "pwdb:3275625",
        source=local_source,
        offline=True,
    )
    started = time.monotonic()
    results = []
    try:
        for index, case in enumerate(CASES):
            print(
                f"\n=== {phase.upper()} {index + 1}/4: "
                f"{case['condition']} ===",
                flush=True,
            )
            results.append(
                run_case(
                    phase=phase_name,
                    case=case,
                    patients=patients,
                    seed=BASE_SEED + seed_offset + index,
                    source=local_source,
                    output_root=output_root,
                    session=session,
                )
            )
            _write_json(
                result_path,
                {
                    "status": "IN_PROGRESS",
                    "code_revision": code_revision,
                    "cases_completed": len(results),
                    "results": results,
                },
            )
    except Exception as exc:
        _write_json(
            result_path,
            {
                "status": "FAIL",
                "code_revision": code_revision,
                "cases_completed": len(results),
                "results": results,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": round(time.monotonic() - started, 6),
            },
        )
        raise

    payload = {
        "status": "PASS",
        "code_revision": code_revision,
        "cases_completed": len(results),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "source_artifacts": source_records,
        "results": results,
    }
    _write_json(result_path, payload)
    print(f"\n{phase.upper()} QUALIFICATION: PASS")
    print(result_path)


def finalize(output_root: Path, code_revision: str) -> None:
    smoke = json.loads(
        (output_root / "smoke_results.json").read_text(encoding="utf-8")
    )
    full = json.loads(
        (output_root / "full_results.json").read_text(encoding="utf-8")
    )
    if smoke.get("status") != "PASS" or smoke.get("cases_completed") != 4:
        raise RuntimeError("cannot finalize: smoke phase is not complete/PASS")
    if full.get("status") != "PASS" or full.get("cases_completed") != 4:
        raise RuntimeError("cannot finalize: full phase is not complete/PASS")
    report = {
        "format": "vascuquest-parameterized-cohort-manual-qualification",
        "format_version": 1,
        "status": "PASS",
        "execution_environment": "Google Colab manual qualification",
        "code_revision": code_revision,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "qualification_scope": {
            "canonical_pwdb_source": True,
            "source_artifacts_checksum_verified": True,
            "smoke_phase": "1 subject x 4 conditions",
            "full_phase": "3 subjects x 4 conditions",
            "per_subject_immediate_verification": True,
            "full_network_segment_count": 116,
            "standard_materialised_results_per_subject": 58,
            "resume_checkpoint_immutability": True,
            "original_pwdb_subject_numbers_preserved": True,
        },
        "source_artifacts": full["source_artifacts"],
        "smoke": smoke,
        "full": full,
        "scientific_boundary": {
            "evidence": "MODELLED",
            "healthy_reconstruction_gate": "METRICS_ONLY_THRESHOLDS_NOT_FROZEN",
            "clinical_validation": False,
            "population_interpretation": (
                "designed_counterfactual_not_epidemiological"
            ),
        },
    }
    path = output_root / "parameterized-cohort-qualification.json"
    _write_json(path, report)
    print(json.dumps(
        {
            "status": "PASS",
            "code_revision": code_revision,
            "report": str(path),
        },
        indent=2,
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("smoke", "full", "finalize"), required=True)
    parser.add_argument("--drive-pwdb-root", type=Path, required=True)
    parser.add_argument("--local-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.phase == "finalize":
        finalize(args.output_root, args.code_revision)
    else:
        run_phase(
            phase=args.phase,
            drive_pwdb_root=args.drive_pwdb_root,
            local_source=args.local_source,
            output_root=args.output_root,
            code_revision=args.code_revision,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
