"""Tier-4 real-source validation for the core-only PWDB v1 release scope.

This is not an ordinary CI test. It acquires the exact canonical artifacts used
by the shipped core backend, verifies their manifest checksums, validates the
full 4,374-subject source alignment, checks every declared common-site CSV
structure, exercises deterministic representative real-source geometry and
waveform reads through the public API, and emits a machine-readable report.

Dense path-resolved artifacts, MATLAB/WFDB alternate representations,
``model_variations``, and plausibility metadata are not claimed by core v1 and
are explicitly recorded as outside this validation scope.
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


EXPECTED_SUBJECT_IDS = tuple(str(index) for index in range(1, 4375))
EXPECTED_AGES = (25, 35, 45, 55, 65, 75)
CORE_ARTIFACT_IDS = (
    "model_configurations",
    "haemodynamic_parameters",
    "pulse_wave_indices",
    "onset_times",
    "geometry",
    "common_site_waveforms_csv",
)
SCALAR_SCOPE_ARTIFACT_IDS = {
    "model_configurations": "model_configurations",
    "haemodynamic_parameters": "haemodynamic_parameters",
    "pulse_wave_indices": "pulse_wave_indices",
    "onset_times": "onset_times",
}
EXPECTED_CAPABILITIES = frozenset(
    {
        "subject_model_configuration",
        "haemodynamic_parameters",
        "pulse_wave_indices",
        "onset_times",
        "geometry",
        "common_site_waveforms:csv",
    }
)
SOURCE_SIGNALS = ("P", "U", "A", "PPG")
CANONICAL_SIGNALS = {
    "P": "pressure",
    "U": "flow_velocity",
    "A": "luminal_area",
    "PPG": "photoplethysmogram",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _package_versions() -> dict[str, str]:
    names = ("vascuquest", "numpy", "platformdirs", "typer")
    return {name: importlib.metadata.version(name) for name in names}


def _artifact_inventory(
    *,
    acquirer: ArtifactAcquirer,
    manifest: object,
) -> tuple[dict[str, Path], list[dict[str, object]]]:
    paths: dict[str, Path] = {}
    records: list[dict[str, object]] = []
    for artifact_id in CORE_ARTIFACT_IDS:
        started = time.monotonic()
        path = acquirer.acquire(artifact_id, offline=False)
        artifact = manifest.artifact(artifact_id)
        inspection = verify_artifact(path, artifact)
        _require(inspection.state.value == "verified", f"{artifact_id} is not checksum-verified")
        _require(
            inspection.observed_checksum == artifact.checksum_value,
            f"{artifact_id} observed checksum does not match canonical manifest",
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


def _validate_scalar_sources(
    artifact_paths: dict[str, Path],
    schema: object,
) -> tuple[dict[str, SubjectCSVTable], dict[str, object]]:
    tables = {
        scope: SubjectCSVTable(artifact_paths[artifact_id])
        for scope, artifact_id in SCALAR_SCOPE_ARTIFACT_IDS.items()
    }
    source_rows: dict[str, object] = {}
    for scope, table in tables.items():
        subject_ids = table.subject_ids()
        _require(
            subject_ids == EXPECTED_SUBJECT_IDS,
            f"{scope} does not contain the exact canonical 1..4374 subject sequence",
        )
        source_rows[scope] = {
            "subjects": len(subject_ids),
            "fields": len(table.fieldnames),
        }

    checked_mappings = 0
    for quantity in schema.quantities:
        for mapping in quantity.source_mappings:
            table = tables.get(mapping.source_scope)
            if table is None:
                continue
            _require(
                table.has_field(mapping.source_field),
                f"schema field {mapping.source_field!r} is absent from {mapping.source_scope}",
            )
            checked_mappings += 1
    _require(checked_mappings > 0, "no scalar schema mappings were validated")

    model = tables["model_configurations"]
    age_groups: dict[int, list[str]] = {age: [] for age in EXPECTED_AGES}
    for subject_id in EXPECTED_SUBJECT_IDS:
        cell = model.numeric(subject_id, "age [years]")
        _require(not cell.missing and cell.value is not None, f"age missing for subject {subject_id}")
        age = int(cell.value)
        _require(float(age) == cell.value, f"non-integral source age for subject {subject_id}")
        _require(age in age_groups, f"unexpected source age {age} for subject {subject_id}")
        age_groups[age].append(subject_id)
    for age, subject_ids in age_groups.items():
        _require(
            len(subject_ids) == 729,
            f"age {age} must contain the canonical 729 virtual subjects, found {len(subject_ids)}",
        )

    return tables, {
        "source_tables": source_rows,
        "schema_scalar_mappings_checked": checked_mappings,
        "age_group_counts": {str(age): len(ids) for age, ids in age_groups.items()},
        "age_groups": age_groups,
    }


def _stratified_subjects(age_groups: dict[int, list[str]]) -> tuple[str, ...]:
    selected: list[str] = []
    for age in EXPECTED_AGES:
        group = age_groups[age]
        selected.extend((group[0], group[len(group) // 2], group[-1]))
    _require(len(selected) == 18 and len(set(selected)) == 18, "invalid deterministic age/configuration sample")
    return tuple(selected)


def _zip_member_map(path: Path) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    with zipfile.ZipFile(path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = PurePosixPath(info.filename).name
            _require(basename not in members, f"ambiguous ZIP basename {basename!r}")
            members[basename] = info
    return members


def _validate_geometry(
    *,
    geometry_path: Path,
    session: object,
    sampled_subjects: tuple[str, ...],
) -> dict[str, object]:
    members = _zip_member_map(geometry_path)
    expected = {f"pwdb_geo_{index:04d}.csv" for index in range(1, 4375)}
    observed = {name for name in members if name.startswith("pwdb_geo_") and name.endswith(".csv")}
    _require(observed == expected, "geometry archive subject inventory is not exactly 1..4374")

    counts: dict[str, int] = {}
    for subject_id in sampled_subjects:
        result = session.geometry(subject=subject_id)
        _require(result.quantity.canonical_name == "vascular_geometry", "wrong geometry quantity identity")
        _require(result.evidence is EvidenceClass.SOURCE, "geometry must remain SOURCE evidence")
        _require(result.subject is not None and result.subject.canonical_subject_id == subject_id, "geometry subject mismatch")
        segments = tuple(result.values)
        _require(segments, f"geometry is empty for subject {subject_id}")
        _require(len({segment.segment_id for segment in segments}) == len(segments), f"duplicate geometry segment for {subject_id}")
        _require(
            all(segment.length_m > 0 and segment.inlet_radius_m > 0 and segment.outlet_radius_m > 0 for segment in segments),
            f"non-positive source geometry length/radius for {subject_id}",
        )
        counts[subject_id] = len(segments)

    return {
        "subject_members": len(observed),
        "sampled_subjects": list(sampled_subjects),
        "sampled_segment_counts": counts,
    }


def _validate_waveform_archive(
    waveform_path: Path,
) -> dict[str, object]:
    expected_names = {
        f"PWs_{site}_{signal}.csv"
        for site in PWDB_MEASUREMENT_SITE_IDS
        for signal in SOURCE_SIGNALS
    }
    structures: dict[str, int] = {}
    with zipfile.ZipFile(waveform_path, "r") as archive:
        by_name: dict[str, zipfile.ZipInfo] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            basename = PurePosixPath(info.filename).name
            if basename in expected_names:
                _require(basename not in by_name, f"ambiguous waveform ZIP member {basename!r}")
                by_name[basename] = info
        _require(set(by_name) == expected_names, "common-site waveform archive does not expose all declared site/signal members")

        for basename in sorted(expected_names):
            info = by_name[basename]
            with archive.open(info, "r") as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                reader = csv.reader(text, skipinitialspace=True)
                try:
                    header = tuple(value.strip() for value in next(reader))
                except StopIteration as exc:
                    raise AssertionError(f"waveform source {basename!r} is empty") from exc
                _require(header and header[0] == "Subject Number", f"{basename} lacks Subject Number")
                sample_fields = header[1:]
                _require(sample_fields, f"{basename} has no waveform samples")
                _require(
                    sample_fields == tuple(f"pt{index}" for index in range(1, len(sample_fields) + 1)),
                    f"{basename} has non-canonical sample columns",
                )

                row_index = 0
                for values in reader:
                    if not values or all(not value.strip() for value in values):
                        continue
                    _require(len(values) == len(header), f"{basename} contains a malformed row")
                    _require(row_index < len(EXPECTED_SUBJECT_IDS), f"{basename} has more than 4374 subject rows")
                    subject_id = values[0].strip()
                    _require(
                        subject_id == EXPECTED_SUBJECT_IDS[row_index],
                        f"{basename} subject alignment fails at row {row_index + 2}: {subject_id!r}",
                    )
                    row_index += 1
                _require(row_index == 4374, f"{basename} contains {row_index} subjects instead of 4374")
                structures[basename] = len(sample_fields)

    return {
        "declared_members": len(expected_names),
        "all_members_subject_aligned": True,
        "sample_columns_by_member": structures,
    }


def _validate_public_api(
    *,
    session: object,
    schema: object,
    age_groups: dict[int, list[str]],
) -> dict[str, object]:
    _require(session.capabilities() == EXPECTED_CAPABILITIES, "public core capability set differs from release scope")
    status = session.status()
    _require(status.path_resolved_supported is False, "path-resolved support must remain unavailable in core-only release")
    _require(
        tuple(subject.canonical_subject_id for subject in session.subjects()) == EXPECTED_SUBJECT_IDS,
        "public subject enumeration is not exactly 1..4374",
    )
    location_ids = tuple(location.canonical_site_id for location in session.locations())
    _require(location_ids == tuple(PWDB_MEASUREMENT_SITE_IDS), "public measurement-site inventory mismatch")

    scalar_results: dict[str, object] = {}
    location_free = (
        "age",
        "heart_rate",
        "stroke_volume",
        "cardiac_output",
        "brachial_systolic_pressure",
        "aortic_pulse_wave_velocity",
        "aortic_augmentation_index",
    )
    for quantity_name in location_free:
        result = session.get(quantity_name)
        _validate_full_subject_result(result, quantity_name)
        scalar_results[quantity_name] = _result_summary(result)

    onset_results: dict[str, object] = {}
    for site_id in PWDB_MEASUREMENT_SITE_IDS:
        result = session.get("pressure_onset_time", location=MeasurementSite(site_id))
        _validate_full_subject_result(result, "pressure_onset_time")
        onset_results[site_id] = _result_summary(result)

    representative: list[dict[str, object]] = []
    sites = ("AorticRoot", "Carotid", "Brachial", "Radial", "Femoral", "AntTibial")
    signals = ("pressure", "flow_velocity", "luminal_area", "photoplethysmogram", "pressure", "flow_velocity")
    for age, site_id, signal in zip(EXPECTED_AGES, sites, signals, strict=True):
        group = age_groups[age]
        subject_id = group[len(group) // 2]
        waveform = session.waveform(signal, subject=subject_id, location=MeasurementSite(site_id))
        _require(waveform.quantity.canonical_name == signal, f"waveform quantity mismatch for {signal}")
        _require(waveform.evidence is EvidenceClass.SOURCE, f"{signal} waveform must remain SOURCE")
        _require(waveform.subject is not None and waveform.subject.canonical_subject_id == subject_id, "waveform subject mismatch")
        _require(getattr(waveform.location, "canonical_site_id", None) == site_id, "waveform site mismatch")
        values = np.asarray(waveform.values, dtype=float)
        times = np.asarray(waveform.time_coordinate.values, dtype=float)
        _require(values.ndim == 1 and values.size > 0, "waveform values must be a non-empty vector")
        _require(times.shape == values.shape, "waveform time/value shape mismatch")
        _require(waveform.time_coordinate.unit == "s", "waveform time coordinate must use seconds")
        if times.size > 1:
            _require(np.allclose(np.diff(times), 1.0 / 500.0, rtol=0.0, atol=1e-15), "waveform time spacing is not 500 Hz")
        missing = np.asarray(waveform.missing_mask, dtype=bool)
        padding = np.asarray(waveform.padding_mask, dtype=bool)
        _require(missing.shape == values.shape and padding.shape == values.shape, "waveform masks do not match values")
        _require(not np.any(missing & padding), "waveform missing/padding masks overlap")
        representative.append(
            {
                "age": age,
                "subject_id": subject_id,
                "site": site_id,
                "signal": signal,
                "samples": int(values.size),
                "missing": int(missing.sum()),
                "padding": int(padding.sum()),
            }
        )

    reconstruction_subject = age_groups[55][len(age_groups[55]) // 2]
    reconstruction_site = MeasurementSite("AorticRoot")
    velocity = session.waveform("flow_velocity", subject=reconstruction_subject, location=reconstruction_site)
    area = session.waveform("luminal_area", subject=reconstruction_subject, location=reconstruction_site)
    flow_rate = session.derive(
        FLOW_RATE_RECONSTRUCTION_ID,
        subjects=reconstruction_subject,
        location=reconstruction_site,
    )
    expected = np.asarray(velocity.values, dtype=float) * np.asarray(area.values, dtype=float)
    actual = np.asarray(flow_rate.values, dtype=float)
    _require(np.array_equal(actual, expected, equal_nan=True), "real-source flow-rate reconstruction differs from Q=U*A")
    _require(flow_rate.evidence is EvidenceClass.RECONSTRUCTED, "flow-rate reconstruction evidence must be RECONSTRUCTED")
    _require(flow_rate.canonical_unit == "m^3/s", "flow-rate reconstruction unit mismatch")
    _require(flow_rate.method_id == FLOW_RATE_RECONSTRUCTION_ID, "flow-rate reconstruction method identity mismatch")

    return {
        "capabilities": sorted(session.capabilities()),
        "path_resolved_supported": status.path_resolved_supported,
        "path_validation_state": status.path_validation_state,
        "subjects": 4374,
        "measurement_sites": list(location_ids),
        "scalar_results": scalar_results,
        "pressure_onset_time_by_site": onset_results,
        "representative_waveforms": representative,
        "flow_rate_reconstruction": {
            "subject_id": reconstruction_subject,
            "site": "AorticRoot",
            "samples": int(actual.size),
            "evidence": flow_rate.evidence.value,
            "unit": flow_rate.canonical_unit,
            "method_id": flow_rate.method_id,
            "real_source_identity_check": "Q=U*A exact floating-point operation on parsed source arrays",
        },
        "schema_quantities": [quantity.canonical_name for quantity in schema.quantities],
    }


def _validate_full_subject_result(result: object, quantity_name: str) -> None:
    _require(result.quantity.canonical_name == quantity_name, f"quantity identity mismatch for {quantity_name}")
    _require(result.evidence is EvidenceClass.SOURCE, f"{quantity_name} must remain SOURCE evidence")
    _require(result.dimensions == ("subject",), f"{quantity_name} must return a subject axis")
    _require(len(result.coordinates) == 1 and result.coordinates[0].name == "subject", f"{quantity_name} subject coordinate missing")
    _require(tuple(result.coordinates[0].values) == EXPECTED_SUBJECT_IDS, f"{quantity_name} subject coordinate misaligned")
    _require(len(tuple(result.values)) == 4374, f"{quantity_name} result does not contain 4374 values")
    _require(bool(result.provenance_ref), f"{quantity_name} has no provenance reference")


def _result_summary(result: object) -> dict[str, object]:
    values = tuple(result.values)
    missing = sum(value is None for value in values)
    return {
        "unit": result.canonical_unit,
        "evidence": result.evidence.value,
        "values": len(values),
        "missing": missing,
        "validity": result.validity.value,
    }


def _validate_licence_and_attribution(repo_root: Path) -> dict[str, object]:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    _require('license = "Apache-2.0"' in pyproject, "package metadata is not Apache-2.0")
    _require("Apache License" in license_text and "Version 2.0" in license_text, "LICENSE is not Apache-2.0 text")
    _require("10.5281/zenodo.3275625" in readme, "README lacks canonical dataset attribution")
    _require("10.1152/ajpheart.00218.2019" in readme, "README lacks authoritative PWDB article attribution")
    _require("does not relicense the source dataset" in readme, "README does not preserve the external dataset licence boundary")
    return {
        "software_licence": "Apache-2.0",
        "canonical_dataset_doi": "10.5281/zenodo.3275625",
        "authoritative_pwdb_article_doi": "10.1152/ajpheart.00218.2019",
        "dataset_relicensed_by_vascuquest": False,
    }


def run_validation(*, report_path: Path, code_revision: str, repo_root: Path) -> dict[str, object]:
    started = time.monotonic()
    manifest = load_manifest()
    schema = load_canonical_schema()
    paths = DataPaths.default()
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    acquirer = ArtifactAcquirer(paths, registry, manifest=manifest)

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
        "package_versions": _package_versions(),
        "claimed_core_artifacts": list(CORE_ARTIFACT_IDS),
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
        artifact_paths, artifact_records = _artifact_inventory(acquirer=acquirer, manifest=manifest)
        tables, scalar = _validate_scalar_sources(artifact_paths, schema)
        del tables
        age_groups = scalar.pop("age_groups")
        sampled_subjects = _stratified_subjects(age_groups)

        session = vq.open_dataset(source=paths.source, offline=True)
        report["artifacts"] = artifact_records
        report["scalar_source_validation"] = scalar
        report["geometry_validation"] = _validate_geometry(
            geometry_path=artifact_paths["geometry"],
            session=session,
            sampled_subjects=sampled_subjects,
        )
        report["waveform_archive_validation"] = _validate_waveform_archive(
            artifact_paths["common_site_waveforms_csv"]
        )
        report["public_api_and_science_validation"] = _validate_public_api(
            session=session,
            schema=schema,
            age_groups=age_groups,
        )
        report["licence_and_attribution"] = _validate_licence_and_attribution(repo_root)
        report["status"] = "passed"
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["failure"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
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
        report = run_validation(
            report_path=args.report,
            code_revision=args.code_revision,
            repo_root=args.repo_root.resolve(),
        )
    except Exception:
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.report)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
