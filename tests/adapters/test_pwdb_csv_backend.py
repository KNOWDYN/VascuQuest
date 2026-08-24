"""Adapter tests for the PWDB lightweight CSV backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from vascuquest.backends.pwdb3275625 import PWDB3275625Backend
from vascuquest.backends.pwdb3275625.csv_reader import SubjectCSVTable
from vascuquest.domain.identity import SubjectKey
from vascuquest.domain.location import MeasurementSite
from vascuquest.errors import SchemaError, SelectionError
from vascuquest.ports.backend import DatasetBackend, QuantityRequest


def _write_sources(tmp_path: Path) -> dict[str, Path]:
    sources = {
        "model_configurations": tmp_path / "pwdb_model_configs.csv",
        "haemodynamic_parameters": tmp_path / "pwdb_haemod_params.csv",
        "pulse_wave_indices": tmp_path / "pwdb_pw_indices.csv",
        "onset_times": tmp_path / "pwdb_onset_times.csv",
    }
    sources["model_configurations"].write_text(
        "Subject Number, age [years], hr [bpm], sv [ml]\n1,25,60,70\n2,35,65,72\n",
        encoding="utf-8",
    )
    sources["haemodynamic_parameters"].write_text(
        "Subject Number, age [years], HR [bpm], SV [ml], CO [l/min], SBP_b [mmHg], PWV_a [m/s], AIx [%]\n"
        "1,25,60,70,4.2,118,6.1,10\n2,35,65,72,4.68,124,6.8,14\n",
        encoding="utf-8",
    )
    sources["pulse_wave_indices"].write_text(
        "Subject Number, Age, Brachial_SBP_V, AorticRoot_AI\n1,25,118,10\n2,35,124,14\n",
        encoding="utf-8",
    )
    sources["onset_times"].write_text(
        "Subject Number, AorticRoot_P, Radial_P, Brachial_P\n1,0,0.115,0.082\n2,0,0.121,0.087\n",
        encoding="utf-8",
    )
    return sources


def _backend(tmp_path: Path) -> PWDB3275625Backend:
    sources = _write_sources(tmp_path)
    def resolve(artifact_id: str) -> Path:
        return sources[artifact_id]
    return PWDB3275625Backend(resolve)


def test_subject_csv_table_uses_explicit_subject_identifier_not_row_number(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    path.write_text("Subject Number, value\n2,20\n1,10\n", encoding="utf-8")
    table = SubjectCSVTable(path)
    assert table.subject_ids() == ("2", "1")
    assert table.numeric("1", "value").value == 10.0
    assert table.numeric("2", "value").value == 20.0


def test_subject_csv_table_rejects_duplicate_subject_identity(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("Subject Number, value\n1,10\n1,11\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="duplicate"):
        SubjectCSVTable(path).subject_ids()


def test_backend_conforms_to_port_and_enumerates_virtual_subjects(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    assert isinstance(backend, DatasetBackend)
    assert backend.identity().record_id == "3275625"
    assert backend.identity().persistent_identifier == "10.5281/zenodo.3275625"
    assert tuple(subject.canonical_subject_id for subject in backend.subjects()) == ("1", "2")
    assert {"subject_model_configuration", "haemodynamic_parameters", "pulse_wave_indices", "onset_times"}.issubset(backend.capabilities())


def test_backend_reads_canonical_scalars_from_verified_source_headers(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "2")
    age = backend.get_quantity(QuantityRequest("age", subject=subject))
    assert age.values == 35.0
    assert age.source_label == "age [years]"
    assert age.source_unit == "years"
    assert age.quantity.canonical_unit == "years"

    cardiac_output = backend.get_quantity(QuantityRequest("cardiac_output", subject=subject))
    assert cardiac_output.values == 4.68
    assert cardiac_output.source_label == "CO [l/min]"
    assert cardiac_output.quantity.canonical_unit == "l/min"

    brachial = backend.get_quantity(QuantityRequest("brachial_systolic_pressure", subject=subject, location=MeasurementSite("Brachial")))
    assert brachial.values == 124.0
    assert brachial.source_label == "Brachial_SBP_V"
    assert brachial.location == MeasurementSite("Brachial")

    onset = backend.get_quantity(QuantityRequest("pressure_onset_time", subject=subject, location=MeasurementSite("Radial")))
    assert onset.values == 0.121
    assert onset.source_label == "Radial_P"
    assert onset.source_unit == "s"


def test_backend_provenance_identifies_exact_source_artifact_and_field(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    result = backend.get_quantity(QuantityRequest("aortic_augmentation_index", subject=subject, location=MeasurementSite("AorticRoot")))
    provenance = backend.provenance(result.provenance_ref)
    assert provenance.source_artifacts[0].artifact_id == "pulse_wave_indices"
    assert provenance.source_fields == ("AorticRoot_AI",)
    assert provenance.subject == subject
    assert provenance.location == MeasurementSite("AorticRoot")


def test_fixed_site_quantity_rejects_scientifically_wrong_location(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    with pytest.raises(SelectionError, match="Brachial"):
        backend.get_quantity(QuantityRequest("brachial_systolic_pressure", subject=subject, location=MeasurementSite("Radial")))
