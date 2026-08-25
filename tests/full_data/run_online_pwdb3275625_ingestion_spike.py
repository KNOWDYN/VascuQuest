"""Acquire the minimum canonical PWDB Tier-3 artifacts, then run Batch 8.

This validation runner intentionally uses VascuQuest's production acquisition
layer.  It is not production backend code and does not claim HTTP range/resume.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry  # noqa: E402

REQUIRED = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
    "common_site_waveforms_wfdb",
    "unified_matlab",
    "path_aorta_foot_p",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "workspace",
        type=Path,
        help="Persistent workspace for canonical source/work/state directories.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("pwdb3275625-tier3-report.json"),
    )
    parser.add_argument("--code-revision", default=None)
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    report = args.report.expanduser().resolve()
    paths = DataPaths.under(workspace)
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry)

    for artifact_id in REQUIRED:
        started = time.perf_counter()
        path = acquirer.acquire(artifact_id, offline=False)
        elapsed = time.perf_counter() - started
        print(
            f"acquired {artifact_id}: {path} "
            f"({path.stat().st_size} bytes, {elapsed:.3f} s)",
            flush=True,
        )

    spike = Path(__file__).with_name("pwdb3275625_ingestion_spike_corrected.py")
    command = [
        sys.executable,
        str(spike),
        str(paths.source),
        "--report",
        str(report),
    ]
    if args.code_revision:
        command.extend(["--code-revision", args.code_revision])
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
