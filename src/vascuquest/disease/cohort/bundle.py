"""Persistent plans and streaming bundles for parameterized disease cohorts."""

from __future__ import annotations

from dataclasses import asdict
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from collections.abc import Mapping

import numpy as np

from vascuquest.disease.runtime.materialize import RuntimeSubjectState
from vascuquest.errors import CapabilityError, IntegrityError
from vascuquest.exporters.json_exporter import JSONResultExporter
from vascuquest.provenance import provenance_to_json

from .model import DiseaseCohortAssignment, ParameterizedDiseaseCohortPlan

_COHORT_BUNDLE_FORMAT = "vascuquest-parameterized-disease-cohort-bundle"
_COHORT_BUNDLE_VERSION = 1
_QUALIFICATION_STATE = "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"


def _json_text(payload: Mapping[str, object]) -> str:
    return json.dumps(
        dict(payload),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(_json_text(payload), encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _identity(identity: object) -> dict[str, str]:
    return {
        "dataset_family": str(getattr(identity, "dataset_family")),
        "record_id": str(getattr(identity, "record_id")),
        "persistent_identifier": str(getattr(identity, "persistent_identifier")),
        "schema_version": str(getattr(identity, "schema_version")),
    }


def write_cohort_plan(
    plan: ParameterizedDiseaseCohortPlan,
    destination: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> Path:
    if not isinstance(plan, ParameterizedDiseaseCohortPlan):
        raise TypeError("plan must be a ParameterizedDiseaseCohortPlan")
    path = Path(destination).expanduser()
    if path.exists() and not overwrite:
        raise CapabilityError(f"cohort plan already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(_json_text(plan.to_dict()), encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    return path


def read_cohort_plan(source: str | os.PathLike[str]) -> ParameterizedDiseaseCohortPlan:
    path = Path(source).expanduser()
    if not path.exists() or not path.is_file():
        raise CapabilityError(f"cohort plan does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ParameterizedDiseaseCohortPlan.from_dict(payload)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"invalid parameterized disease cohort plan: {path}") from exc


def _assignment_rows(plan: ParameterizedDiseaseCohortPlan) -> list[dict[str, object]]:
    return [item.to_dict() for item in plan.assignments]


def _write_assignments(root: Path, plan: ParameterizedDiseaseCohortPlan) -> dict[str, str]:
    json_path = root / "assignments.json"
    csv_path = root / "assignments.csv"
    _write_json(json_path, {"assignments": _assignment_rows(plan)})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "canonical_subject_id",
                "age_years",
                "condition",
                "severity_parameter",
                "severity_value",
                "parameters_json",
                "preset_version",
            ),
        )
        writer.writeheader()
        for item in plan.assignments:
            writer.writerow(
                {
                    "canonical_subject_id": item.canonical_subject_id,
                    "age_years": item.age_years,
                    "condition": item.specification.condition.value,
                    "severity_parameter": item.severity_parameter,
                    "severity_value": format(item.severity_value, ".17g"),
                    "parameters_json": json.dumps(
                        dict(item.specification.parameters),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "preset_version": item.specification.preset_version,
                }
            )
    return {
        "assignments.json": _sha256(json_path),
        "assignments.csv": _sha256(csv_path),
    }


def _append_log(root: Path, message: str) -> None:
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / "run.log").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(message.rstrip() + "\n")


def _append_error(root: Path, payload: Mapping[str, object]) -> None:
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    with (logs / "errors.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True, ensure_ascii=False) + "\n")


class ParameterizedDiseaseCohortBundleWriter:
    """Atomically persist one subject at a time and support deterministic resume."""

    def __init__(
        self,
        destination: str | os.PathLike[str],
        plan: ParameterizedDiseaseCohortPlan,
        runtime_identity: object,
        *,
        resume: bool = False,
    ) -> None:
        if not isinstance(plan, ParameterizedDiseaseCohortPlan):
            raise TypeError("plan must be a ParameterizedDiseaseCohortPlan")
        self.root = Path(destination).expanduser()
        self.plan = plan
        self.runtime_identity = runtime_identity
        self.subjects_root = self.root / "subjects"
        self.manifest_path = self.root / "manifest.json"
        if self.root.exists():
            if not resume:
                raise CapabilityError(
                    f"cohort bundle destination already exists: {self.root}; pass resume=True to continue"
                )
            self._load_and_validate_existing()
        else:
            self.root.mkdir(parents=True)
            self.subjects_root.mkdir()
            (self.root / "logs").mkdir()
            write_cohort_plan(plan, self.root / "plan.json")
            static_hashes = _write_assignments(self.root, plan)
            self._manifest = self._base_manifest(static_hashes)
            self._write_manifest()
            _append_log(self.root, f"START cohort_run_id={plan.run_id}")

    def _base_manifest(self, static_hashes: Mapping[str, str]) -> dict[str, object]:
        return {
            "format": _COHORT_BUNDLE_FORMAT,
            "format_version": _COHORT_BUNDLE_VERSION,
            "status": "INCOMPLETE",
            "cohort_run_id": self.plan.run_id,
            "dataset_identity": _identity(self.runtime_identity),
            "parent_dataset_identity": _identity(self.plan.parent_dataset_identity),
            "contract_version": self.plan.request.contract_version,
            "planner_version": self.plan.planner_version,
            "condition": self.plan.request.condition.value,
            "severity_parameter": self.plan.request.severity_parameter,
            "requested_age_range": [self.plan.request.age_min, self.plan.request.age_max],
            "source_supported_ages": list(self.plan.supported_ages),
            "requested_severity_range": [
                self.plan.request.severity_min,
                self.plan.request.severity_max,
            ],
            "patients": self.plan.request.patients,
            "canonical_subject_ids": list(self.plan.canonical_subject_ids),
            "completed_subject_ids": [],
            "subject_manifests": {},
            "static_files": {
                "plan.json": _sha256(self.root / "plan.json"),
                **dict(static_hashes),
            },
            "full_network_storage": {
                "scope": "final_converged_cardiac_cycle",
                "expected_segment_count": 116,
                "fields": {
                    "time_s": "s",
                    "x_m": "m",
                    "area_m2": "m^2",
                    "flow_m3_per_s": "m^3/s",
                    "pressure_pa": "Pa",
                    "velocity": "derived as flow_m3_per_s / area_m2",
                },
            },
            "population_interpretation": "designed_counterfactual_not_epidemiological",
            "evidence": "MODELLED",
            "healthy_reconstruction_gate": _QUALIFICATION_STATE,
            "clinical_validation": False,
            "warnings": [
                "Virtual Disease output is MODELLED and is not a clinical observation.",
                "The cohort is a designed counterfactual population, not a real-world epidemiological sample.",
                "Healthy PWDB reconstruction thresholds remain unfrozen; disease output is not clinically validated.",
            ],
        }

    def _load_and_validate_existing(self) -> None:
        if not self.manifest_path.exists():
            raise IntegrityError("resume destination lacks manifest.json")
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if payload.get("format") != _COHORT_BUNDLE_FORMAT:
            raise IntegrityError("resume destination is not a parameterized disease cohort bundle")
        if payload.get("cohort_run_id") != self.plan.run_id:
            raise IntegrityError("resume bundle cohort_run_id does not match the supplied plan")
        persisted = read_cohort_plan(self.root / "plan.json")
        if persisted.run_id != self.plan.run_id:
            raise IntegrityError("resume bundle plan content does not match the supplied plan")
        self.subjects_root.mkdir(exist_ok=True)
        (self.root / "logs").mkdir(exist_ok=True)
        self._manifest = payload
        for item in self.plan.assignments:
            partial = self.subjects_root / f".{item.canonical_subject_id}.partial"
            if partial.exists():
                shutil.rmtree(partial, ignore_errors=True)
        _append_log(self.root, f"RESUME cohort_run_id={self.plan.run_id}")

    def _write_manifest(self) -> None:
        temporary = self.manifest_path.with_suffix(".json.partial")
        temporary.write_text(_json_text(self._manifest), encoding="utf-8", newline="\n")
        os.replace(temporary, self.manifest_path)

    def subject_complete(self, subject_id: str) -> bool:
        expected = dict(self._manifest.get("subject_manifests", {})).get(subject_id)
        subject_root = self.subjects_root / subject_id
        manifest_path = subject_root / "subject_manifest.json"
        if expected is None or not manifest_path.exists():
            return False
        if _sha256(manifest_path) != expected:
            return False
        try:
            _verify_subject_directory(subject_root, json.loads(manifest_path.read_text(encoding="utf-8")))
        except IntegrityError:
            return False
        return True

    def write_subject(
        self,
        assignment: DiseaseCohortAssignment,
        state: RuntimeSubjectState,
        *,
        subject_disease_run_id: str,
    ) -> None:
        subject_id = assignment.canonical_subject_id
        if state.subject.canonical_subject_id != subject_id:
            raise IntegrityError("runtime state changed the planned canonical subject ID")
        if len(state.solution.segments) != 116 or len(state.baseline.segments) != 116:
            raise IntegrityError("parameterized PWDB cohort requires the complete 116-segment network")

        final_root = self.subjects_root / subject_id
        temporary = self.subjects_root / f".{subject_id}.partial"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir()
        results_root = temporary / "results"
        provenance_root = temporary / "provenance"
        results_root.mkdir()
        provenance_root.mkdir()
        exporter = JSONResultExporter()
        files: list[dict[str, object]] = []

        for index, result in enumerate(state.results, start=1):
            location = getattr(result, "location")
            if location is None:
                token = "global"
            elif hasattr(location, "canonical_site_id"):
                token = f"site-{location.canonical_site_id}"
            elif hasattr(location, "canonical_segment_id"):
                token = f"segment-{location.canonical_segment_id}"
            else:
                token = "location"
            result_path = results_root / f"{index:03d}_{result.quantity.canonical_name}_{token}.json"
            exporter.export(result, result_path, {})
            files.append(
                {
                    "kind": "scientific_result",
                    "path": result_path.relative_to(temporary).as_posix(),
                    "bytes": result_path.stat().st_size,
                    "sha256": _sha256(result_path),
                    "quantity": result.quantity.canonical_name,
                }
            )

        seen_provenance: set[str] = set()
        for record in state.provenance_records:
            if record.record_id in seen_provenance:
                continue
            seen_provenance.add(record.record_id)
            digest = hashlib.sha256(record.record_id.encode("utf-8")).hexdigest()
            record_path = provenance_root / f"record_{digest}.json"
            record_path.write_text(provenance_to_json(record) + "\n", encoding="utf-8", newline="\n")
            files.append(
                {
                    "kind": "provenance",
                    "path": record_path.relative_to(temporary).as_posix(),
                    "bytes": record_path.stat().st_size,
                    "sha256": _sha256(record_path),
                    "record_id": record.record_id,
                }
            )

        diagnostics_path = temporary / "diagnostics.json"
        _write_json(diagnostics_path, asdict(state.solution.diagnostics))
        files.append(
            {
                "kind": "solver_diagnostics",
                "path": "diagnostics.json",
                "bytes": diagnostics_path.stat().st_size,
                "sha256": _sha256(diagnostics_path),
            }
        )

        network_path = temporary / "full_network.npz"
        arrays: dict[str, np.ndarray] = {"time_s": np.asarray(state.solution.time_s, dtype=float)}
        segment_ids = []
        for segment in state.solution.segments:
            segment_ids.append(segment.segment_id)
            prefix = f"segment_{segment.segment_id}"
            arrays[f"{prefix}__x_m"] = np.asarray(segment.x_m, dtype=float)
            arrays[f"{prefix}__area_m2"] = np.asarray(segment.area_m2, dtype=float)
            arrays[f"{prefix}__flow_m3_per_s"] = np.asarray(segment.flow_m3_per_s, dtype=float)
            arrays[f"{prefix}__pressure_pa"] = np.asarray(segment.pressure_pa, dtype=float)
        np.savez_compressed(network_path, **arrays)
        network_index = temporary / "full_network_index.json"
        _write_json(
            network_index,
            {
                "segment_count": len(segment_ids),
                "segment_ids": segment_ids,
                "scope": "final_converged_cardiac_cycle",
                "velocity_definition": "U=Q/A",
                "units": {
                    "time_s": "s",
                    "x_m": "m",
                    "area_m2": "m^2",
                    "flow_m3_per_s": "m^3/s",
                    "pressure_pa": "Pa",
                },
            },
        )
        for path, kind in ((network_path, "full_network_solution"), (network_index, "full_network_index")):
            files.append(
                {
                    "kind": kind,
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )

        subject_manifest = {
            "canonical_subject_id": subject_id,
            "source_age_years": assignment.age_years,
            "condition": assignment.specification.condition.value,
            "severity_parameter": assignment.severity_parameter,
            "severity_value": assignment.severity_value,
            "disease_parameters": dict(assignment.specification.parameters),
            "preset_version": assignment.specification.preset_version,
            "subject_disease_run_id": subject_disease_run_id,
            "cohort_run_id": self.plan.run_id,
            "result_count": len(state.results),
            "provenance_count": len(seen_provenance),
            "full_network_segment_count": len(segment_ids),
            "solver_diagnostics": asdict(state.solution.diagnostics),
            "files": sorted(files, key=lambda item: str(item["path"])),
        }
        subject_manifest_path = temporary / "subject_manifest.json"
        _write_json(subject_manifest_path, subject_manifest)
        (temporary / "COMPLETE").write_text("complete\n", encoding="utf-8", newline="\n")

        if final_root.exists():
            shutil.rmtree(final_root)
        os.replace(temporary, final_root)
        manifest_hash = _sha256(final_root / "subject_manifest.json")
        subject_manifests = dict(self._manifest.get("subject_manifests", {}))
        subject_manifests[subject_id] = manifest_hash
        completed = [
            item.canonical_subject_id
            for item in self.plan.assignments
            if item.canonical_subject_id in subject_manifests
        ]
        self._manifest["subject_manifests"] = subject_manifests
        self._manifest["completed_subject_ids"] = completed
        self._manifest["status"] = "INCOMPLETE"
        self._write_manifest()
        _append_log(
            self.root,
            f"SUBJECT COMPLETE subject={subject_id} severity={assignment.severity_value:.17g}",
        )

    def record_failure(self, subject_id: str, exc: BaseException) -> None:
        self._manifest["status"] = "FAILED"
        self._manifest["failed_subject_id"] = subject_id
        self._manifest["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        self._write_manifest()
        _append_error(
            self.root,
            {
                "cohort_run_id": self.plan.run_id,
                "subject_id": subject_id,
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )
        _append_log(self.root, f"SUBJECT FAILED subject={subject_id} type={type(exc).__name__}")

    def finalize(self) -> Path:
        missing = [
            item.canonical_subject_id
            for item in self.plan.assignments
            if not self.subject_complete(item.canonical_subject_id)
        ]
        if missing:
            raise IntegrityError(f"cannot finalize cohort bundle; incomplete subjects: {missing}")
        self._manifest.pop("failed_subject_id", None)
        self._manifest.pop("failure", None)
        self._manifest["status"] = "COMPLETE"
        self._manifest["completed_subject_ids"] = list(self.plan.canonical_subject_ids)
        self._write_manifest()
        _append_log(self.root, f"COMPLETE cohort_run_id={self.plan.run_id}")
        return self.root


def _verify_subject_directory(subject_root: Path, subject_manifest: Mapping[str, object]) -> None:
    if not (subject_root / "COMPLETE").exists():
        raise IntegrityError(f"subject bundle incomplete: {subject_root.name}")
    if int(subject_manifest.get("full_network_segment_count", 0)) != 116:
        raise IntegrityError(f"subject {subject_root.name} does not preserve all 116 segments")
    for item in subject_manifest.get("files", []):
        row = dict(item)
        path = subject_root / str(row["path"])
        if not path.exists() or not path.is_file():
            raise IntegrityError(f"missing subject artifact: {path}")
        if path.stat().st_size != int(row["bytes"]):
            raise IntegrityError(f"size mismatch for subject artifact: {path}")
        if _sha256(path) != str(row["sha256"]):
            raise IntegrityError(f"checksum mismatch for subject artifact: {path}")


def inspect_parameterized_cohort_bundle(source: str | os.PathLike[str]) -> dict[str, object]:
    root = Path(source).expanduser()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise CapabilityError(f"cohort bundle manifest does not exist: {manifest_path}")
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"invalid cohort bundle manifest: {manifest_path}") from exc


def verify_parameterized_cohort_bundle(source: str | os.PathLike[str]) -> dict[str, object]:
    root = Path(source).expanduser()
    manifest = inspect_parameterized_cohort_bundle(root)
    if manifest.get("format") != _COHORT_BUNDLE_FORMAT:
        raise IntegrityError("not a VascuQuest parameterized disease cohort bundle")
    plan = read_cohort_plan(root / "plan.json")
    if manifest.get("cohort_run_id") != plan.run_id:
        raise IntegrityError("bundle manifest cohort_run_id does not match plan content")
    static_files = dict(manifest.get("static_files", {}))
    for relative, expected in static_files.items():
        path = root / relative
        if not path.exists() or _sha256(path) != str(expected):
            raise IntegrityError(f"static cohort artifact checksum mismatch: {relative}")

    subject_manifests = dict(manifest.get("subject_manifests", {}))
    verified = []
    for assignment in plan.assignments:
        subject_id = assignment.canonical_subject_id
        expected = subject_manifests.get(subject_id)
        if expected is None:
            if manifest.get("status") == "COMPLETE":
                raise IntegrityError(f"complete cohort is missing subject {subject_id}")
            continue
        subject_root = root / "subjects" / subject_id
        subject_manifest_path = subject_root / "subject_manifest.json"
        if not subject_manifest_path.exists() or _sha256(subject_manifest_path) != str(expected):
            raise IntegrityError(f"subject manifest checksum mismatch: {subject_id}")
        subject_manifest = json.loads(subject_manifest_path.read_text(encoding="utf-8"))
        if subject_manifest.get("canonical_subject_id") != subject_id:
            raise IntegrityError(f"subject manifest identity mismatch: {subject_id}")
        if not np.isclose(
            float(subject_manifest.get("severity_value")),
            assignment.severity_value,
            rtol=0.0,
            atol=1e-15,
        ):
            raise IntegrityError(f"subject severity assignment mismatch: {subject_id}")
        _verify_subject_directory(subject_root, subject_manifest)
        verified.append(subject_id)

    if manifest.get("status") == "COMPLETE" and tuple(verified) != plan.canonical_subject_ids:
        raise IntegrityError("complete cohort subject order/content does not match the frozen plan")
    return {
        "valid": True,
        "status": manifest.get("status"),
        "cohort_run_id": plan.run_id,
        "patients_planned": plan.request.patients,
        "subjects_verified": len(verified),
        "canonical_subject_ids": verified,
        "full_network_segment_count_per_completed_subject": 116,
        "evidence": "MODELLED",
        "clinical_validation": False,
    }


__all__ = [
    "ParameterizedDiseaseCohortBundleWriter",
    "inspect_parameterized_cohort_bundle",
    "read_cohort_plan",
    "verify_parameterized_cohort_bundle",
    "write_cohort_plan",
]
