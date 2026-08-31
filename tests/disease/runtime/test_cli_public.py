from __future__ import annotations

import json

from typer.testing import CliRunner

from vascuquest.cli.app import app
import vascuquest.cli.disease_commands as disease_commands


runner = CliRunner()


def test_disease_generate_cli_dispatches_public_api_and_reports_runtime_boundary(
    runtime_dataset,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_generate_population(**kwargs):
        captured.update(kwargs)
        return runtime_dataset

    monkeypatch.setattr(disease_commands, "_preflight_sources", lambda **kwargs: None)
    monkeypatch.setattr(disease_commands, "generate_population", fake_generate_population)

    result = runner.invoke(
        app,
        [
            "disease",
            "generate",
            "large_artery_stiffening",
            "--patients",
            "1",
            "--age",
            "50",
            "--param",
            "target_cfpwv_m_per_s=12.0",
            "--seed",
            "0",
            "--offline",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "MODELLED counterfactual data" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_id"] == runtime_dataset.run_id
    assert payload["canonical_subject_ids"] == ["1"]
    assert payload["storage"] == "runtime_only_process_memory"
    assert payload["bundle_path"] is None
    assert payload["healthy_reconstruction_gate"] == "METRICS_ONLY_THRESHOLDS_NOT_FROZEN"
    assert payload["clinical_validation"] is False
    assert payload["evidence"] == "MODELLED"
    assert payload["unsupported_quantities"] == [
        "aortic_augmentation_index",
        "aortic_pulse_wave_velocity",
        "photoplethysmogram",
        "pressure_onset_time",
    ]
    assert captured["patients"] == 1
    assert captured["age_group"] == 50
    assert captured["condition"].value == "large_artery_stiffening"
    assert captured["parameters"] == {"target_cfpwv_m_per_s": 12.0}
    assert captured["seed"] == 0
    assert captured["offline"] is True


def test_disease_generate_cli_can_explicitly_write_bundle(
    runtime_dataset,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(disease_commands, "_preflight_sources", lambda **kwargs: None)
    monkeypatch.setattr(
        disease_commands,
        "generate_population",
        lambda **kwargs: runtime_dataset,
    )
    bundle = tmp_path / "bundle"
    result = runner.invoke(
        app,
        [
            "disease",
            "generate",
            "large_artery_stiffening",
            "--patients",
            "1",
            "--age",
            "50",
            "--param",
            "target_cfpwv_m_per_s=12",
            "--bundle",
            str(bundle),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["storage"] == "explicit_portable_bundle"
    assert payload["bundle_path"] == str(bundle)
    assert (bundle / "manifest.json").is_file()
