from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from typer.testing import CliRunner

import vascuquest as vq
from vascuquest.bootstrap import _compose_session
from vascuquest.cli.app import app
from vascuquest.cli.rendering import serialize_primary
from vascuquest.domain import (
    Coordinate,
    MeasurementSite,
    ScientificResult,
    SubjectKey,
    VirtualSubject,
    Waveform,
)
from vascuquest.errors import CapabilityError
from vascuquest.exporters import JSONResultExporter, load_result_csv
from vascuquest.methods import (
    FLOW_RATE_RECONSTRUCTION_ID,
    create_flow_rate_reconstruction,
)
from vascuquest.plugins.descriptor import (
    ComponentDescriptor,
    ComponentKind,
    SUPPORTED_PROTOCOL_VERSION,
)
from vascuquest.plugins.registry import PluginRegistry
from vascuquest.ports.backend import GeometryRequest, QuantityRequest, WaveformRequest
from vascuquest.provenance import (
    ProvenanceRecord,
    SourceArtifactReference,
    provenance_to_json,
)
from vascuquest.schema import load_canonical_schema, load_manifest


runner = CliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class _CLIParityBackend:
    def __init__(self) -> None:
        self.schema = load_canonical_schema()
        self._identity = vq.DatasetIdentity(
            dataset_family=self.schema.dataset_family,
            record_id=self.schema.canonical_record_id,
            persistent_identifier=self.schema.canonical_doi,
            schema_version=self.schema.schema_version,
        )
        self._site = MeasurementSite("AorticRoot")
        self._descriptor = ComponentDescriptor(
            kind=ComponentKind.BACKEND,
            name="CLI parity fixture backend",
            qualified_id="tests:cli-parity-backend",
            implementation_version="1",
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="tests",
            distribution_version="1",
            summary="Deterministic fixture proving CLI/API parity without canonical data.",
        )

    @property
    def descriptor(self) -> ComponentDescriptor:
        return self._descriptor

    def identity(self):
        return self._identity

    def capabilities(self):
        return frozenset(
            {
                "subject_model_configuration",
                "geometry",
                "common_site_waveforms:csv",
            }
        )

    def subjects(self, request=None):
        assert request is None
        return tuple(
            VirtualSubject(SubjectKey(self._identity, subject_id))
            for subject_id in ("1", "2")
        )

    def locations(self, request=None):
        assert request is None
        return (self._site,)

    def get_quantity(self, request: QuantityRequest):
        if request.quantity != "age":
            raise CapabilityError(request.quantity)
        values_by_subject = {"1": 25.0, "2": 55.0}
        if request.subject is not None:
            return ScientificResult(
                dataset_identity=self._identity,
                quantity=self.schema.quantity("age"),
                values=values_by_subject[request.subject.canonical_subject_id],
                provenance_ref="cli:age",
                subject=request.subject,
            )
        ids = (
            request.cohort.canonical_subject_ids
            if request.cohort is not None
            else ("1", "2")
        )
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=self.schema.quantity("age"),
            values=tuple(values_by_subject[item] for item in ids),
            provenance_ref="cli:age-cohort",
            dimensions=("subject",),
            coordinates=(Coordinate("subject", ids),),
            cohort=request.cohort,
        )

    def get_waveform(self, request: WaveformRequest):
        values = {
            "pressure": (80.0, 120.0, 90.0),
            "flow_velocity": (1.0, 2.0, -1.0),
            "luminal_area": (0.01, 0.02, 0.03),
        }.get(request.signal)
        if values is None:
            raise CapabilityError(request.signal)
        return Waveform(
            dataset_identity=self._identity,
            quantity=self.schema.quantity(request.signal),
            values=np.asarray(values, dtype=float),
            provenance_ref=f"cli:{request.signal}",
            dimensions=("time",),
            coordinates=(
                Coordinate("time", np.asarray((0.0, 0.002, 0.004)), unit="s"),
            ),
            subject=request.subject,
            location=request.location,
        )

    def geometry(self, request: GeometryRequest):
        if request.subject is None:
            raise CapabilityError("geometry requires one subject")
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=self.schema.quantity("vascular_geometry"),
            values=(("1", 0.1),),
            provenance_ref="cli:geometry",
            dimensions=("segment",),
            coordinates=(Coordinate("segment", ("1",)),),
            subject=request.subject,
            location=request.location,
        )


def _session():
    backend = _CLIParityBackend()
    registry = PluginRegistry()
    registry.register_factory(
        lambda: backend,
        expected_kind=ComponentKind.BACKEND,
        built_in=True,
    )
    registry.register_factory(
        create_flow_rate_reconstruction,
        expected_kind=ComponentKind.DERIVATION,
        built_in=True,
    )
    return _compose_session(backend, registry=registry)


def _json(value: str) -> object:
    return json.loads(value)


def _strip_ansi(value: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", value)


def test_cli_get_waveform_geometry_and_derive_match_python_api(monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr(vq, "open_dataset", lambda *args, **kwargs: session)

    direct_age = session.get("age", subjects="1")
    cli_age = runner.invoke(app, ["get", "age", "--subject", "1", "--format", "json"])
    assert cli_age.exit_code == 0, cli_age.output
    assert _json(cli_age.stdout) == _json(serialize_primary(direct_age, "json"))

    direct_waveform = session.waveform(
        "pressure",
        subject="1",
        location=MeasurementSite("AorticRoot"),
    )
    cli_waveform = runner.invoke(
        app,
        [
            "waveform",
            "pressure",
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--format",
            "json",
        ],
    )
    assert cli_waveform.exit_code == 0, cli_waveform.output
    assert _json(cli_waveform.stdout) == _json(serialize_primary(direct_waveform, "json"))

    direct_geometry = session.geometry(subject="1")
    cli_geometry = runner.invoke(
        app,
        ["get", "vascular_geometry", "--subject", "1", "--format", "json"],
    )
    assert cli_geometry.exit_code == 0, cli_geometry.output
    assert _json(cli_geometry.stdout) == _json(serialize_primary(direct_geometry, "json"))

    direct_flow = session.derive(
        FLOW_RATE_RECONSTRUCTION_ID,
        subjects="1",
        location=MeasurementSite("AorticRoot"),
    )
    cli_flow = runner.invoke(
        app,
        [
            "derive",
            FLOW_RATE_RECONSTRUCTION_ID,
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--format",
            "json",
        ],
    )
    assert cli_flow.exit_code == 0, cli_flow.output
    assert _json(cli_flow.stdout) == _json(serialize_primary(direct_flow, "json"))


def test_cli_exact_match_subject_selection_matches_python(monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr(vq, "open_dataset", lambda *args, **kwargs: session)
    direct_ids = [item.canonical_subject_id for item in session.subjects(where={"age": 55.0})]
    result = runner.invoke(
        app,
        ["subjects", "--where", "age=55.0", "--format", "jsonl"],
    )
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    cli_ids = [json.loads(line)["canonical_subject_id"] for line in result.stdout.splitlines()]
    assert cli_ids == direct_ids == ["2"]


def test_cli_export_round_trip_uses_registered_exporter(tmp_path: Path) -> None:
    session = vq.open_dataset(offline=True)
    result = ScientificResult(
        dataset_identity=session.identity,
        quantity=load_canonical_schema().quantity("age"),
        values=np.asarray((25.0, 55.0)),
        provenance_ref="cli-export-fixture",
        dimensions=("subject",),
        coordinates=(Coordinate("subject", ("1", "2")),),
    )
    source = tmp_path / "source.json"
    JSONResultExporter().export(result, source, {})
    destination = tmp_path / "result.csv"

    exported = runner.invoke(
        app,
        [
            "export",
            str(source),
            "--exporter",
            "vascuquest:csv",
            "--output",
            str(destination),
            "--format",
            "json",
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert destination.exists()
    assert destination.with_suffix(".csv.meta.json").exists()
    rebuilt = load_result_csv(destination)
    assert rebuilt.dataset_identity == result.dataset_identity
    assert rebuilt.quantity == result.quantity
    np.testing.assert_allclose(rebuilt.values, result.values)


def test_cli_reproduce_matches_python_source_reproduction(tmp_path: Path, monkeypatch) -> None:
    session = _session()
    monkeypatch.setattr(vq, "open_dataset", lambda *args, **kwargs: session)
    artifact = load_manifest().artifact("model_configurations")
    provenance = ProvenanceRecord(
        record_id="cli-source-age-1",
        dataset_identity=session.identity,
        schema_version=session.identity.schema_version,
        evidence=vq.EvidenceClass.SOURCE,
        source_artifacts=(
            SourceArtifactReference(
                artifact_id=artifact.artifact_id,
                checksum_algorithm=artifact.checksum_algorithm,
                checksum_value=artifact.checksum_value,
            ),
        ),
        subject=SubjectKey(session.identity, "1"),
        output_identity="age",
    )
    provenance_path = tmp_path / "provenance.json"
    provenance_path.write_text(provenance_to_json(provenance), encoding="utf-8")

    direct = session.reproduce(provenance)
    cli = runner.invoke(
        app,
        ["reproduce", str(provenance_path), "--format", "json"],
    )
    assert cli.exit_code == 0, cli.output
    assert _json(cli.stdout) == _json(serialize_primary(direct, "json"))


def _isolated_environment(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    return env


def test_installed_cli_error_boundary_preserves_stdout_and_exit_codes(tmp_path: Path) -> None:
    env = _isolated_environment(tmp_path)
    unavailable = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "waveform",
            "pressure",
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--offline",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert unavailable.returncode == 3
    assert unavailable.stdout == ""
    assert "DatasetUnavailableError" in unavailable.stderr
    assert "Traceback" not in unavailable.stderr

    debug = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "--debug",
            "waveform",
            "pressure",
            "--subject",
            "1",
            "--location",
            "AorticRoot",
            "--offline",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert debug.returncode == 3
    assert debug.stdout == ""
    assert "Traceback" in debug.stderr

    plugin = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "model",
            "missing:operator",
            "--subject",
            "1",
            "--offline",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert plugin.returncode == 7
    assert plugin.stdout == ""
    assert "PluginError" in plugin.stderr

    bad_source = tmp_path / "bad-source"
    bad_source.mkdir()
    (bad_source / "pwdb_model_configs.csv").write_text("not canonical", encoding="utf-8")
    integrity = subprocess.run(
        [sys.executable, "-m", "vascuquest", "dataset", "register", str(bad_source)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert integrity.returncode == 4
    assert integrity.stdout == ""
    assert "IntegrityError" in integrity.stderr


def test_installed_acquire_guard_never_prompts_noninteractively(tmp_path: Path) -> None:
    env = _isolated_environment(tmp_path)
    guarded = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "dataset",
            "acquire",
            "--artifact",
            "model_configurations",
            "--offline",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert guarded.returncode == 2
    assert guarded.stdout == ""
    plain_stderr = _strip_ansi(guarded.stderr)
    assert "requires --yes" in plain_stderr
    assert "Acquisition plan:" in plain_stderr

    missing_source = subprocess.run(
        [
            sys.executable,
            "-m",
            "vascuquest",
            "dataset",
            "acquire",
            "--artifact",
            "model_configurations",
            "--source",
            str(tmp_path / "does-not-exist"),
            "--yes",
            "--offline",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert missing_source.returncode == 3
    assert missing_source.stdout == ""
    assert "DatasetUnavailableError" in missing_source.stderr
