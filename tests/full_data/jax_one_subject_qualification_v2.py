"""Run the one-subject JAX qualification with the production bounded-replay backend."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback

import jax_one_subject_qualification as qualification
from vascuquest.disease.solver.jax_disease_v2 import JaxDiseaseOneDSolver

# Reuse the established real-PWDB operator/full-solution qualification contract,
# replacing only the full JAX solver implementation under test. The operator
# snapshot remains the shared frozen JAX numerical operator from jax_disease.
qualification.JaxDiseaseOneDSolver = JaxDiseaseOneDSolver


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    try:
        qualification.qualify(args.source, args.report, args.code_revision)
    except Exception as exc:
        if args.report.exists():
            try:
                payload = json.loads(args.report.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        else:
            payload = {}
        payload.update(
            {
                "format": "vascuquest-jax-one-subject-qualification",
                "format_version": 1,
                "status": "FAIL",
                "code_revision": args.code_revision,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        payload.setdefault(
            "scientific_boundary",
            {"evidence": "MODELLED", "clinical_validation": False},
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
