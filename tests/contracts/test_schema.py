"""Contract tests for the canonical PWDB manifest and scientific schema."""

from __future__ import annotations

from copy import deepcopy
import json
from importlib.resources import files

import pytest

from vascuquest.domain.evidence import EvidenceClass
from vascuquest.errors import SchemaError
from vascuquest.schema import load_canonical_schema, load_manifest
from vascuquest.schema import loader


EXPECTED_ARTIFACTS = {
    "geo.zip": "4b1fba2da497094e6ad71fcee14b0f7e",
    "pwdb_data.mat": "3bd22caacaa7d7a83b3a04c71e1b2d49",
    "pwdb_data_w_aorta_brain_path.mat": "132c52b9962d83bfa672ff2bc96de6ac",
    "pwdb_data_w_aorta_finger_path.mat": "801dbfc7927dc951a87034ebb40ff12f",
    "pwdb_data_w_aorta_foot_path_a.mat": "01f6f7c079ccbd245d44996ad95ff58f",
    "pwdb_data_w_aorta_foot_path_p.mat": "58a5bfc5eeeb6584652c8238eceba73c",
    "pwdb_data_w_aorta_foot_path_u.mat": "bc00c1cc9c9ddef5d5070123be4b0f44",
    "pwdb_data_w_aorta_rsubclavian_path.mat": "85052a34c42b847af397e42bd6300fc7",
    "pwdb_haemod_params.csv": "43e1244665e6cee6b77501102404b70a",
    "pwdb_model_configs.csv": "8c3b4f2f86386b72250766aedea9db52",
    "pwdb_model_variations.csv": "3f1987efbc131b2cab8e576807385d5b",
    "pwdb_onset_times.csv": "1103ddc3852d6f2164b981582fad8d23",
    "pwdb_pw_indices.csv": "87946898d39d5a6d894901ad39f6b546",
    "PWs_csv.zip": "81067f96d6078bbbb5cd9fce5d73f5bd",
    "PWs_mat.zip": "50c03268de6ae2484367a881f92eaa3d",
    "PWs_wfdb.zip": "c4c3c3ba8163ee1f4f1495d7a4e70d73",
}


def _raw_resource(name: str) -> dict[str, object]:
    resource = files("vascuquest.schema").joinpath("resources", name)
    with resource.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def test_manifest_matches_canonical_record_exactly() -> None:
    manifest = load_manifest()

    assert manifest.manifest_version == 1
    assert manifest.canonical_record_id == "3275625"
    assert manifest.canonical_doi == "10.5281/zenodo.3275625"
    assert manifest.canonical_record_url == "https://zenodo.org/records/3275625"
    assert len(manifest.artifacts) == 16
    assert {artifact.filename: artifact.checksum_value for artifact in manifest.artifacts} == EXPECTED_ARTIFACTS


def test_manifest_identifiers_filenames_locators_and_checksums_are_unique_and_valid() -> None:
    manifest = load_manifest()

    artifact_ids = [artifact.artifact_id for artifact in manifest.artifacts]
    filenames = [artifact.filename for artifact in manifest.artifacts]
    locators = [artifact.source_locator for artifact in manifest.artifacts]

    assert len(artifact_ids) == len(set(artifact_ids))
    assert len(filenames) == len(set(filenames))
    assert len(locators) == len(set(locators))

    for artifact in manifest.artifacts:
        assert artifact.checksum_algorithm == "md5"
        assert len(artifact.checksum_value) == 32
        assert artifact.source_locator.startswith("https://")
        assert artifact.capabilities_provided
        assert artifact.reported_size_bytes is None or (
            isinstance(artifact.reported_size_bytes, int)
            and not isinstance(artifact.reported_size_bytes, bool)
            and artifact.reported_size_bytes >= 0
        )


def test_manifest_does_not_encode_rounded_display_sizes_as_byte_counts() -> None:
    raw = _raw_resource("pwdb3275625_manifest.json")
    artifacts = raw["artifacts"]
    assert isinstance(artifacts, list)

    for artifact in artifacts:
        assert isinstance(artifact, dict)
        assert artifact["reported_size_bytes"] is None or isinstance(
            artifact["reported_size_bytes"], int
        )
        assert not isinstance(artifact["reported_size_bytes"], str)


def test_schema_has_versioned_unique_canonical_quantity_identities() -> None:
    schema = load_canonical_schema()

    assert schema.schema_version == "1"
    assert schema.dataset_family == "PWDB"
    assert schema.canonical_record_id == "3275625"
    assert schema.canonical_doi == "10.5281/zenodo.3275625"

    names = tuple(quantity.definition.canonical_name for quantity in schema.quantities)
    assert names == (
        "pressure",
        "flow_velocity",
        "luminal_area",
        "photoplethysmogram",
    )
    assert len(names) == len(set(names))


def test_waveform_quantity_mappings_preserve_source_aliases_and_units() -> None:
    schema = load_canonical_schema()
    expected = {
        "pressure": ("P", "mmHg", "pressure", "mmHg"),
        "flow_velocity": ("U", "m/s", "velocity", "m/s"),
        "luminal_area": ("A", "m^2", "area", "m^2"),
        "photoplethysmogram": ("PPG", "au", "dimensionless", "au"),
    }

    for name, (alias, source_unit, dimension, canonical_unit) in expected.items():
        quantity_schema = schema.quantity_schema(name)
        definition = quantity_schema.definition
        assert definition.source_aliases == (alias,)
        assert definition.physical_dimension == dimension
        assert definition.canonical_unit == canonical_unit
        assert definition.default_evidence is EvidenceClass.SOURCE
        assert quantity_schema.category == "waveform_signal"
        assert len(quantity_schema.source_mappings) == 1
        mapping = quantity_schema.source_mappings[0]
        assert mapping.source_field == alias
        assert mapping.source_unit == source_unit
        assert mapping.canonical_unit == canonical_unit


def test_dimensionless_ppg_is_marked_explicitly() -> None:
    ppg = load_canonical_schema().quantity("photoplethysmogram")

    assert ppg.physical_dimension == "dimensionless"
    assert ppg.canonical_unit == "au"
    assert ppg.canonical_unit is not None


def test_luminal_area_metadata_defect_is_traceable_without_changing_source_label() -> None:
    area = load_canonical_schema().quantity_schema("luminal_area")

    assert area.definition.canonical_unit == "m^2"
    assert area.definition.known_source_issues == ("pwdb_mat_metadata_area_unit",)
    assert len(area.source_defects) == 1

    defect = area.source_defects[0]
    assert defect.issue_id == "pwdb_mat_metadata_area_unit"
    assert defect.source_scope == "PWs_mat_metadata"
    assert defect.source_field == "PWs.units.A"
    assert defect.reported_value == "m3"
    assert defect.canonical_interpretation == "m^2"
    assert defect.status == "upstream_metadata_defect"


def test_unknown_quantity_lookup_fails_explicitly() -> None:
    with pytest.raises(KeyError):
        load_canonical_schema().quantity("not_a_quantity")


def test_schema_rejects_source_alias_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(_raw_resource("canonical_schema.json"))
    quantities = payload["quantities"]
    assert isinstance(quantities, list)
    assert isinstance(quantities[1], dict)
    quantities[1]["source_aliases"] = ["P"]

    monkeypatch.setattr(loader, "_read_resource", lambda _name: payload)
    with pytest.raises(SchemaError, match="source alias"):
        loader.load_canonical_schema()


def test_schema_rejects_source_unit_not_declared_as_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(_raw_resource("canonical_schema.json"))
    quantities = payload["quantities"]
    assert isinstance(quantities, list)
    assert isinstance(quantities[0], dict)
    mappings = quantities[0]["source_mappings"]
    assert isinstance(mappings, list)
    assert isinstance(mappings[0], dict)
    mappings[0]["source_unit"] = "Pa"

    monkeypatch.setattr(loader, "_read_resource", lambda _name: payload)
    with pytest.raises(SchemaError, match="allowed source unit"):
        loader.load_canonical_schema()


def test_schema_rejects_unknown_category(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(_raw_resource("canonical_schema.json"))
    quantities = payload["quantities"]
    assert isinstance(quantities, list)
    assert isinstance(quantities[0], dict)
    quantities[0]["category"] = "invented_category"

    monkeypatch.setattr(loader, "_read_resource", lambda _name: payload)
    with pytest.raises(SchemaError, match="unknown category"):
        loader.load_canonical_schema()


def test_schema_rejects_unmatched_defect_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(_raw_resource("canonical_schema.json"))
    quantities = payload["quantities"]
    assert isinstance(quantities, list)
    assert isinstance(quantities[2], dict)
    quantities[2]["known_source_issues"] = []

    monkeypatch.setattr(loader, "_read_resource", lambda _name: payload)
    with pytest.raises(SchemaError, match="known_source_issues"):
        loader.load_canonical_schema()


def test_manifest_rejects_duplicate_artifact_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = deepcopy(_raw_resource("pwdb3275625_manifest.json"))
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    assert isinstance(artifacts[0], dict)
    assert isinstance(artifacts[1], dict)
    artifacts[1]["artifact_id"] = artifacts[0]["artifact_id"]

    monkeypatch.setattr(loader, "_read_resource", lambda _name: payload)
    with pytest.raises(SchemaError, match="artifact IDs"):
        loader.load_manifest()
