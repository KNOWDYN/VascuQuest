"""Fast HEMOSPACE completion-contract tests; no full PWDB archive required."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vascuquest.hemospace.agent import agent_contract
from vascuquest.hemospace.catalogue import semantics_for
from vascuquest.hemospace.cohort import Criterion
from vascuquest.hemospace.service import HemospaceSession
from vascuquest.hemospace.source_table import HemospaceSubjectCSVTable


class _FakeDatasetSession:
    identity = SimpleNamespace(
        dataset_family="PWDB",
        record_id="3275625",
        persistent_identifier="10.5281/zenodo.3275625",
    )

    def subject(self, subject_id: str) -> object:
        return SimpleNamespace(canonical_subject_id=subject_id)


def _write_sources(tmp_path: Path) -> dict[str, Path]:
    files = {
        "model_configurations": tmp_path / "pwdb_model_configs.csv",
        "model_variations": tmp_path / "pwdb_model_variations.csv",
        "haemodynamic_parameters": tmp_path / "pwdb_haemod_params.csv",
        "pulse_wave_indices": tmp_path / "pwdb_pw_indices.csv",
        "onset_times": tmp_path / "pwdb_onset_times.csv",
    }
    files["model_configurations"].write_text(
        "Subject Number,age [years],hr [bpm],sv [ml]\n1,45,60,70\n2,45,60,70\n3,45,60,70\n",
        encoding="utf-8",
    )
    files["model_variations"].write_text(
        "SUBJECT NUMBER,AGE,DIA,PWV,SV\n1,45,-1,-1,0\n2,45,0,0,0\n3,45,1,2,1\n",
        encoding="utf-8",
    )
    files["haemodynamic_parameters"].write_text(
        "Subject Number,age [years],HR [bpm],SV [ml],CO [l/min],SBP_a [mmHg],DBP_a [mmHg],PP_a [mmHg],"
        "SBP_b [mmHg],DBP_b [mmHg],MBP_b [mmHg],PP_b [mmHg],PP_amp [1]\n"
        "1,45,60,70,4.2,113,79,34,125,79,95,46,1.39\n"
        "2,45,60,70,4.2,113,79,34,125,79,95,46,1.39\n"
        "3,45,60,70,4.2,113,79,34,125,79,95,46,1.39\n",
        encoding="utf-8",
    )
    files["pulse_wave_indices"].write_text(
        "Subject Number,Age,AorticRoot_SBP_V\n1,45,113\n2,45,113\n3,45,113\n",
        encoding="utf-8",
    )
    files["onset_times"].write_text(
        "Subject Number,AorticRoot_P\n1,0\n2,0\n3,0\n",
        encoding="utf-8",
    )
    return files


def test_source_adapter_accepts_canonical_uppercase_model_variation_header(tmp_path: Path) -> None:
    path = tmp_path / "variations.csv"
    path.write_text("SUBJECT NUMBER,AGE,PWV\n1,45,2\n", encoding="utf-8")
    table = HemospaceSubjectCSVTable(path)
    assert table.subject_field == "SUBJECT NUMBER"
    assert table.subject_ids() == ("1",)
    assert table.numeric("1", "PWV").value == 2.0


def test_model_variation_age_is_grouping_information_not_an_sd_axis() -> None:
    item = semantics_for("model_variations", "AGE")
    assert item.canonical_id == "model_variation_age"
    assert item.section == "identity_and_design"
    assert item.unit == "years"


def test_scalar_record_adds_dataset_assumption_and_reconstructs_source_plausibility(tmp_path: Path) -> None:
    files = _write_sources(tmp_path)
    hs = HemospaceSession(_FakeDatasetSession(), lambda artifact_id: files[artifact_id])
    record = hs.record("1")
    by_id = {item.canonical_id: item for item in record.items}
    assert by_id["model_population_sex_assumption"].value == "male"
    assert by_id["model_population_sex_assumption"].evidence == "SOURCE"
    plausibility = by_id["pwdb_physiological_plausibility"]
    assert plausibility.evidence == "RECONSTRUCTED"
    assert isinstance(plausibility.value["plausible"], bool)
    assert "biological_sex" not in {entry.canonical_id for entry in record.unavailable}


def test_phenotype_cohort_selection_is_deterministic(tmp_path: Path) -> None:
    files = _write_sources(tmp_path)
    hs = HemospaceSession(_FakeDatasetSession(), lambda artifact_id: files[artifact_id])
    cohort = hs.select_cohort(
        ["arterial_stiffness_variation>=1", "stroke_volume_variation>=1"],
        profile_id="carotid-stenosis",
    )
    assert cohort.canonical_subject_ids == ("3",)
    assert cohort.count == 1
    assert len(cohort.selection_id) == 64


def test_agent_contract_declares_completion_operations() -> None:
    payload = agent_contract()
    assert payload["record_schema_version"] == "hemospace-1"
    assert set(payload["operations"]) >= {
        "record", "path", "cohort_select", "disease_response", "closure"
    }
    assert "carotid-stenosis" in payload["trial_profiles"]


def test_criterion_parser_is_explicit() -> None:
    criterion = Criterion.parse("arterial_stiffness_variation>=1")
    assert criterion.operator == ">="
    assert criterion.value == 1.0
    assert criterion.matches(2.0) is True
    assert criterion.matches(0.0) is False
