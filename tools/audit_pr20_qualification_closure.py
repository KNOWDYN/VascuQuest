#!/usr/bin/env python3
"""Zero-compute audit for the PR #20 qualification closure.

This script performs Git-history and JSON consistency checks only. It deliberately
imports no VascuQuest numerical modules, JAX, NumPy, or PWDB data readers and does
not execute any solver.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

FROZEN_PRODUCTION_REVISION = "d68708aab538003c29ae619417cdaf8345fc2b93"
TRUSTED_EXECUTION_EVIDENCE_REVISION = "19c6a24d5ec571946440927344801d3a0a40e78d"
CERTIFICATE_PATH = Path("docs/evidence/JAX_SCALAR_QUALIFICATION.json")
HEAVY_WORKFLOW_PATH = Path(".github/workflows/parameterized-cohort-release-validation.yml")

PROTECTED_NUMERICAL_SCIENTIFIC_PATHS = (
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

ALLOWED_CLOSURE_PATHS = {
    ".github/workflows/parameterized-cohort-release-validation.yml",
    "docs/PARAMETERIZED_COHORT_QUALIFICATION.md",
    "docs/evidence/JAX_SCALAR_QUALIFICATION.json",
    "tools/audit_pr20_qualification_closure.py",
}


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def _assert_commit(repo: Path, revision: str) -> None:
    _git(repo, "cat-file", "-e", f"{revision}^{{commit}}")


def _changed(repo: Path, base: str, head: str, paths: tuple[str, ...] | None = None) -> list[str]:
    args = ["diff", "--name-only", base, head]
    if paths:
        args.extend(["--", *paths])
    return [line for line in _git(repo, *args).splitlines() if line]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def audit() -> None:
    repo = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel"))
    head = _git(repo, "rev-parse", "HEAD")

    _assert_commit(repo, FROZEN_PRODUCTION_REVISION)
    _assert_commit(repo, TRUSTED_EXECUTION_EVIDENCE_REVISION)

    lineage_changes = _changed(
        repo,
        TRUSTED_EXECUTION_EVIDENCE_REVISION,
        FROZEN_PRODUCTION_REVISION,
        PROTECTED_NUMERICAL_SCIENTIFIC_PATHS,
    )
    _require(
        not lineage_changes,
        "retained execution evidence crosses protected numerical/scientific changes: "
        + ", ".join(lineage_changes),
    )

    production_changes = _changed(
        repo,
        FROZEN_PRODUCTION_REVISION,
        head,
        ("src", "pyproject.toml"),
    )
    _require(
        not production_changes,
        "qualification closure changed production source/package metadata: "
        + ", ".join(production_changes),
    )

    closure_changes = set(_changed(repo, FROZEN_PRODUCTION_REVISION, head))
    unexpected = closure_changes - ALLOWED_CLOSURE_PATHS
    _require(
        not unexpected,
        "qualification closure contains unexpected paths: " + ", ".join(sorted(unexpected)),
    )
    _require(
        "docs/PARAMETERIZED_COHORT_QUALIFICATION.md" in closure_changes,
        "qualification contract was not rewritten",
    )
    _require(
        "docs/evidence/JAX_SCALAR_QUALIFICATION.json" in closure_changes,
        "machine-readable qualification certificate is missing from the closure diff",
    )
    _require(
        ".github/workflows/parameterized-cohort-release-validation.yml" in closure_changes,
        "heavy qualification workflow was not retired in the closure diff",
    )

    certificate_file = repo / CERTIFICATE_PATH
    _require(certificate_file.is_file(), f"missing certificate: {CERTIFICATE_PATH}")
    certificate = json.loads(certificate_file.read_text(encoding="utf-8"))
    _require(certificate.get("status") == "PASS", "certificate status is not PASS")
    _require(
        certificate.get("frozen_production_revision") == FROZEN_PRODUCTION_REVISION,
        "certificate frozen production revision mismatch",
    )
    _require(
        certificate.get("trusted_execution_evidence_revision")
        == TRUSTED_EXECUTION_EVIDENCE_REVISION,
        "certificate trusted evidence revision mismatch",
    )
    _require(
        certificate.get("scientific_boundary", {}).get("clinical_validation") is False,
        "certificate must not claim clinical validation",
    )
    _require(
        "empirical_full_network_temporal_order_greater_than_or_equal_to_1_5"
        in certificate.get("not_claimed", []),
        "certificate must explicitly exclude the unexecuted full-network temporal-order claim",
    )
    _require(
        not (repo / HEAVY_WORKFLOW_PATH).exists(),
        "superseded heavy qualification workflow still exists",
    )

    print("VascuQuest PR #20 qualification closure audit: PASS")
    print(f"frozen production revision: {FROZEN_PRODUCTION_REVISION}")
    print(f"trusted execution evidence revision: {TRUSTED_EXECUTION_EVIDENCE_REVISION}")
    print(f"closure HEAD: {head}")
    print("protected numerical/scientific lineage changes: 0")
    print("production source/package changes after freeze: 0")
    print("new numerical execution performed by this audit: 0")


def main() -> int:
    try:
        audit()
    except Exception as exc:
        print(f"VascuQuest PR #20 qualification closure audit: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
