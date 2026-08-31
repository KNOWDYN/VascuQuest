"""One-subject real-PWDB qualification of the optional JAX Virtual Disease solver.

The same canonical PWDB subject is used for all four frozen disease conditions.
For every transformed network, the NumPy and JAX RHS/stability operators are
compared on the same deterministic non-trivial state. All four cases then run
to periodic convergence with JAX. One coarse-network stiffening case is also
solved end-to-end with the frozen NumPy reference and compared across the full
116-segment final cycle. The benchmark is reported separately from correctness.

This is software/mechanistic qualification, not clinical validation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

import numpy as np

import vascuquest as vq
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry
from vascuquest.disease.baseline import PWDBBaselineAssembler
from vascuquest.disease.catalogue import specification
from vascuquest.disease.physics import model_cfpwv_m_per_s, transform_disease
from vascuquest.disease.solver.disease_finite_volume import (
    DiseaseOneDSolver,
    _loss_stability_dt,
    _losses_by_segment,
    _rhs,
    _stability_dt,
)
from vascuquest.disease.solver.jax_disease import (
    JaxDiseaseOneDSolver,
    jax_operator_snapshot,
)
from vascuquest.disease.solver.model import SolverOptions
from vascuquest.disease.solver.network import build_network


OPERATOR_RELATIVE_L2_LIMIT = 1e-8
OPERATOR_MAX_SCALED_LIMIT = 5e-8
STABILITY_RELATIVE_LIMIT = 1e-8
ANCHOR_LIMITS = {
    "area_m2": 5e-3,
    "flow_m3_per_s": 1e-2,
    "pressure_pa": 5e-3,
}
SEED = 17031


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _acquisition(source: Path) -> ArtifactAcquirer:
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    registry.register_local(source)
    return ArtifactAcquirer(paths, registry)


def _rank(subject_id: str) -> bytes:
    return hashlib.sha256(f"{SEED}\0jax-qualification\0{subject_id}".encode()).digest()


def _case_specifications(baseline, options: SolverOptions):
    healthy = build_network(baseline, options)
    baseline_cfpwv = model_cfpwv_m_per_s(healthy, baseline)
    return (
        (
            "carotid_stenosis",
            specification(
                "carotid_stenosis",
                {
                    "side": "left",
                    "artery": "common_carotid",
                    "nascet_stenosis": 0.55,
                    "lesion_length_m": 0.020,
                    "lesion_center_fraction": 0.50,
                },
            ),
        ),
        (
            "iliac_stenosis",
            specification(
                "iliac_stenosis",
                {
                    "side": "right",
                    "artery": "common_iliac",
                    "diameter_stenosis": 0.50,
                    "lesion_length_m": 0.030,
                    "lesion_center_fraction": 0.50,
                },
            ),
        ),
        (
            "fusiform_abdominal_aortic_aneurysm",
            specification(
                "fusiform_abdominal_aortic_aneurysm",
                {
                    "maximum_diameter_m": 0.040,
                    "aneurysm_length_m": 0.100,
                    "aneurysm_center_fraction": 0.50,
                },
            ),
        ),
        (
            "large_artery_stiffening",
            specification(
                "large_artery_stiffening",
                {"target_cfpwv_m_per_s": 1.25 * baseline_cfpwv},
            ),
        ),
    )


def _select_subject(session, assembler, options: SolverOptions):
    subjects = tuple(session.subjects())
    ids = tuple(str(item.canonical_subject_id) for item in subjects)
    ages = np.asarray(session.get("age").values, dtype=float).reshape(-1)
    candidates = [
        (subject_id, int(round(age)))
        for subject_id, age in zip(ids, ages, strict=True)
        if int(round(age)) in {45, 55}
    ]
    candidates.sort(key=lambda item: (_rank(item[0]), item[0]))
    rejections = []
    for subject_id, age in candidates:
        baseline = assembler.assemble(session, subject_id)
        try:
            cases = _case_specifications(baseline, options)
            physics = tuple(
                (name, transform_disease(baseline, spec, options=options))
                for name, spec in cases
            )
        except Exception as exc:
            rejections.append(
                {
                    "canonical_subject_id": subject_id,
                    "age_years": age,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        return baseline, cases, physics, rejections
    raise RuntimeError("no age-45/55 PWDB subject was admissible for all four qualification cases")


def _deterministic_state(baseline, network):
    conserved = {}
    mean_q = float(baseline.aortic_inflow.mean_flow_m3_per_s)
    for segment_index, mesh in enumerate(network.meshes):
        phase = np.linspace(0.0, 1.0, mesh.cell_count, endpoint=False)
        offset = 0.071 * (segment_index + 1)
        area = np.asarray(mesh.reference_area_m2, dtype=float) * (
            1.0 + 0.006 * np.sin(2.0 * np.pi * phase + offset)
        )
        flow = mean_q * (
            0.70 + 0.12 * np.cos(2.0 * np.pi * phase + 0.5 * offset)
        )
        conserved[mesh.segment_id] = np.vstack((area, flow))
    capacitor = {
        sid: float(baseline.diastolic_pressure_pa + 250.0)
        for sid in baseline.terminal_segment_ids
    }
    return conserved, capacitor


def _relative_metrics(reference: np.ndarray, candidate: np.ndarray):
    ref = np.asarray(reference, dtype=float).reshape(-1)
    got = np.asarray(candidate, dtype=float).reshape(-1)
    if ref.shape != got.shape:
        raise AssertionError(f"operator shape mismatch: {ref.shape} != {got.shape}")
    diff = got - ref
    relative_l2 = float(np.linalg.norm(diff) / max(np.linalg.norm(ref), 1e-30))
    max_scaled = float(np.max(np.abs(diff)) / max(np.max(np.abs(ref)), 1e-30))
    return relative_l2, max_scaled


def _operator_gate(baseline, physics, options: SolverOptions):
    conserved, capacitor = _deterministic_state(baseline, physics.network)
    loss_map = _losses_by_segment(physics.network, physics.pressure_losses)
    time_s = 0.37 * baseline.aortic_inflow.duration_s
    numpy_rhs, numpy_pc = _rhs(
        baseline,
        physics.network,
        conserved,
        capacitor,
        time_s,
        loss_map,
    )
    numpy_dt, numpy_cfl_rate, numpy_diffusion_rate = _stability_dt(
        conserved, physics.network, baseline, options
    )
    numpy_loss_dt = _loss_stability_dt(
        conserved, physics.network, baseline, options, loss_map
    )
    numpy_total_dt = min(numpy_dt, numpy_loss_dt)

    jax_snapshot = jax_operator_snapshot(
        baseline,
        physics.network,
        conserved,
        capacitor,
        pressure_losses=physics.pressure_losses,
        time_s=time_s,
        options=options,
    )
    ref_state = np.concatenate(
        [np.asarray(numpy_rhs[sid], dtype=float).reshape(-1) for sid in sorted(numpy_rhs)]
    )
    jax_state = np.concatenate(
        [
            np.asarray(jax_snapshot.derivatives[sid], dtype=float).reshape(-1)
            for sid in sorted(numpy_rhs)
        ]
    )
    relative_l2, max_scaled = _relative_metrics(ref_state, jax_state)
    terminal_ids = sorted(numpy_pc)
    ref_pc = np.asarray([numpy_pc[sid] for sid in terminal_ids], dtype=float)
    got_pc = np.asarray(
        [jax_snapshot.capacitor_derivatives[sid] for sid in terminal_ids], dtype=float
    )
    pc_relative_l2, pc_max_scaled = _relative_metrics(ref_pc, got_pc)
    dt_relative = abs(jax_snapshot.stability_dt_s - numpy_total_dt) / max(
        abs(numpy_total_dt), 1e-30
    )
    cfl_relative = abs(
        jax_snapshot.hyperbolic_cfl_rate_per_s - numpy_cfl_rate
    ) / max(abs(numpy_cfl_rate), 1e-30)
    diffusion_relative = abs(
        jax_snapshot.diffusion_rate_per_s - numpy_diffusion_rate
    ) / max(abs(numpy_diffusion_rate), 1e-30)

    passed = (
        relative_l2 <= OPERATOR_RELATIVE_L2_LIMIT
        and max_scaled <= OPERATOR_MAX_SCALED_LIMIT
        and pc_relative_l2 <= OPERATOR_RELATIVE_L2_LIMIT
        and pc_max_scaled <= OPERATOR_MAX_SCALED_LIMIT
        and dt_relative <= STABILITY_RELATIVE_LIMIT
        and cfl_relative <= STABILITY_RELATIVE_LIMIT
        and diffusion_relative <= STABILITY_RELATIVE_LIMIT
    )
    record = {
        "passed": passed,
        "rhs_relative_l2": relative_l2,
        "rhs_max_scaled_error": max_scaled,
        "capacitor_rhs_relative_l2": pc_relative_l2,
        "capacitor_rhs_max_scaled_error": pc_max_scaled,
        "stability_dt_relative_error": dt_relative,
        "cfl_rate_relative_error": cfl_relative,
        "diffusion_rate_relative_error": diffusion_relative,
        "numpy_total_dt_s": float(numpy_total_dt),
        "jax_total_dt_s": float(jax_snapshot.stability_dt_s),
        "numpy_loss_dt_s": float(numpy_loss_dt),
        "jax_loss_dt_s": float(jax_snapshot.disease_loss_dt_s),
    }
    if not passed:
        raise AssertionError(f"NumPy/JAX operator-equivalence gate failed: {record}")
    return record


def _validate_solution(solution):
    if not solution.diagnostics.converged:
        raise AssertionError("solver did not reach periodic convergence")
    if len(solution.segments) != 116:
        raise AssertionError("solution does not contain all 116 arterial segments")
    if not np.all(np.isfinite(solution.time_s)) or not np.all(np.diff(solution.time_s) > 0):
        raise AssertionError("solution time coordinate is invalid")
    for segment in solution.segments:
        for values in (segment.area_m2, segment.flow_m3_per_s, segment.pressure_pa):
            if not np.all(np.isfinite(values)):
                raise AssertionError(f"non-finite solution state in segment {segment.segment_id}")
        if not np.all(segment.area_m2 > 0):
            raise AssertionError(f"non-positive area in segment {segment.segment_id}")
        velocity = segment.flow_m3_per_s / segment.area_m2
        if not np.all(np.isfinite(velocity)):
            raise AssertionError(f"non-finite U=Q/A in segment {segment.segment_id}")


def _field_equivalence(reference, candidate, points: int = 192):
    if tuple(item.segment_id for item in reference.segments) != tuple(
        item.segment_id for item in candidate.segments
    ):
        raise AssertionError("NumPy/JAX segment identity/order mismatch")
    target = np.linspace(0.0, min(reference.time_s[-1], candidate.time_s[-1]), points)
    sums = {name: [0.0, 0.0] for name in ANCHOR_LIMITS}
    for ref_segment, got_segment in zip(reference.segments, candidate.segments, strict=True):
        if ref_segment.x_m.shape != got_segment.x_m.shape or not np.allclose(
            ref_segment.x_m, got_segment.x_m, rtol=0.0, atol=1e-14
        ):
            raise AssertionError(f"NumPy/JAX mesh mismatch in segment {ref_segment.segment_id}")
        for name in ANCHOR_LIMITS:
            ref_values = getattr(ref_segment, name)
            got_values = getattr(got_segment, name)
            for cell in range(ref_values.shape[1]):
                ref_wave = np.interp(target, reference.time_s, ref_values[:, cell])
                got_wave = np.interp(target, candidate.time_s, got_values[:, cell])
                diff = got_wave - ref_wave
                sums[name][0] += float(np.sum(diff * diff))
                sums[name][1] += float(np.sum(ref_wave * ref_wave))
    errors = {
        name: float(np.sqrt(num / max(den, 1e-30)))
        for name, (num, den) in sums.items()
    }
    if any(errors[name] > ANCHOR_LIMITS[name] for name in errors):
        raise AssertionError(f"full-solution NumPy/JAX anchor equivalence failed: {errors}")
    return errors


def qualify(source: Path, report_path: Path, code_revision: str) -> dict[str, object]:
    started = time.perf_counter()
    options = SolverOptions()
    session = vq.open_dataset("pwdb:3275625", source=source, offline=True)
    assembler = PWDBBaselineAssembler(_acquisition(source), offline=True)
    baseline, cases, physics_cases, rejections = _select_subject(session, assembler, options)

    report: dict[str, object] = {
        "format": "vascuquest-jax-one-subject-qualification",
        "format_version": 1,
        "status": "IN_PROGRESS",
        "code_revision": code_revision,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_subject_id": baseline.canonical_subject_id,
        "source_age_years": baseline.age_years,
        "selection_rejections": rejections,
        "operator_limits": {
            "relative_l2": OPERATOR_RELATIVE_L2_LIMIT,
            "max_scaled": OPERATOR_MAX_SCALED_LIMIT,
            "stability_relative": STABILITY_RELATIVE_LIMIT,
        },
        "anchor_limits": ANCHOR_LIMITS,
        "cases": [],
        "scientific_boundary": {
            "evidence": "MODELLED",
            "clinical_validation": False,
            "population_interpretation": "single_subject_backend_qualification_not_epidemiological",
        },
    }
    _write_json(report_path, report)

    jax_solutions = {}
    for index, ((name, spec), (physics_name, physics)) in enumerate(
        zip(cases, physics_cases, strict=True), start=1
    ):
        if name != physics_name:
            raise RuntimeError("internal qualification case ordering mismatch")
        print(f"\n[{index}/4] {name}: NumPy/JAX operator equivalence", flush=True)
        operator = _operator_gate(baseline, physics, options)
        print(f"[{index}/4] {name}: operator PASS; JAX full solve", flush=True)
        solver = JaxDiseaseOneDSolver(options)
        wall_start = time.perf_counter()
        solution = solver.solve(
            baseline, physics.network, pressure_losses=physics.pressure_losses
        )
        wall = time.perf_counter() - wall_start
        _validate_solution(solution)
        jax_solutions[name] = solution
        timing = asdict(solver.last_timing) if solver.last_timing is not None else {}
        case_record = {
            "condition": name,
            "specification": spec.to_dict(),
            "modified_segment_ids": list(physics.modified_segment_ids),
            "operator_equivalence": operator,
            "jax_full_solve": {
                "status": "PASS",
                "wall_seconds": wall,
                "diagnostics": asdict(solution.diagnostics),
                "segments": len(solution.segments),
                "final_cycle_samples": int(solution.time_s.size),
                "timing": timing,
            },
        }
        report["cases"].append(case_record)
        _write_json(report_path, report)
        print(f"[{index}/4] {name}: JAX full solve PASS in {wall:.3f}s", flush=True)

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
    _validate_solution(numpy_solution)
    jax_solution = jax_solutions[anchor_name]
    errors = _field_equivalence(numpy_solution, jax_solution)
    jax_wall = next(
        item["jax_full_solve"]["wall_seconds"]
        for item in report["cases"]
        if item["condition"] == anchor_name
    )
    speedup = float(numpy_wall / max(float(jax_wall), 1e-12))
    report["full_numpy_jax_anchor"] = {
        "condition": anchor_name,
        "status": "PASS",
        "numpy_wall_seconds": numpy_wall,
        "jax_wall_seconds_including_compile": jax_wall,
        "speedup_including_jax_compile": speedup,
        "relative_l2_errors": errors,
        "numpy_diagnostics": asdict(numpy_solution.diagnostics),
        "jax_diagnostics": asdict(jax_solution.diagnostics),
    }
    report["status"] = "PASS"
    report["elapsed_seconds"] = time.perf_counter() - started
    report["generated_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(report_path, report)
    print("\nJAX ONE-SUBJECT QUALIFICATION: PASS", flush=True)
    print(json.dumps(report["full_numpy_jax_anchor"], indent=2, sort_keys=True), flush=True)
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
        failure = {
            "format": "vascuquest-jax-one-subject-qualification",
            "format_version": 1,
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
        _write_json(args.report, failure)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
