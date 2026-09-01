"""Real-PWDB qualification of the structure-preserving JAX disease solver.

One deterministic canonical PWDB subject is exercised through all four frozen
Virtual Disease conditions.  The frozen NumPy/JAX semidiscrete operator gate
is retained, while the accelerated solver is qualified for convergence,
complete 116-segment output, limiter attribution, exact-loss execution and one
full NumPy anchor.  This is numerical/software qualification, not clinical
validation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import traceback

import numpy as np

import jax_one_subject_qualification as reference
from vascuquest.disease.solver.disease_finite_volume import DiseaseOneDSolver
from vascuquest.disease.solver.jax_split_disease import (
    JAX_SPLIT_SCHEME_ID,
    JaxDiseaseOneDSolver,
)
from vascuquest.disease.solver.model import SolverOptions

FORMAT = "vascuquest-jax-split-one-subject-qualification"
FORMAT_VERSION = 1


def _json_safe(value):
    """Return strict-JSON data while preserving inactive/unbounded telemetry.

    Numerical limiter telemetry legitimately uses +inf when an operator is
    inactive (for example focal-loss dt for AAA/stiffening). JSON has no
    standard infinity literal, so non-finite floating values are persisted as
    null. The surrounding limiter fields retain the semantic meaning.
    """

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


def qualify(source: Path, report_path: Path, code_revision: str) -> dict[str, object]:
    started = time.perf_counter()
    options = SolverOptions()
    session = reference.vq.open_dataset("pwdb:3275625", source=source, offline=True)
    assembler = reference.PWDBBaselineAssembler(reference._acquisition(source), offline=True)
    baseline, cases, physics_cases, rejections = reference._select_subject(
        session, assembler, options
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
        "selection_rejections": rejections,
        "reference_operator_limits": {
            "relative_l2": reference.OPERATOR_RELATIVE_L2_LIMIT,
            "max_scaled": reference.OPERATOR_MAX_SCALED_LIMIT,
            "stability_relative": reference.STABILITY_RELATIVE_LIMIT,
        },
        "reference_anchor_limits": reference.ANCHOR_LIMITS,
        "cases": [],
        "scientific_boundary": {
            "evidence": "MODELLED",
            "clinical_validation": False,
            "population_interpretation": "single_subject_backend_qualification_not_epidemiological",
        },
    }
    _write(report_path, report)

    solutions = {}
    for index, ((name, spec), (physics_name, physics)) in enumerate(
        zip(cases, physics_cases, strict=True), start=1
    ):
        if name != physics_name:
            raise RuntimeError("internal qualification case ordering mismatch")
        print(f"\n[{index}/4] {name}: frozen NumPy/JAX operator gate", flush=True)
        operator = reference._operator_gate(baseline, physics, options)

        for loss in physics.pressure_losses:
            if float(loss.inertance_pa_s2_per_m3) != 0.0:
                raise AssertionError(
                    f"{name} unexpectedly requires nonzero excess inertance"
                )

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

        solutions[name] = solution
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

    # The non-focal stiffening model avoids the pathological lesion mesh/loss
    # restriction and is therefore retained as the complete frozen-NumPy anchor.
    anchor_name = "large_artery_stiffening"
    anchor_physics = dict(physics_cases)[anchor_name]
    print("\nAnchor: frozen NumPy full solve", flush=True)
    numpy_start = time.perf_counter()
    numpy_solution = DiseaseOneDSolver(options).solve(
        baseline,
        anchor_physics.network,
        pressure_losses=anchor_physics.pressure_losses,
    )
    numpy_wall = time.perf_counter() - numpy_start
    reference._validate_solution(numpy_solution)
    accelerated_solution = solutions[anchor_name]
    errors = reference._field_equivalence(numpy_solution, accelerated_solution)
    accelerated_wall = next(
        item["accelerated_full_solve"]["wall_seconds"]
        for item in report["cases"]
        if item["condition"] == anchor_name
    )
    report["full_numpy_anchor"] = {
        "condition": anchor_name,
        "status": "PASS",
        "numpy_wall_seconds": numpy_wall,
        "accelerated_wall_seconds_including_compile": accelerated_wall,
        "speedup_including_compile": float(
            numpy_wall / max(float(accelerated_wall), 1e-12)
        ),
        "relative_l2_errors": errors,
        "numpy_diagnostics": asdict(numpy_solution.diagnostics),
        "accelerated_diagnostics": asdict(accelerated_solution.diagnostics),
    }

    report["status"] = "PASS"
    report["elapsed_seconds"] = time.perf_counter() - started
    report["generated_utc"] = datetime.now(timezone.utc).isoformat()
    _write(report_path, report)
    print("\nJAX SPLIT ONE-SUBJECT QUALIFICATION: PASS", flush=True)
    print(json.dumps(_json_safe(report["full_numpy_anchor"]), indent=2, sort_keys=True), flush=True)
    print(report_path, flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    try:
        qualify(args.source, args.report, args.code_revision)
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
