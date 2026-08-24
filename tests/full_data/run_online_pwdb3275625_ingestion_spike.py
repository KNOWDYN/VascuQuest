"""Acquire the minimum canonical PWDB Tier-3 artifacts, then run Batch 8.

This repository validation tool intentionally uses VascuQuest's own canonical
ArtifactAcquirer. It is not production backend code and makes no range/resume
claim.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

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
        default=Path("pwdb3275625_ingestion_spike_report.json"),
    )
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    report = args.report.expanduser().resolve()
    paths = DataPaths.under(workspace)
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry)

    for artifact_id in REQUIRED:
        path = acquirer.acquire(artifact_id, offline=False)
        print(f"{artifact_id}: {path}", flush=True)

    spike = Path(__file__).with_name("pwdb3275625_ingestion_spike.py")
    completed = subprocess.run(
        [
            sys.executable,
            str(spike),
            str(paths.source),
            "--report",
            str(report),
        ],
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
