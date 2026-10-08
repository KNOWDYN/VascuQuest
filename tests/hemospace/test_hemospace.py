"""HEMOSPACE unit/contract tests that do not require the full PWDB archive."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vascuquest.hemospace.catalogue import semantics_for
from vascuquest.hemospace.service import HemospaceSession


class _FakeDatasetSession:
    identity = SimpleNamespace(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
    )

    def subject(self, subject_id: str) -> object:
        return SimpleNamespace(canonical_subject_id=subject_id)


def _sources(tmp_path: Path) -> dict[str, Path]:
    files = {
        "model_configurations": tmp_path / "pwdb_model_configs.csv",
        "model_variations": tmp_path / "pwdb_model_variations.csv",
        "haemodynamic_parameters": tmp_path / "pwdb_haemod_params.csv",
        "pulse_wave_indices": tmp_path / "pwdb_pw_indices.csv",
        "onset_times": tmp_path / "pwdb_onset_times.csv",
    }
    files["model_configurations"].write_text(
        "Subject Number, age [years], hr [bpm], sv [ml]\n1,45,60,70\n",
        encoding="utf-8",
    )
    files["model_variations"].write_text(
        "Subject Number,DIA,PWV\n1,-1,2\n",
        encoding="utf-8",
    )
    files["haemodynamic_parameters"].write_text(
        "Subject Number,HR [bpm],SV [ml],CO [l/min]\n1,60,70,4.2\n",
        encoding="utf-8",
    )
    files["pulse_wave_indices"].write_text(
        "Subject Number,Age,AorticRoot_SBP_V\n1,45,120\n",
        encoding="utf-8",
    )
    files["onset_times"].write_text(
        "Subject Number,AorticRoot_P\n1,0\n",
        encoding="utf-8",
    )
    return files


def test_model_variation_semantics_preserve_design_space_meaning() -> None:
    pwv = semantics_for("model_variations", "PWV")
    assert pwv.canonical_id == "arterial_stiffness_variation"
    assert pwv.section == "generative_variation"
    assert pwv.unit == "SD_from_age_specific_mean"


def test_pulse_wave_index_parser_preserves_site_metric_and_unit() -> None:
    item = semantics_for("pulse_wave_indices", "Femoral_Qmean_V")
    assert item.location == "Femoral"
    assert item.section == "flow"
    assert item.unit == "m^3/s"


def test_scalar_record_exposes_every_numeric_source_field_and_derives_transparently(tmp_path: Path) -> None:
    files = _sources(tmp_path)
    hs = HemospaceSession(_FakeDatasetSession(), lambda artifact_id: files[artifact_id])
    record = hs.record("1")

    assert record.subject_id == "1"
    assert record.depth == "scalar"
    assert record.coverage.source_fields_seen == 12
    assert record.coverage.source_fields_exposed == 12
    assert record.coverage.source_fields_missing == 0
    assert record.coverage.scalar_source_complete is True

    by_id = {item.canonical_id: item for item in record.items}
    assert by_id["arterial_stiffness_variation"].value == 2.0
    assert by_id["arterial_stiffness_variation"].evidence == "SOURCE"
    assert by_id["cardiac_cycle_duration"].value == 1.0
    assert by_id["cardiac_cycle_duration"].evidence == "DERIVED"
    assert by_id["cardiac_output_from_hr_sv"].value == 4.2
    assert by_id["cardiac_output_from_hr_sv"].evidence == "RECONSTRUCTED"


def test_record_explicitly_marks_unencoded_clinical_information_unavailable(tmp_path: Path) -> None:
    files = _sources(tmp_path)
    hs = HemospaceSession(_FakeDatasetSession(), lambda artifact_id: files[artifact_id])
    record = hs.record("1")
    unavailable = {entry.canonical_id for entry in record.unavailable}
    assert "smoking_history" in unavailable
    assert "genetics" in unavailable
    assert "longitudinal_life_history" in unavailable
    assert "future_clinical_event_risk" in unavailable
