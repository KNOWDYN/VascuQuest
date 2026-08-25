from __future__ import annotations

import json

import numpy as np
import pytest

from vascuquest.backends.pwdb3275625.geometry_reader import GeometrySegment
from vascuquest.domain import (
    Cohort,
    Coordinate,
    DatasetIdentity,
    EvidenceClass,
    MeasurementSite,
    ScientificResult,
    SubjectKey,
    ValidityState,
    Waveform,
)
from vascuquest.errors import CapabilityError, ReproducibilityError
from vascuquest.exporters import (
    CSV_EXPORTER_ID,
    CSVResultExporter,
    JSON_EXPORTER_ID,
    JSONResultExporter,
    load_result_csv,
    load_result_json,
)
from vascuquest.ports.exporter import ResultExporter
from vascuquest.schema import load_canonical_schema


IDENTITY = DatasetIdentity(
    dataset_family="PWDB",
    record_id="3275625",
    persistent_identifier="10.5281/zenodo.3275625",
    schema_version="1",
)
SUBJECT = SubjectKey(IDENTITY, "1")
SITE = MeasurementSite("AorticRoot")


def _waveform() -> Waveform:
    return Waveform(
        dataset_identity=IDENTITY,
        quantity=load_canonical_schema().quantity("pressure"),
        values=np.asarray([80.0, np.nan, 82.0, np.nan]),
        provenance_ref="sha256:source-pressure",
        dimensions=("time",),
        coordinates=(
            Coordinate("time", np.asarray([0.0, 0.002, 0.004, 0.006]), unit="s"),
        ),
        source_unit="mmHg",
        source_label="P",
        subject=SUBJECT,
        location=SITE,
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.VALID_WITH_WARNING,
        warnings=("one internal source sample is missing",),
        missing_mask=np.asarray([False, True, False, False]),
        padding_mask=np.asarray([False, False, False, True]),
    )


def _cohort_result() -> ScientificResult:
    cohort = Cohort(
        dataset_identity=IDENTITY,
        canonical_subject_ids=("1", "2", "3"),
        ordering_rule="canonical_backend_order",
        selection_specification=("ids:1,2,3",),
        creation_provenance_ref="selection:1-2-3",
    )
    return ScientificResult(
        dataset_identity=IDENTITY,
        quantity=load_canonical_schema().quantity("age"),
        values=(25.0, None, 45.0),
        provenance_ref="sha256:source-age",
        dimensions=("subject",),
        coordinates=(Coordinate("subject", ("1", "2", "3")),),
        source_unit="years",
        source_label="age [years]",
        cohort=cohort,
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.VALID_WITH_WARNING,
        warnings=("1 of 3 source values are missing",),
    )


def _geometry_result() -> ScientificResult:
    segments = (
        GeometrySegment("1", 1, 2, 0.10, 0.012, 0.011, 1.5, 2.5),
        GeometrySegment("2", 2, 3, 0.20, 0.011, 0.010, 1.6, 2.6),
    )
    return ScientificResult(
        dataset_identity=IDENTITY,
        quantity=load_canonical_schema().quantity("vascular_geometry"),
        values=segments,
        provenance_ref="sha256:source-geometry",
        dimensions=("segment",),
        coordinates=(Coordinate("segment", ("1", "2")),),
        subject=SUBJECT,
        evidence=EvidenceClass.SOURCE,
        validity=ValidityState.NOT_EVALUATED,
    )


def _assert_common_metadata(original: ScientificResult, rebuilt: ScientificResult) -> None:
    assert rebuilt.dataset_identity == original.dataset_identity
    assert rebuilt.quantity == original.quantity
    assert rebuilt.provenance_ref == original.provenance_ref
    assert rebuilt.dimensions == original.dimensions
    assert rebuilt.source_unit == original.source_unit
    assert rebuilt.source_label == original.source_label
    assert rebuilt.subject == original.subject
    assert rebuilt.cohort == original.cohort
    assert rebuilt.location == original.location
    assert rebuilt.evidence is original.evidence
    assert rebuilt.value_state is original.value_state
    assert rebuilt.validity is original.validity
    assert rebuilt.warnings == original.warnings
    assert rebuilt.method_id == original.method_id


def test_exporters_conform_to_protocol_and_declare_retention() -> None:
    json_exporter = JSONResultExporter()
    csv_exporter = CSVResultExporter()
    assert isinstance(json_exporter, ResultExporter)
    assert isinstance(csv_exporter, ResultExporter)
    assert json_exporter.descriptor.qualified_id == JSON_EXPORTER_ID
    assert csv_exporter.descriptor.qualified_id == CSV_EXPORTER_ID
    assert json_exporter.supported_output_formats == ("json",)
    assert csv_exporter.supported_output_formats == ("csv",)
    assert "provenance" in json_exporter.provenance_retention.lower()
    assert "sidecar" in csv_exporter.provenance_retention.lower()


def test_json_waveform_round_trip_preserves_scientific_semantics(tmp_path) -> None:
    original = _waveform()
    destination = tmp_path / "pressure.json"
    returned = JSONResultExporter().export(original, destination, {})
    assert returned == destination

    rebuilt = load_result_json(destination)
    assert isinstance(rebuilt, Waveform)
    _assert_common_metadata(original, rebuilt)
    np.testing.assert_allclose(rebuilt.values, original.values, equal_nan=True)
    np.testing.assert_allclose(
        rebuilt.time_coordinate.values,
        original.time_coordinate.values,
    )
    assert rebuilt.time_coordinate.unit == "s"
    np.testing.assert_array_equal(rebuilt.missing_mask, original.missing_mask)
    np.testing.assert_array_equal(rebuilt.padding_mask, original.padding_mask)
    assert rebuilt.values.flags.writeable is False


def test_json_export_is_deterministic_and_preserves_structured_geometry(tmp_path) -> None:
    original = _geometry_result()
    first = tmp_path / "geometry-a.json"
    second = tmp_path / "geometry-b.json"
    exporter = JSONResultExporter()
    exporter.export(original, first, {})
    exporter.export(original, second, {})
    assert first.read_bytes() == second.read_bytes()

    rebuilt = load_result_json(first)
    _assert_common_metadata(original, rebuilt)
    assert isinstance(rebuilt.values, tuple)
    assert rebuilt.values[0]["segment_id"] == "1"
    assert rebuilt.values[0]["length_m"] == pytest.approx(0.10)
    assert rebuilt.values[0]["__record_type__"].endswith("GeometrySegment")
    assert tuple(rebuilt.coordinates[0].values) == ("1", "2")


def test_csv_cohort_round_trip_uses_mandatory_metadata_sidecar(tmp_path) -> None:
    original = _cohort_result()
    destination = tmp_path / "ages.csv"
    outputs = CSVResultExporter().export(original, destination, {})
    assert outputs["data_path"] == destination
    metadata_path = outputs["metadata_path"]
    assert metadata_path.name == "ages.csv.meta.json"

    sidecar = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["provenance_ref"] == original.provenance_ref
    assert sidecar["metadata"]["evidence"] == "SOURCE"
    assert sidecar["metadata"]["quantity"]["canonical_unit"] == "years"
    assert sidecar["table"]["dimensions"] == ["subject"]

    rebuilt = load_result_csv(destination)
    _assert_common_metadata(original, rebuilt)
    assert rebuilt.values.tolist() == [25.0, None, 45.0]
    assert tuple(rebuilt.coordinates[0].values) == ("1", "2", "3")


def test_csv_waveform_round_trip_preserves_coordinates_and_masks(tmp_path) -> None:
    original = _waveform()
    destination = tmp_path / "pressure.csv"
    CSVResultExporter().export(original, destination, {})
    rebuilt = load_result_csv(destination)
    assert isinstance(rebuilt, Waveform)
    _assert_common_metadata(original, rebuilt)
    np.testing.assert_allclose(rebuilt.values, original.values, equal_nan=True)
    np.testing.assert_allclose(
        rebuilt.time_coordinate.values,
        original.time_coordinate.values,
    )
    np.testing.assert_array_equal(rebuilt.missing_mask, original.missing_mask)
    np.testing.assert_array_equal(rebuilt.padding_mask, original.padding_mask)


def test_csv_rejects_structured_values_instead_of_flattening_them(tmp_path) -> None:
    with pytest.raises(CapabilityError, match="does not flatten structured"):
        CSVResultExporter().export(_geometry_result(), tmp_path / "geometry.csv", {})


def test_exporters_reject_undeclared_options(tmp_path) -> None:
    result = _cohort_result()
    with pytest.raises(ValueError, match="defines no export options"):
        JSONResultExporter().export(result, tmp_path / "result.json", {"indent": 2})
    with pytest.raises(ValueError, match="defines no export options"):
        CSVResultExporter().export(result, tmp_path / "result.csv", {"delimiter": ";"})


def test_csv_loader_rejects_sidecar_coordinate_disagreement(tmp_path) -> None:
    destination = tmp_path / "ages.csv"
    outputs = CSVResultExporter().export(_cohort_result(), destination, {})
    text = destination.read_text(encoding="utf-8")
    destination.write_text(text.replace('"1"', '"999"', 1), encoding="utf-8")
    with pytest.raises(ReproducibilityError, match="disagrees with its sidecar"):
        load_result_csv(outputs["data_path"])
