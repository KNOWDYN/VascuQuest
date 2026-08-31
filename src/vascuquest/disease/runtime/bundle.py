"""Portable explicit bundle export for generated Virtual Disease populations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from vascuquest.disease.runtime.dataset import RuntimeDiseaseDataset
from vascuquest.domain.location import MeasurementSite, SegmentLocation
from vascuquest.errors import CapabilityError
from vascuquest.exporters.json_exporter import JSONResultExporter
from vascuquest.provenance import provenance_to_json

_BUNDLE_FORMAT = "vascuquest-virtual-disease-bundle"
_BUNDLE_VERSION = 1
_QUALIFICATION_STATE = "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"


def _identity(identity: object) -> dict[str, str]:
    return {
        "dataset_family": str(getattr(identity, "dataset_family")),
        "record_id": str(getattr(identity, "record_id")),
        "persistent_identifier": str(getattr(identity, "persistent_identifier")),
        "schema_version": str(getattr(identity, "schema_version")),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _location_token(location: object | None) -> str:
    if location is None:
        return "global"
    if isinstance(location, MeasurementSite):
        return f"site-{location.canonical_site_id}"
    if isinstance(location, SegmentLocation):
        return f"segment-{location.canonical_segment_id}"
    return "location"


def _record_filename(record_id: str) -> str:
    if record_id.startswith("sha256:"):
        return f"sha256_{record_id.split(':', 1)[1]}.json"
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    return f"record_{digest}.json"


def _result_filename(index: int, result: object) -> str:
    quantity = str(getattr(getattr(result, "quantity"), "canonical_name"))
    location = _location_token(getattr(result, "location"))
    return f"{index:03d}_{quantity}_{location}.json"


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    text = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_runtime_bundle(
    dataset: RuntimeDiseaseDataset,
    destination: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> Path:
    """Explicitly persist a generated runtime dataset as portable JSON files.

    The bundle is a user-requested export, not an implicit runtime cache. Source
    PWDB artifacts are referenced through provenance checksums and are never
    copied or modified.
    """

    if not isinstance(dataset, RuntimeDiseaseDataset):
        raise TypeError("dataset must be a RuntimeDiseaseDataset")
    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a boolean")
    path = Path(destination).expanduser()
    if not path.name:
        raise ValueError("bundle destination must be a named directory path")
    if path.exists() and not overwrite:
        raise CapabilityError(
            f"bundle destination already exists: {path}; pass overwrite=True explicitly"
        )
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{path.name}.", dir=str(path.parent))
    )
    exporter = JSONResultExporter()
    files: list[dict[str, object]] = []
    provenance_ids: set[str] = set()
    try:
        results_root = temporary / "results"
        provenance_root = temporary / "provenance"
        results_root.mkdir(parents=True)
        provenance_root.mkdir(parents=True)

        for subject in dataset.subjects():
            subject_id = subject.canonical_subject_id
            state = dataset.state(subject_id)
            subject_root = results_root / subject_id
            subject_root.mkdir(parents=True)
            for index, result in enumerate(state.results, start=1):
                result_path = subject_root / _result_filename(index, result)
                exporter.export(result, result_path, {})
                relative = result_path.relative_to(temporary).as_posix()
                location = result.location
                files.append(
                    {
                        "kind": "scientific_result",
                        "path": relative,
                        "sha256": _sha256(result_path),
                        "subject_id": subject_id,
                        "quantity": result.quantity.canonical_name,
                        "location": (
                            None
                            if location is None
                            else (
                                location.canonical_site_id
                                if isinstance(location, MeasurementSite)
                                else getattr(location, "canonical_segment_id", str(location))
                            )
                        ),
                        "evidence": result.evidence.value,
                        "source_label": result.source_label,
                        "provenance_ref": result.provenance_ref,
                    }
                )
                provenance_ids.add(result.provenance_ref)

        for record_id in sorted(provenance_ids):
            record = dataset.provenance(record_id)
            record_path = provenance_root / _record_filename(record_id)
            record_path.write_text(
                provenance_to_json(record) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            files.append(
                {
                    "kind": "provenance",
                    "path": record_path.relative_to(temporary).as_posix(),
                    "sha256": _sha256(record_path),
                    "record_id": record_id,
                }
            )

        request = dataset.run_identity.request
        specification = request.specification
        manifest = {
            "format": _BUNDLE_FORMAT,
            "format_version": _BUNDLE_VERSION,
            "dataset_identity": _identity(dataset.identity),
            "parent_dataset_identity": _identity(dataset.parent_identity),
            "run_id": dataset.run_id,
            "contract_version": dataset.run_identity.contract_version,
            "request": {
                "patients": request.patients,
                "age_group": request.age_group,
                "seed": request.seed,
                "condition": specification.condition.value,
                "parameters": dict(specification.parameters),
                "preset_version": specification.preset_version,
            },
            "canonical_subject_ids": list(dataset.cohort.canonical_subject_ids),
            "quantity_statuses": {
                name: status.value for name, status in dataset.quantity_statuses()
            },
            "materialized_quantities": [
                item.canonical_name for item in dataset.quantities()
            ],
            "measurement_sites": [
                item.canonical_site_id for item in dataset.locations()
            ],
            "result_count": sum(
                len(dataset.state(subject.canonical_subject_id).results)
                for subject in dataset.subjects()
            ),
            "provenance_count": len(provenance_ids),
            "qualification_state": _QUALIFICATION_STATE,
            "warnings": [
                "Virtual Disease output is MODELLED and is not a clinical observation.",
                "Healthy PWDB reconstruction thresholds remain unfrozen; disease output is not clinically validated.",
            ],
            "files": sorted(files, key=lambda item: str(item["path"])),
        }
        manifest_path = temporary / "manifest.json"
        _write_manifest(manifest_path, manifest)

        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        os.replace(temporary, path)
        return path
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


__all__ = ["write_runtime_bundle"]
