"""Real-PWDB qualification of the structure-preserving JAX disease solver.

One frozen canonical PWDB subject is exercised through all four frozen Virtual
Disease conditions. The frozen NumPy/JAX semidiscrete operator gate is retained
for every transformed network, while the accelerated solver is qualified for
periodic convergence, complete 116-segment output and limiter attribution.
Temporal refinement is the independent time-integration convergence gate.
This is numerical/software qualification, not clinical validation.

A full periodic run of the frozen explicit NumPy solver is deliberately not a
release gate. For the production PWDB Voigt wall, its explicit stability limit
is orders of magnitude smaller than the accelerated wave-CFL step; requiring
millions of explicit steps per cardiac cycle would test computational patience,
not a different scientific model. The scientific reference is therefore the
frozen semidiscrete NumPy operator, checked directly against JAX, together with
fresh accelerated temporal self-convergence.

The runner may reuse already-PASS accelerated disease cases from explicitly
trusted revisions only when a git-diff lineage check proves that the numerical
split solver, frozen reference, baseline reconstruction and disease physics are
unchanged. Reused cases always re-run the current NumPy/JAX operator-equivalence
gate and retain evidence lineage in the new report.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np

import jax_one_subject_qualification as reference
from vascuquest.disease.solver.jax_split_disease import (
    JAX_SPLIT_SCHEME_ID,
    JaxDiseaseOneDSolver,
)
from vascuquest.disease.solver.model import SolverOptions

FORMAT = "vascuquest-jax-split-one-subject-qualification"
FORMAT_VERSION = 1
QUALIFICATION_SUBJECT_ID = "2104"
TRUSTED_REUSE_REVISIONS = {
    "4460009bc1739a9896047c1b9a551113a0076486": (
        "failed only during strict JSON persistence; subsequent commits changed "
        "qualification/reporting code, not the numerical solver or disease physics"
    ),
    "19c6a24d5ec571946440927344801d3a0a40e78d": (
        "all four accelerated disease solves and current operator gates passed; "
        "reuse is permitted only after the runner independently verifies unchanged "
        "numerical/reference/baseline/disease implementation paths"
    ),
}
NUMERICAL_REUSE_PATHS = (
    "src/vascuquest/disease/baseline",
    "src/vascuquest/disease/catalogue.py",
    "src/vascuquest/disease/physics",
    "src/vascuquest/disease/solver/boundaries.py",
    "src/vascuquest/disease/solver/disease_finite_volume.py",
    "src/vascuquest/disease/solver/exact_loss.py",
    "src/vascuquest/disease/solver/jax_disease.py",
    "src/vascuquest/disease/solver/jax_split_disease.py",
    "src/vascuquest/disease/solver/losses.py",
    "src/vascuquest/disease/solver/model.py",
    "src/vascuquest/disease/solver/network.py",
)


def _json_safe(value):
    """Return strict-JSON data while preserving inactive/unbounded telemetry."""

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _limiter_record(baseline, timing) -> dict[str, object]:
    values = {
        "wave": float(timing.minimum_wave_dt_s),
        "voigt_explicit": float(timing.minimum_voigt_explicit_dt_s),
        "focal_loss_explicit": float(timing.minimum_loss_explicit_dt_s),
    }
    finite = {name: value for name, value in values.items() if np.isfinite(value)}
    original_limiter = min(finite, key=finite.get) if finite else "none"
    period = float(baseline.aortic_inflow.duration_s)
    original_dt = min(finite.values()) if finite else period
    explicit_equivalent_steps = int(np.ceil(period / max(original_dt, 1e-30)))
    actual = int(timing.final_cycle_outer_steps)
    return {
        "minimum_dt_s": values,
        "inactive_or_unbounded_limiters": [
            name for name, value in values.items() if not np.isfinite(value)
        ],
        "dominant_original_explicit_limiter": original_limiter,
        "old_explicit_equivalent_steps_per_cycle": explicit_equivalent_steps,
        "accelerated_outer_steps_per_cycle": actual,
        "outer_step_reduction_factor": float(explicit_equivalent_steps / max(actual, 1)),
        "rkc_stages_total": int(timing.final_cycle_rkc_stages_total),
        "rkc_stages_max": int(timing.final_cycle_rkc_stages_max),
        "exact_loss_updates": int(timing.exact_loss_updates),
    }


def _prepare_frozen_subject(session, assembler, options: SolverOptions):
    """Assemble the already-qualified canonical subject without population scans."""

    print(
        f"Qualification subject: {QUALIFICATION_SUBJECT_ID} (frozen canonical PWDB subject)",
        flush=True,
    )
    print("Assembling subject baseline from local PWDB artifacts...", flush=True)
    baseline = assembler.assemble(session, QUALIFICATION_SUBJECT_ID)
    if str(baseline.canonical_subject_id) != QUALIFICATION_SUBJECT_ID:
        raise AssertionError("PWDB assembler returned the wrong frozen qualification subject")
    if int(baseline.age_years) != 45:
        raise AssertionError("frozen qualification subject 2104 no longer has expected age 45")
    print("Baseline assembly: PASS; constructing four disease transforms...", flush=True)
    cases = reference._case_specifications(baseline, options)
    physics = tuple(
        (name, reference.transform_disease(baseline, spec, options=options))
        for name, spec in cases
    )
    print("Four disease transforms: PASS", flush=True)
    return baseline, cases, physics


def _validate_reuse_lineage(
    source_revision: str,
    current_revision: str,
) -> dict[str, object]:
    """Prove that retained accelerated evidence crosses no numerical code change."""

    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "qualification evidence reuse requires execution inside the VascuQuest git checkout"
        ) from exc

    for revision in (source_revision, current_revision):
        probe = subprocess.run(
            ["git", "-C", repo_root, "cat-file", "-e", f"{revision}^{{commit}}"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            raise RuntimeError(
                f"qualification evidence lineage commit {revision!r} is unavailable; fetch it before reuse"
            )

    command = [
        "git",
        "-C",
        repo_root,
        "diff",
        "--name-only",
        source_revision,
        current_revision,
        "--",
        *NUMERICAL_REUSE_PATHS,
    ]
    changed = [
        item
        for item in subprocess.check_output(command, text=True).splitlines()
        if item.strip()
    ]
    if changed:
        raise RuntimeError(
            "trusted qualification evidence cannot cross numerical/scientific code changes: "
            + ", ".join(changed)
        )
    return {
        "status": "PASS",
        "source_revision": source_revision,
        "current_revision": current_revision,
        "changed_numerical_paths": [],
        "protected_paths": list(NUMERICAL_REUSE_PATHS),
    }


def _load_reusable_cases(
    reuse_report: Path | None,
    *,
    baseline,
    current_cases,
    code_revision: str,
) -> tuple[dict[str, dict[str, object]], dict[str, object] | None]:
    if reuse_report is None or not reuse_report.exists():
        return {}, None
    print(f"Validating trusted partial evidence: {reuse_report}", flush=True)
    payload = json.loads(reuse_report.read_text(encoding="utf-8"))
    revision = str(payload.get("code_revision", ""))
    if revision not in TRUSTED_REUSE_REVISIONS:
        raise RuntimeError(
            f"reuse report revision {revision!r} is not an explicitly trusted numerical-equivalence revision"
        )
    lineage_check = _validate_reuse_lineage(revision, code_revision)
    if payload.get("format") != FORMAT:
        raise RuntimeError("reuse report is not a JAX split qualification report")
    if payload.get("numerical_scheme_id") != JAX_SPLIT_SCHEME_ID:
        raise RuntimeError("reuse report numerical scheme does not match current split solver")
    if str(payload.get("canonical_subject_id")) != str(baseline.canonical_subject_id):
        raise RuntimeError("reuse report canonical PWDB subject does not match current qualification")
    if int(payload.get("source_age_years")) != int(baseline.age_years):
        raise RuntimeError("reuse report subject age does not match current qualification")

    expected = {name: reference._spec_payload(spec) for name, spec in current_cases}
    reusable: dict[str, dict[str, object]] = {}
    for raw in payload.get("cases", []):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("condition", ""))
        if name not in expected:
            continue
        if raw.get("specification") != expected[name]:
            continue
        operator = raw.get("operator_equivalence", {})
        accelerated = raw.get("accelerated_full_solve", {})
        diagnostics = accelerated.get("diagnostics", {}) if isinstance(accelerated, dict) else {}
        timing = accelerated.get("timing", {}) if isinstance(accelerated, dict) else {}
        if not (
            isinstance(operator, dict)
            and operator.get("passed") is True
            and isinstance(accelerated, dict)
            and accelerated.get("status") == "PASS"
            and diagnostics.get("converged") is True
            and int(accelerated.get("segments", 0)) == 116
            and timing.get("scheme_id") == JAX_SPLIT_SCHEME_ID
        ):
            continue
        reusable[name] = deepcopy(raw)

    lineage = {
        "source_report": str(reuse_report),
        "source_code_revision": revision,
        "reuse_basis": TRUSTED_REUSE_REVISIONS[revision],
        "numerical_lineage_check": lineage_check,
        "reused_conditions": sorted(reusable),
        "current_operator_gate_reexecuted": True,
    }
    print(f"Reusable PASS cases: {sorted(reusable)}", flush=True)
    return reusable, lineage


def qualify(
    source: Path,
    report_path: Path,
    code_revision: str,
    *,
    reuse_report: Path | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    options = SolverOptions()
    print("Opening canonical PWDB 3275625 in offline/local mode...", flush=True)
    session = reference.vq.open_dataset("pwdb:3275625", source=source, offline=True)
    assembler = reference.PWDBBaselineAssembler(reference._acquisition(source), offline=True)
    baseline, cases, physics_cases = _prepare_frozen_subject(session, assembler, options)
    reusable, reuse_lineage = _load_reusable_cases(
        reuse_report,
        baseline=baseline,
        current_cases=cases,
        code_revision=code_revision,
    )

    report: dict[str, object] = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "status": "IN_PROGRESS",
        "code_revision": code_revision,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_subject_id": baseline.canonical_subject_id,
        "source_age_years": baseline.age_years,
        "numerical_scheme_id": JAX_SPLIT_SCHEME_ID,
        "selection_mode": "frozen_canonical_subject_no_population_scan",
        "reference_operator_limits": {
            "relative_l2": reference.OPERATOR_RELATIVE_L2_LIMIT,
            "max_scaled": reference.OPERATOR_MAX_SCALED_LIMIT,
            "stability_relative": reference.STABILITY_RELATIVE_LIMIT,
        },
        "reference_strategy": {
            "scientific_reference": "frozen_numpy_semidiscrete_operator",
            "full_periodic_numpy_anchor_required": False,
            "reason": (
                "The frozen NumPy solver advances the same semidiscrete model with an "
                "explicit Voigt step. Real-PWDB limiter telemetry shows that this step "
                "requires millions of updates per cardiac cycle. Numerical identity is "
                "therefore tested directly at the semidiscrete operator/stability level; "
                "the accelerated time integrator is independently qualified by fresh "
                "temporal refinement over one complete cardiac cycle."
            ),
            "temporal_refinement_required_for_final_pass": True,
        },
        "cases": [],
        "evidence_reuse": reuse_lineage,
        "scientific_boundary": {
            "evidence": "MODELLED",
            "clinical_validation": False,
            "population_interpretation": "single_subject_backend_qualification_not_epidemiological",
        },
    }
    _write(report_path, report)
    print(f"Qualification report initialized: {report_path}", flush=True)

    for index, ((name, spec), (physics_name, physics)) in enumerate(
        zip(cases, physics_cases, strict=True), start=1
    ):
        if name != physics_name:
            raise RuntimeError("internal qualification case ordering mismatch")

        print(f"\n[{index}/4] {name}: frozen NumPy/JAX operator gate", flush=True)
        operator = reference._operator_gate(baseline, physics, options)
        for loss in physics.pressure_losses:
            if float(loss.inertance_pa_s2_per_m3) != 0.0:
                raise AssertionError(f"{name} unexpectedly requires nonzero excess inertance")

        if name in reusable:
            case_record = reusable[name]
            case_record["operator_equivalence"] = operator
            case_record["reuse_provenance"] = {
                "reused": True,
                "source_code_revision": reuse_lineage["source_code_revision"],
                "reason": reuse_lineage["reuse_basis"],
                "numerical_lineage_check": reuse_lineage["numerical_lineage_check"],
                "current_operator_gate_reexecuted": True,
            }
            report["cases"].append(case_record)
            _write(report_path, report)
            print(
                f"[{index}/4] {name}: REUSED prior PASS full solve; current operator gate PASS",
                flush=True,
            )
            continue

        print(f"[{index}/4] {name}: accelerated split solve", flush=True)
        solver = JaxDiseaseOneDSolver(options)
        wall_start = time.perf_counter()
        solution = solver.solve(
            baseline,
            physics.network,
            pressure_losses=physics.pressure_losses,
        )
        wall = time.perf_counter() - wall_start
        reference._validate_solution(solution)
        if solver.last_timing is None:
            raise AssertionError("accelerated solver did not expose timing/limiter telemetry")
        timing = solver.last_timing
        if timing.scheme_id != JAX_SPLIT_SCHEME_ID:
            raise AssertionError("accelerated solver reported the wrong numerical scheme")
        if timing.final_cycle_outer_steps < 1 or timing.final_cycle_rkc_stages_max < 2:
            raise AssertionError("accelerated solver telemetry is incomplete")
        if physics.pressure_losses and timing.exact_loss_updates <= 0:
            raise AssertionError("focal disease solve did not execute exact loss updates")
        if not physics.pressure_losses and timing.exact_loss_updates != 0:
            raise AssertionError("non-focal disease solve unexpectedly executed focal loss updates")

        case_record = {
            "condition": name,
            "specification": reference._spec_payload(spec),
            "modified_segment_ids": list(physics.modified_segment_ids),
            "operator_equivalence": operator,
            "accelerated_full_solve": {
                "status": "PASS",
                "wall_seconds": wall,
                "diagnostics": asdict(solution.diagnostics),
                "segments": len(solution.segments),
                "final_cycle_samples": int(solution.time_s.size),
                "timing": asdict(timing),
                "limiter_attribution": _limiter_record(baseline, timing),
            },
        }
        report["cases"].append(case_record)
        _write(report_path, report)
        print(
            f"[{index}/4] {name}: PASS in {wall:.3f}s; "
            f"outer_steps={timing.final_cycle_outer_steps}, "
            f"max_rkc_stages={timing.final_cycle_rkc_stages_max}",
            flush=True,
        )

    if len(report["cases"]) != 4:
        raise AssertionError("qualification did not retain all four disease cases")
    if not all(item["operator_equivalence"]["passed"] is True for item in report["cases"]):
        raise AssertionError("one or more current operator-equivalence gates did not pass")

    report["main_stage"] = {
        "status": "PASS",
        "four_disease_periodic_convergence": True,
        "complete_116_segment_outputs": True,
        "current_operator_equivalence": True,
        "limiter_attribution": True,
    }
    report["status"] = "AWAITING_TEMPORAL_REFINEMENT"
    report["elapsed_seconds"] = time.perf_counter() - started
    report["generated_utc"] = datetime.now(timezone.utc).isoformat()
    _write(report_path, report)
    print("\nJAX SPLIT MAIN QUALIFICATION: PASS", flush=True)
    print("Final PASS requires temporal refinement.", flush=True)
    print(report_path, flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--reuse-report", type=Path)
    args = parser.parse_args()
    try:
        qualify(
            args.source,
            args.report,
            args.code_revision,
            reuse_report=args.reuse_report,
        )
    except Exception as exc:
        payload: dict[str, object]
        if args.report.exists():
            try:
                payload = json.loads(args.report.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        else:
            payload = {}
        payload.update(
            {
                "format": FORMAT,
                "format_version": FORMAT_VERSION,
                "status": "FAIL",
                "code_revision": args.code_revision,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "scientific_boundary": {
                    "evidence": "MODELLED",
                    "clinical_validation": False,
                },
            }
        )
        _write(args.report, payload)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
