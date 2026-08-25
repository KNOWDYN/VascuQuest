"""Tier-4 real-source validation for the core-only PWDB v1 release scope.

This release gate acquires the exact six canonical artifacts used by the core
backend, verifies checksums, validates exhaustive source identity/alignment,
performs deterministic representative geometry/waveform reads through the
public API, validates the shipped flow-rate reconstruction, and emits a JSON
report. Optional dense path support and alternate source representations remain
explicitly outside the claimed core scope.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sys
import time
import traceback
import zipfile

import numpy as np

import vascuquest as vq
from vascuquest.backends.pwdb3275625.capabilities import PWDB_MEASUREMENT_SITE_IDS
from vascuquest.backends.pwdb3275625.csv_reader import SubjectCSVTable
from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, verify_artifact
from vascuquest.domain import EvidenceClass, MeasurementSite
from vascuquest.methods import FLOW_RATE_RECONSTRUCTION_ID
from vascuquest.schema import load_canonical_schema, load_manifest


SUBJECT_IDS = tuple(str(index) for index in range(1, 4375))
AGES = (25, 35, 45, 55, 65, 75)
CORE_ARTIFACTS = (
    "model_configurations",
    "haemodynamic_parameters",
    "pulse_wave_indices",
    "onset_times",
    "geometry",
    "common_site_waveforms_csv",
)
SCALAR_ARTIFACTS = {
    "model_configurations": "model_configurations",
    "haemodynamic_parameters": "haemodynamic_parameters",
    "pulse_wave_indices": "pulse_wave_indices",
    "onset_times": "onset_times",
}
CAPABILITIES = frozenset(
    {
        "subject_model_configuration",
        "haemodynamic_parameters",
        "pulse_wave_indices",
        "onset_times",
        "geometry",
        "common_site_waveforms:csv",
    }
)
LOCATION_FREE_SCALARS = (
    "age",
    "heart_rate",
    "stroke_volume",
    "cardiac_output",
    "aortic_pulse_wave_velocity",
)
FIXED_SITE_SCALARS = {
    "brachial_systolic_pressure": "Brachial",
    "aortic_augmentation_index": "AorticRoot",
}
SOURCE_SIGNALS = ("P", "U", "A", "PPG")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def acquire_core(acquirer: ArtifactAcquirer, manifest: object):
    paths: dict[str, Path] = {}
    records: list[dict[str, object]] = []
    for artifact_id in CORE_ARTIFACTS:
        started = time.monotonic()
        path = acquirer.acquire(artifact_id, offline=False)
        artifact = manifest.artifact(artifact_id)
        inspection = verify_artifact(path, artifact)
        require(inspection.state.value == "verified", f"{artifact_id} is not verified")
        require(
            inspection.observed_checksum == artifact.checksum_value,
            f"{artifact_id} checksum mismatch",
        )
        paths[artifact_id] = path
        records.append(
            {
                "artifact_id": artifact_id,
                "filename": artifact.filename,
                "checksum_algorithm": artifact.checksum_algorithm,
                "expected_checksum": artifact.checksum_value,
                "observed_checksum": inspection.observed_checksum,
                "size_bytes": inspection.size_bytes,
                "acquire_and_verify_seconds": round(time.monotonic() - started, 6),
            }
        )
    return paths, records


def validate_scalar_sources(paths: dict[str, Path], schema: object):
    tables = {
        scope: SubjectCSVTable(paths[artifact_id])
        for scope, artifact_id in SCALAR_ARTIFACTS.items()
    }
    table_summary: dict[str, object] = {}
    for scope, table in tables.items():
        require(
            table.subject_ids() == SUBJECT_IDS,
            f"{scope} subject sequence is not exactly 1..4374",
        )
        table_summary[scope] = {
            "subjects": len(table.subject_ids()),
            "fields": len(table.fieldnames),
        }

    mappings = 0
    for quantity in schema.quantities:
        for mapping in quantity.source_mappings:
            table = tables.get(mapping.source_scope)
            if table is not None:
                require(
                    table.has_field(mapping.source_field),
                    f"missing mapped field {mapping.source_scope}:{mapping.source_field}",
                )
                mappings += 1
    require(mappings > 0, "no scalar schema mappings were checked")

    groups: dict[int, list[str]] = {age: [] for age in AGES}
    model = tables["model_configurations"]
    for subject_id in SUBJECT_IDS:
        cell = model.numeric(subject_id, "age [years]")
        require(not cell.missing and cell.value is not None, f"missing age for {subject_id}")
        age = int(cell.value)
        require(float(age) == cell.value and age in groups, f"invalid age for {subject_id}")
        groups[age].append(subject_id)
    for age, subject_ids in groups.items():
        require(len(subject_ids) == 729, f"age {age} has {len(subject_ids)} subjects")

    return groups, {
        "source_tables": table_summary,
        "schema_scalar_mappings_checked": mappings,
        "age_group_counts": {str(age): len(ids) for age, ids in groups.items()},
    }


def stratified_subjects(groups: dict[int, list[str]]) -> tuple[str, ...]:
    selected: list[str] = []
    for age in AGES:
        group = groups[age]
        selected.extend((group[0], group[len(group) // 2], group[-1]))
    require(len(selected) == 18 and len(set(selected)) == 18, "invalid geometry sample")
    return tuple(selected)


def validate_geometry(path: Path, session: object, sample: tuple[str, ...]):
    with zipfile.ZipFile(path, "r") as archive:
        names = {
            PurePosixPath(info.filename).name
            for info in archive.infolist()
            if not info.is_dir()
        }
    expected = {f"pwdb_geo_{index:04d}.csv" for index in range(1, 4375)}
    observed = {name for name in names if name.startswith("pwdb_geo_") and name.endswith(".csv")}
    require(observed == expected, "geometry archive inventory is not exactly 1..4374")

    counts: dict[str, int] = {}
    for subject_id in sample:
        result = session.geometry(subject=subject_id)
        require(result.quantity.canonical_name == "vascular_geometry", "geometry identity mismatch")
        require(result.evidence is EvidenceClass.SOURCE, "geometry evidence is not SOURCE")
        require(result.subject is not None and result.subject.canonical_subject_id == subject_id, "geometry subject mismatch")
        segments = tuple(result.values)
        require(segments, f"empty geometry for {subject_id}")
        require(len({item.segment_id for item in segments}) == len(segments), f"duplicate segment for {subject_id}")
        require(
            all(item.length_m > 0 and item.inlet_radius_m > 0 and item.outlet_radius_m > 0 for item in segments),
            f"non-positive geometry for {subject_id}",
        )
        counts[subject_id] = len(segments)
    return {"subject_members": 4374, "sampled_subjects": list(sample), "sampled_segment_counts": counts}


def validate_waveform_archive(path: Path):
    expected = {
        f"PWs_{site}_{signal}.csv"
        for site in PWDB_MEASUREMENT_SITE_IDS
        for signal in SOURCE_SIGNALS
    }
    samples: dict[str, int] = {}
    with zipfile.ZipFile(path, "r") as archive:
        members: dict[str, zipfile.ZipInfo] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename).name
            if name in expected:
                require(name not in members, f"ambiguous waveform member {name}")
                members[name] = info
        require(set(members) == expected, "common-site archive does not expose all 52 members")

        for name in sorted(expected):
            with archive.open(members[name], "r") as raw:
                reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), skipinitialspace=True)
                try:
                    header = tuple(value.strip() for value in next(reader))
                except StopIteration as exc:
                    raise AssertionError(f"empty waveform source {name}") from exc
                require(header and header[0] == "Subject Number", f"{name} lacks Subject Number")
                points = header[1:]
                require(points == tuple(f"pt{i}" for i in range(1, len(points) + 1)), f"{name} sample columns are non-canonical")
                row = 0
                for values in reader:
                    if not values or all(not value.strip() for value in values):
                        continue
                    require(len(values) == len(header), f"malformed waveform row in {name}")
                    require(row < 4374 and values[0].strip() == SUBJECT_IDS[row], f"subject alignment failure in {name} at row {row + 2}")
                    row += 1
                require(row == 4374, f"{name} contains {row} subjects")
                samples[name] = len(points)
    return {"declared_members": 52, "all_members_subject_aligned": True, "sample_columns_by_member": samples}


def validate_population_result(result: object, quantity: str) -> None:
    require(result.quantity.canonical_name == quantity, f"{quantity} identity mismatch")
    require(result.evidence is EvidenceClass.SOURCE, f"{quantity} evidence is not SOURCE")
    require(result.dimensions == ("subject",), f"{quantity} lacks subject dimension")
    require(len(result.coordinates) == 1 and result.coordinates[0].name == "subject", f"{quantity} subject coordinate missing")
    require(tuple(result.coordinates[0].values) == SUBJECT_IDS, f"{quantity} subject coordinate misaligned")
    require(len(tuple(result.values)) == 4374, f"{quantity} does not contain 4374 values")
    require(bool(result.provenance_ref), f"{quantity} lacks provenance")


def result_summary(result: object):
    values = tuple(result.values)
    return {
        "unit": result.canonical_unit,
        "evidence": result.evidence.value,
        "values": len(values),
        "missing": sum(value is None for value in values),
        "validity": result.validity.value,
    }


def validate_public_api(session: object, schema: object, groups: dict[int, list[str]]):
    require(session.capabilities() == CAPABILITIES, "public capability set differs from core scope")
    status = session.status()
    require(status.path_resolved_supported is False, "path-resolved support unexpectedly enabled")
    require(tuple(item.canonical_subject_id for item in session.subjects()) == SUBJECT_IDS, "public subject enumeration mismatch")
    sites = tuple(item.canonical_site_id for item in session.locations())
    require(sites == tuple(PWDB_MEASUREMENT_SITE_IDS), "public measurement-site inventory mismatch")

    scalar: dict[str, object] = {}
    for quantity in LOCATION_FREE_SCALARS:
        result = session.get(quantity)
        validate_population_result(result, quantity)
        scalar[quantity] = result_summary(result)
    for quantity, site in FIXED_SITE_SCALARS.items():
        result = session.get(quantity, location=MeasurementSite(site))
        validate_population_result(result, quantity)
        summary = result_summary(result)
        summary["measurement_site"] = site
        scalar[quantity] = summary

    onset: dict[str, object] = {}
    for site in PWDB_MEASUREMENT_SITE_IDS:
        result = session.get("pressure_onset_time", location=MeasurementSite(site))
        validate_population_result(result, "pressure_onset_time")
        onset[site] = result_summary(result)

    representative: list[dict[str, object]] = []
    sample_sites = ("AorticRoot", "Carotid", "Brachial", "Radial", "Femoral", "AntTibial")
    sample_signals = ("pressure", "flow_velocity", "luminal_area", "photoplethysmogram", "pressure", "flow_velocity")
    for age, site, signal in zip(AGES, sample_sites, sample_signals, strict=True):
        group = groups[age]
        subject = group[len(group) // 2]
        wave = session.waveform(signal, subject=subject, location=MeasurementSite(site))
        require(wave.quantity.canonical_name == signal, f"waveform identity mismatch for {signal}")
        require(wave.evidence is EvidenceClass.SOURCE, f"waveform evidence mismatch for {signal}")
        require(wave.subject is not None and wave.subject.canonical_subject_id == subject, "waveform subject mismatch")
        require(getattr(wave.location, "canonical_site_id", None) == site, "waveform site mismatch")
        values = np.asarray(wave.values, dtype=float)
        times = np.asarray(wave.time_coordinate.values, dtype=float)
        missing = np.asarray(wave.missing_mask, dtype=bool)
        padding = np.asarray(wave.padding_mask, dtype=bool)
        require(values.ndim == 1 and values.size > 0 and times.shape == values.shape, "invalid waveform shape")
        require(wave.time_coordinate.unit == "s", "waveform time unit mismatch")
        if times.size > 1:
            require(np.allclose(np.diff(times), 1 / 500, rtol=0, atol=1e-15), "waveform sampling is not 500 Hz")
        require(missing.shape == values.shape and padding.shape == values.shape, "waveform mask shape mismatch")
        require(not np.any(missing & padding), "waveform missing/padding masks overlap")
        representative.append({"age": age, "subject_id": subject, "site": site, "signal": signal, "samples": int(values.size), "missing": int(missing.sum()), "padding": int(padding.sum())})

    subject = groups[55][len(groups[55]) // 2]
    site = MeasurementSite("AorticRoot")
    velocity = session.waveform("flow_velocity", subject=subject, location=site)
    area = session.waveform("luminal_area", subject=subject, location=site)
    flow = session.derive(FLOW_RATE_RECONSTRUCTION_ID, subjects=subject, location=site)
    expected = np.asarray(velocity.values, dtype=float) * np.asarray(area.values, dtype=float)
    actual = np.asarray(flow.values, dtype=float)
    require(np.array_equal(actual, expected, equal_nan=True), "real-source Q differs from U*A")
    require(flow.evidence is EvidenceClass.RECONSTRUCTED, "flow-rate evidence mismatch")
    require(flow.canonical_unit == "m^3/s", "flow-rate unit mismatch")
    require(flow.method_id == FLOW_RATE_RECONSTRUCTION_ID, "flow-rate method identity mismatch")

    return {
        "capabilities": sorted(session.capabilities()),
        "path_resolved_supported": status.path_resolved_supported,
        "path_validation_state": status.path_validation_state,
        "subjects": 4374,
        "measurement_sites": list(sites),
        "scalar_results": scalar,
        "pressure_onset_time_by_site": onset,
        "representative_waveforms": representative,
        "flow_rate_reconstruction": {
            "subject_id": subject,
            "site": "AorticRoot",
            "samples": int(actual.size),
            "evidence": flow.evidence.value,
            "unit": flow.canonical_unit,
            "method_id": flow.method_id,
            "real_source_identity_check": "Q=U*A on parsed source arrays",
        },
        "schema_quantities": [item.definition.canonical_name for item in schema.quantities],
    }


def validate_licence(repo_root: Path):
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    licence = (repo_root / "LICENSE").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    require('license = "Apache-2.0"' in pyproject, "package licence metadata mismatch")
    require("Apache License" in licence and "Version 2.0" in licence, "LICENSE text mismatch")
    require("10.5281/zenodo.3275625" in readme, "README lacks dataset attribution")
    require("10.1152/ajpheart.00218.2019" in readme, "README lacks PWDB article attribution")
    require("does not relicense the source dataset" in readme, "README lacks dataset licence boundary")
    return {
        "software_licence": "Apache-2.0",
        "canonical_dataset_doi": "10.5281/zenodo.3275625",
        "authoritative_pwdb_article_doi": "10.1152/ajpheart.00218.2019",
        "dataset_relicensed_by_vascuquest": False,
    }


def run_validation(report_path: Path, code_revision: str, repo_root: Path):
    started = time.monotonic()
    manifest = load_manifest()
    schema = load_canonical_schema()
    data_paths = DataPaths.default()
    data_paths.ensure()
    registry = SourceRegistry(data_paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(data_paths, registry, manifest=manifest)
    report: dict[str, object] = {
        "validation_tier": 4,
        "validation_scope": "core PWDB v1",
        "status": "running",
        "code_revision": code_revision,
        "package_version": vq.__version__,
        "schema_version": schema.schema_version,
        "manifest_version": manifest.manifest_version,
        "canonical_record_id": manifest.canonical_record_id,
        "canonical_doi": manifest.canonical_doi,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "runner_os": os.environ.get("RUNNER_OS"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
        "package_versions": {name: importlib.metadata.version(name) for name in ("vascuquest", "numpy", "platformdirs", "typer")},
        "claimed_core_artifacts": list(CORE_ARTIFACTS),
        "explicitly_excluded_capabilities_or_sources": [
            "dense path-resolved waveforms (Batch 8/9 unpassed)",
            "path MAT artifacts and complete 44.3 GB PWDB validation",
            "MATLAB and WFDB alternate common-site representations",
            "unified pwdb_data.mat representation",
            "model_variations (mapped for future schema expansion but not advertised by core)",
            "plausibility metadata (not exposed or claimed by current core capability/schema)",
        ],
    }
    try:
        paths, artifacts = acquire_core(acquirer, manifest)
        groups, scalar = validate_scalar_sources(paths, schema)
        session = vq.open_dataset(source=data_paths.source, offline=True)
        report["artifacts"] = artifacts
        report["scalar_source_validation"] = scalar
        report["geometry_validation"] = validate_geometry(paths["geometry"], session, stratified_subjects(groups))
        report["waveform_archive_validation"] = validate_waveform_archive(paths["common_site_waveforms_csv"])
        report["public_api_and_science_validation"] = validate_public_api(session, schema, groups)
        report["licence_and_attribution"] = validate_licence(repo_root)
        report["status"] = "passed"
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = round(time.monotonic() - started, 6)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        report = run_validation(args.report, args.code_revision, args.repo_root.resolve())
    except Exception:
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
