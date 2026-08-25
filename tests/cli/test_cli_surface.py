from __future__ import annotations

import json

from typer.testing import CliRunner

from vascuquest.cli.app import app, _exit_code
from vascuquest.errors import (
    AdmissibilityError,
    CapabilityError,
    DatasetUnavailableError,
    IntegrityError,
    NumericalMethodError,
    PluginCompatibilityError,
    PluginError,
    ReproducibilityError,
    SchemaError,
    SelectionError,
    UnitError,
    VascuQuestInternalError,
)


runner = CliRunner()


def test_frozen_command_tree_and_global_version() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in (
        "dataset",
        "subjects",
        "quantities",
        "locations",
        "get",
        "waveform",
        "derive",
        "model",
        "discover",
        "plugins",
        "export",
        "reproduce",
    ):
        assert name in result.output

    dataset = runner.invoke(app, ["dataset", "--help"])
    assert dataset.exit_code == 0
    for name in ("info", "status", "register", "acquire", "verify", "clean"):
        assert name in dataset.output

    plugins = runner.invoke(app, ["plugins", "--help"])
    assert plugins.exit_code == 0
    assert "list" in plugins.output
    assert "describe" in plugins.output

    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert version.output.strip() == "0.1.0.dev0"


def test_metadata_machine_output_is_clean_and_parseable() -> None:
    info = runner.invoke(app, ["dataset", "info", "--format", "json"])
    assert info.exit_code == 0
    assert info.stderr == ""
    payload = json.loads(info.stdout)
    assert payload["record_id"] == "3275625"
    assert payload["artifact_count"] == 16

    quantities = runner.invoke(app, ["quantities", "--format", "jsonl"])
    assert quantities.exit_code == 0
    assert quantities.stderr == ""
    rows = [json.loads(line) for line in quantities.stdout.splitlines()]
    assert rows
    assert all("canonical_name" in row for row in rows)

    plugins = runner.invoke(app, ["plugins", "list", "--format", "jsonl"])
    assert plugins.exit_code == 0
    assert plugins.stderr == ""
    plugin_rows = [json.loads(line) for line in plugins.stdout.splitlines()]
    ids = {row["qualified_id"] for row in plugin_rows}
    assert "vascuquest:pwdb3275625" in ids
    assert "vascuquest:flow-rate-reconstruction" in ids
    assert "vascuquest:json" in ids
    assert "vascuquest:csv" in ids


def test_plugin_describe_exposes_declared_scientific_contract() -> None:
    result = runner.invoke(
        app,
        [
            "plugins",
            "describe",
            "vascuquest:flow-rate-reconstruction",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["kind"] == "derivation"
    assert payload["qualified_id"] == "vascuquest:flow-rate-reconstruction"
    assert [item["name"] for item in payload["required_inputs"]] == [
        "flow_velocity",
        "luminal_area",
    ]
    assert payload["output_quantity"]["canonical_name"] == "flow_rate"
    assert payload["output_quantity"]["canonical_unit"] == "m^3/s"
    assert payload["output_evidence"] == "RECONSTRUCTED"
    assert payload["parameter_specs"] == []
    assert payload["validation_scope"]
    assert payload["citations"]


def test_usage_and_assignment_syntax_fail_with_code_two() -> None:
    missing = runner.invoke(app, ["get"])
    assert missing.exit_code == 2

    malformed_where = runner.invoke(
        app,
        ["subjects", "--where", "age>=55", "--offline"],
    )
    assert malformed_where.exit_code == 2

    duplicate_parameter = runner.invoke(
        app,
        [
            "derive",
            "vascuquest:flow-rate-reconstruction",
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--param",
            "alpha=1",
            "--param",
            "alpha=2",
        ],
    )
    assert duplicate_parameter.exit_code == 2


def test_stable_public_exception_exit_mapping() -> None:
    assert _exit_code(DatasetUnavailableError("x")) == 3
    assert _exit_code(CapabilityError("x")) == 3
    assert _exit_code(IntegrityError("x")) == 4
    assert _exit_code(SchemaError("x")) == 5
    assert _exit_code(UnitError("x")) == 5
    assert _exit_code(SelectionError("x")) == 5
    assert _exit_code(AdmissibilityError("x")) == 6
    assert _exit_code(NumericalMethodError("x")) == 6
    assert _exit_code(PluginError("x")) == 7
    assert _exit_code(PluginCompatibilityError("x")) == 7
    assert _exit_code(ReproducibilityError("x")) == 8
    assert _exit_code(VascuQuestInternalError("x")) == 70
