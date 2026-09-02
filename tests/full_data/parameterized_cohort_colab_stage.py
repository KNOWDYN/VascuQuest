"""Prepare the exact PWDB artifacts needed by manual cohort qualification.

The manual Colab route must never recursively scan mounted Google Drive. It checks
only one explicitly configured PWDB directory for the three required canonical
files. Existing Drive files are copied once to local SSD and checksum-verified
there. Missing or invalid files are acquired through VascuQuest's canonical
artifact acquisition layer and verified against the bundled manifest.
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


def prepare(
    drive_source_dir: Path,
    local_source: Path,
    report_path: Path,
) -> list[dict[str, object]]:
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

        # Fast path: a previously staged local-SSD artifact is already valid.
        if destination.exists() and digest(destination, algorithm) == expected:
            source_kind = "reused_verified_local_ssd"
            source_path = destination
        else:
            destination.unlink(missing_ok=True)
            drive_candidate = drive_source_dir / artifact.filename

            # Read a Drive artifact only once: copy it first, then checksum locally.
            if drive_candidate.is_file():
                print(
                    f"{artifact_id}: copying exact Drive file {drive_candidate.name} to SSD...",
                    flush=True,
                )
                copy_atomic(drive_candidate, destination)
                observed = digest(destination, algorithm)
                if observed == expected:
                    source_kind = "verified_drive_copy"
                    source_path = drive_candidate
                else:
                    print(
                        f"{artifact_id}: Drive copy checksum mismatch; "
                        "falling back to canonical acquisition.",
                        flush=True,
                    )
                    destination.unlink(missing_ok=True)
                    acquired = acquirer.acquire(artifact_id, offline=False)
                    inspection = verify_artifact(acquired, artifact)
                    if inspection.state.value != "verified":
                        raise RuntimeError(
                            f"canonical acquisition did not verify: {artifact.filename}"
                        )
                    if inspection.observed_checksum != expected:
                        raise RuntimeError(
                            f"canonical checksum mismatch: {artifact.filename}"
                        )
                    copy_atomic(acquired, destination)
                    source_kind = "canonical_online_acquisition_after_invalid_drive_copy"
                    source_path = acquired
            else:
                print(
                    f"{artifact_id}: {artifact.filename} not present in configured Drive "
                    "directory; acquiring canonical artifact...",
                    flush=True,
                )
                acquired = acquirer.acquire(artifact_id, offline=False)
                inspection = verify_artifact(acquired, artifact)
                if inspection.state.value != "verified":
                    raise RuntimeError(
                        f"canonical acquisition did not verify: {artifact.filename}"
                    )
                if inspection.observed_checksum != expected:
                    raise RuntimeError(
                        f"canonical checksum mismatch: {artifact.filename}"
                    )
                copy_atomic(acquired, destination)
                source_kind = "canonical_online_acquisition"
                source_path = acquired

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
            f"{artifact_id}: PASS -> {source_kind} -> {destination}",
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
    parser.add_argument("--drive-source-dir", type=Path, required=True)
    parser.add_argument("--local-source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(f"Configured Drive PWDB directory: {args.drive_source_dir}", flush=True)
    if not args.drive_source_dir.exists():
        print(
            "Configured Drive directory is not mounted/present; "
            "missing artifacts will be acquired canonically.",
            flush=True,
        )
    prepare(args.drive_source_dir, args.local_source, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
