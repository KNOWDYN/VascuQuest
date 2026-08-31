"""Temporal-refinement gate for the accelerated JAX split solver.

Uses the same deterministic real-PWDB subject and carotid-stenosis model as the
main qualification. Spatial discretisation and disease physics are held fixed;
only the outer wave-CFL number is halved. The final periodic solutions must
show approximately second-order self-convergence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import time

import numpy as np

import jax_one_subject_qualification as reference
from vascuquest.disease.solver.jax_split_disease import JaxDiseaseOneDSolver
from vascuquest.disease.solver.model import SolverOptions

CFL_LEVELS = (0.40, 0.20, 0.10)
MIN_OBSERVED_ORDER = 1.50


def _field_difference(first, second) -> dict[str, float]:
    if tuple(item.segment_id for item in first.segments) != tuple(
        item.segment_id for item in second.segments
    ):
        raise AssertionError("temporal-refinement segment identity/order mismatch")
    if not np.array_equal(first.time_s, second.time_s):
        raise AssertionError("temporal-refinement output grids must be identical")
    result: dict[str, float] = {}
    for field in ("area_m2", "flow_m3_per_s", "pressure_pa"):
        numerator = 0.0
        denominator = 0.0
        for a, b in zip(first.segments, second.segments, strict=True):
            av = np.asarray(getattr(a, field), dtype=float)
            bv = np.asarray(getattr(b, field), dtype=float)
            if av.shape != bv.shape:
                raise AssertionError(f"temporal-refinement shape mismatch for {field}")
            diff = av - bv
            numerator += float(np.sum(diff * diff))
            denominator += float(np.sum(bv * bv))
        result[field] = float(math.sqrt(numerator / max(denominator, 1e-30)))
    return result


def run(source: Path, main_report: Path) -> dict[str, object]:
    payload = json.loads(main_report.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS":
        raise RuntimeError("main split-solver qualification must PASS before temporal refinement")

    base_options = SolverOptions(
        cfl=CFL_LEVELS[0],
        periodicity_tolerance=1e-6,
        minimum_cycles=4,
        maximum_cycles=30,
    )
    session = reference.vq.open_dataset("pwdb:3275625", source=source, offline=True)
    assembler = reference.PWDBBaselineAssembler(reference._acquisition(source), offline=True)
    baseline, _, physics_cases, _ = reference._select_subject(
        session, assembler, base_options
    )
    if baseline.canonical_subject_id != payload.get("canonical_subject_id"):
        raise AssertionError("temporal-refinement subject differs from main qualification")
    physics = dict(physics_cases)["carotid_stenosis"]

    solutions = []
    runs = []
    for cfl in CFL_LEVELS:
        options = SolverOptions(
            cfl=cfl,
            periodicity_tolerance=1e-6,
            minimum_cycles=4,
            maximum_cycles=30,
        )
        # Disease transformation is independent of CFL and only depends on
        # spatial options here; all spatial controls remain at their defaults.
        solver = JaxDiseaseOneDSolver(options)
        started = time.perf_counter()
        solution = solver.solve(
            baseline,
            physics.network,
            pressure_losses=physics.pressure_losses,
        )
        wall = time.perf_counter() - started
        reference._validate_solution(solution)
        if solver.last_timing is None:
            raise AssertionError("temporal-refinement run lacks solver telemetry")
        solutions.append(solution)
        runs.append(
            {
                "cfl": cfl,
                "wall_seconds": wall,
                "diagnostics": asdict(solution.diagnostics),
                "timing": asdict(solver.last_timing),
            }
        )
        print(
            f"temporal refinement cfl={cfl:.3f}: PASS in {wall:.3f}s; "
            f"outer_steps={solver.last_timing.final_cycle_outer_steps}",
            flush=True,
        )

    coarse_medium = _field_difference(solutions[0], solutions[1])
    medium_fine = _field_difference(solutions[1], solutions[2])
    observed = {}
    for field in coarse_medium:
        e1 = coarse_medium[field]
        e2 = medium_fine[field]
        if e1 <= 1e-14 and e2 <= 1e-14:
            order = float("inf")
        elif e2 <= 0.0:
            order = float("inf")
        else:
            order = float(math.log(e1 / e2, 2.0))
        observed[field] = order
        if not math.isfinite(order) and order != float("inf"):
            raise AssertionError(f"non-finite temporal order for {field}")
        if order < MIN_OBSERVED_ORDER:
            raise AssertionError(
                f"accelerated solver temporal order for {field} is {order:.4g}; "
                f"required >= {MIN_OBSERVED_ORDER}"
            )

    result = {
        "status": "PASS",
        "condition": "carotid_stenosis",
        "cfl_levels": list(CFL_LEVELS),
        "periodicity_tolerance": 1e-6,
        "minimum_observed_order_required": MIN_OBSERVED_ORDER,
        "coarse_medium_relative_l2": coarse_medium,
        "medium_fine_relative_l2": medium_fine,
        "observed_order": observed,
        "runs": runs,
    }
    payload["temporal_refinement"] = result
    main_report.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source, args.report)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
