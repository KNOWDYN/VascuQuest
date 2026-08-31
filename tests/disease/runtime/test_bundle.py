from __future__ import annotations

import json
from pathlib import Path

import pytest

from vascuquest.disease.runtime.bundle import write_runtime_bundle
from vascuquest.errors import CapabilityError
from vascuquest.exporters import load_result_json
from vascuquest.provenance import provenance_from_json


def test_runtime_bundle_exports_results_provenance_and_manifest(
    runtime_dataset,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "disease-run"
    written = write_runtime_bundle(runtime_dataset, destination)
    assert written == destination
    assert destination.is_dir()

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == "vascuquest-virtual-disease-bundle"
    assert manifest["format_version"] == 1
    assert manifest["run_id"] == runtime_dataset.run_id
    assert manifest["dataset_identity"]["record_id"] == runtime_dataset.run_id
    assert manifest["parent_dataset_identity"]["record_id"] == "3275625"
    assert manifest["canonical_subject_ids"] == ["1"]
    assert manifest["qualification_state"] == "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"
    assert manifest["result_count"] == 1
    assert manifest["provenance_count"] == 1
    assert manifest["request"]["condition"] == "large_artery_stiffening"
    assert manifest["quantity_statuses"]["photoplethysmogram"] == "NOT_SUPPORTED"

    result_entry = next(item for item in manifest["files"] if item["kind"] == "scientific_result")
    loaded = load_result_json(destination / result_entry["path"])
    assert loaded.quantity.canonical_name == "age"
    assert loaded.values == 50
    assert loaded.evidence.value == "MODELLED"
    assert loaded.subject is not None
    assert loaded.subject.canonical_subject_id == "1"

    provenance_entry = next(item for item in manifest["files"] if item["kind"] == "provenance")
    provenance = provenance_from_json(
        (destination / provenance_entry["path"]).read_text(encoding="utf-8")
    )
    assert provenance.record_id == result_entry["provenance_ref"]


def test_runtime_bundle_refuses_implicit_overwrite(runtime_dataset, tmp_path: Path) -> None:
    destination = tmp_path / "disease-run"
    write_runtime_bundle(runtime_dataset, destination)
    with pytest.raises(CapabilityError, match="overwrite=True"):
        write_runtime_bundle(runtime_dataset, destination)

    rewritten = write_runtime_bundle(runtime_dataset, destination, overwrite=True)
    assert rewritten == destination
    assert (destination / "manifest.json").is_file()
