"""Prepare the exact PWDB artifacts needed by manual cohort qualification.

Use verified files already present anywhere below the mounted Drive search root when
available. Missing artifacts are acquired through VascuQuest's canonical artifact
acquisition layer, verified against the bundled manifest, and copied to local SSD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.schema import load_manifest


REQUIRED_ARTIFACT_IDS = (
    "model_configurations",
    "geometry",
    "common_site_waveforms_csv",
)


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    temporary.unlink(missing_ok=True)
    with source.open("rb") as src, temporary.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
    temporary.replace(destination)


def valid_drive_matches(root: Path, filename: str, algorithm: str, expected: str) -> list[Path]:
    if not root.exists():
        return []
    matches = []
    for path in root.rglob(filename):
        if path.is_file() and digest(path, algorithm) == expected:
            matches.append(path)
    return matches


def prepare(drive_search_root: Path, local_source: Path, report_path: Path) -> list[dict[str, object]]:
    manifest = load_manifest()
    paths = DataPaths.default()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry)
    local_source.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for artifact_id in REQUIRED_ARTIFACT_IDS:
        artifact = manifest.artifact(artifact_id)
        expected = artifact.checksum_value
        algorithm = artifact.checksum_algorithm
        destination = local_source / artifact.filename

        if destination.exists() and digest(destination, algorithm) == expected:
            source_kind = "reused_verified_local_ssd"
            source_path = destination
        else:
            matches = valid_drive_matches(
                drive_search_root,
                artifact.filename,
                algorithm,
                expected,
            )
            if len(matches) > 1:
                raise RuntimeError(
                    f"multiple checksum-valid Drive copies found for {artifact.filename}: {matches}"
                )
            if len(matches) == 1:
                source_path = matches[0]
                copy_atomic(source_path, destination)
                source_kind = "verified_drive_copy"
            else:
                acquired = acquirer.acquire(artifact_id, offline=False)
                inspection = verify_artifact(acquired, artifact)
                if inspection.state.value != "verified":
                    raise RuntimeError(f"canonical acquisition did not verify: {artifact.filename}")
                if inspection.observed_checksum != expected:
                    raise RuntimeError(f"canonical checksum mismatch: {artifact.filename}")
                source_path = acquired
                copy_atomic(source_path, destination)
                source_kind = "canonical_online_acquisition"

        observed = digest(destination, algorithm)
        if observed != expected:
            raise RuntimeError(f"local SSD checksum mismatch for {artifact.filename}")

        record = {
            "artifact_id": artifact_id,
            "filename": artifact.filename,
            "bytes": destination.stat().st_size,
            "checksum_algorithm": algorithm,
            "checksum": observed,
            "source_kind": source_kind,
            "source_path": str(source_path),
            "local_path": str(destination),
        }
        records.append(record)
        print(
            f"{artifact_id}: {artifact.filename} -> {source_kind} -> {destination}",
            flush=True,
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drive-search-root", type=Path, required=True)
    parser.add_argument("--local-source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.drive_search_root, args.local_source, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
