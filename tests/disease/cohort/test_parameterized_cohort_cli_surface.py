from __future__ import annotations

from typer.testing import CliRunner

from vascuquest.cli.app import app


runner = CliRunner()


def test_parameterized_disease_cohort_cli_group_is_additive_and_complete():
    result = runner.invoke(app, ["disease", "cohort", "--help"])
    assert result.exit_code == 0, result.output
    for command in ("plan", "generate", "inspect", "verify"):
        assert command in result.output


def test_existing_virtual_disease_cli_commands_remain_present():
    result = runner.invoke(app, ["disease", "--help"])
    assert result.exit_code == 0, result.output
    for command in ("presets", "describe", "generate", "cohort"):
        assert command in result.output
