from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from vascuquest.cli import commands
from vascuquest.cli.app import app
from vascuquest.data import DataPaths
from vascuquest.domain.location import MeasurementSite, PathPosition
from vascuquest.schema import load_manifest


runner = CliRunner()


class _NonInteractiveInput:
    def isatty(self) -> bool:
        return False


class _WaveformSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def waveform(self, signal: str, *, subject: str, location: object):
        self.calls.append((signal, subject, location))
        return object()


def test_unknown_acquisition_size_requires_confirmation() -> None:
    manifest = load_manifest()
    artifact = manifest.artifact("path_aorta_foot_p")
    assert artifact.reported_size_bytes is None
    assert commands._requires_confirmation((artifact,)) is True
    assert "unknown" in commands._size_summary((artifact,))


def test_noninteractive_confirmation_requires_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands.sys, "stdin", _NonInteractiveInput())
    with pytest.raises(typer.BadParameter, match="requires --yes"):
        commands._confirm_destructive_or_large("large acquisition", yes=False)

    commands._confirm_destructive_or_large("large acquisition", yes=True)


def test_dataset_clean_deletes_only_selected_managed_namespaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = DataPaths.under(tmp_path / "managed")
    paths.ensure()
    external = tmp_path / "registered-external-source"
    external.mkdir()
    external_file = external / "pwdb_model_configs.csv"
    external_file.write_text("external canonical source must not be touched", encoding="utf-8")
    result_file = paths.results / "kept-result.json"
    result_file.write_text("{}", encoding="utf-8")
    for directory in (paths.derived, paths.work, paths.source):
        (directory / "delete-me").write_text("managed", encoding="utf-8")

    monkeypatch.setattr(
        commands.DataPaths,
        "default",
        classmethod(lambda cls: paths),
    )

    result = runner.invoke(
        app,
        [
            "dataset",
            "clean",
            "--derived",
            "--temporary",
            "--source-cache",
            "--yes",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not paths.derived.exists()
    assert not paths.work.exists()
    assert not paths.source.exists()
    assert result_file.exists()
    assert external_file.read_text(encoding="utf-8") == "external canonical source must not be touched"


def test_dataset_clean_requires_explicit_scope() -> None:
    result = runner.invoke(app, ["dataset", "clean", "--yes"])
    assert result.exit_code == 2


def test_waveform_cli_preserves_named_site_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _WaveformSession()
    monkeypatch.setattr(commands, "_open_session", lambda *args, **kwargs: session)
    monkeypatch.setattr(commands, "_emit", lambda *args, **kwargs: None)

    result = runner.invoke(
        app,
        ["waveform", "pressure", "--subject", "1", "--location", "AorticRoot"],
    )
    assert result.exit_code == 0, result.output
    assert session.calls == [("pressure", "1", MeasurementSite("AorticRoot"))]


def test_waveform_cli_constructs_explicit_path_position(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _WaveformSession()
    monkeypatch.setattr(commands, "_open_session", lambda *args, **kwargs: session)
    monkeypatch.setattr(commands, "_emit", lambda *args, **kwargs: None)

    result = runner.invoke(
        app,
        [
            "waveform",
            "pressure",
            "--subject",
            "1",
            "--path",
            "aorta_foot",
            "--position",
            "2",
        ],
    )
    assert result.exit_code == 0, result.output
    assert session.calls == [("pressure", "1", PathPosition("aorta_foot", 2))]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--subject", "1"],
        ["--subject", "1", "--path", "aorta_foot"],
        ["--subject", "1", "--position", "0"],
        [
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--path",
            "aorta_foot",
            "--position",
            "0",
        ],
    ],
)
def test_waveform_cli_rejects_ambiguous_or_incomplete_location_modes(
    arguments: list[str],
) -> None:
    result = runner.invoke(app, ["waveform", "pressure", *arguments])
    assert result.exit_code == 2
