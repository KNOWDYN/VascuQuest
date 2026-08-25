from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.request import Request

import numpy as np
import pytest

import vascuquest as vq
from vascuquest.backends.pwdb3275625.http_range import CanonicalRemoteFile
from vascuquest.backends.pwdb3275625.path_backend import PWDB3275625PathBackend
from vascuquest.backends.pwdb3275625.path_reader import (
    PATH_ARTIFACT_SPECS,
    PATH_CAPABILITIES,
    artifact_id_for_path_signal,
)
from vascuquest.bootstrap import _compose_session
from vascuquest.domain import PathPosition, SubjectKey
from vascuquest.errors import CapabilityError, SelectionError
from vascuquest.schema import load_manifest

h5py = pytest.importorskip("h5py")


def _synthetic_path_mat(path: Path) -> tuple[tuple[float, ...], ...]:
    waveforms = (
        (80.0, 81.5, 82.0, 83.25),
        (90.0, 91.0, 92.0),
        (100.0, 99.0, 98.0, 97.0, 96.0),
    )
    with h5py.File(path, "w") as handle:
        data = handle.create_group("data")
        path_waves = data.create_group("path_waves")
        path_waves.create_dataset("fs", data=np.asarray([[500.0]], dtype=np.float64))
        group = path_waves.create_group("aorta_foot")
        distance_refs = group.create_dataset("dist", shape=(4374, 1), dtype=h5py.ref_dtype)
        distances = handle.create_dataset("subject1_distances", data=np.asarray([[0.0, 0.125, 0.250]], dtype=np.float64))
        distance_refs[0, 0] = distances.ref
        signal_refs = group.create_dataset("P", shape=(4374, 1), dtype=h5py.ref_dtype)
        subject_cell = handle.create_dataset("subject1_pressure", shape=(3, 1), dtype=h5py.ref_dtype)
        for index, values in enumerate(waveforms):
            dataset = handle.create_dataset(f"subject1_pressure_position{index}", data=np.asarray([values], dtype=np.float64))
            subject_cell[index, 0] = dataset.ref
        signal_refs[0, 0] = subject_cell.ref
    return waveforms


def _backend(source: Path, derived: Path) -> PWDB3275625PathBackend:
    def resolver(artifact_id: str) -> Path:
        assert artifact_id == "path_aorta_foot_p"
        return source
    return PWDB3275625PathBackend(resolver, derived_root=derived)


class _Response:
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = {} if headers is None else headers
    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)
    def close(self) -> None:
        self._body.close()
    def getcode(self) -> int:
        return self.status


def test_authoritative_path_signal_mapping_matches_six_manifest_capabilities() -> None:
    manifest = load_manifest()
    expected_capabilities = {capability for artifact in manifest.artifacts if artifact.role == "path_resolved_waveform_data" for capability in artifact.capabilities_provided}
    assert PATH_CAPABILITIES == expected_capabilities
    assert set(PATH_ARTIFACT_SPECS) == {"path_aorta_brain", "path_aorta_finger", "path_aorta_foot_a", "path_aorta_foot_p", "path_aorta_foot_u", "path_aorta_rsubclavian"}
    for path_id in ("aorta_brain", "aorta_finger", "aorta_r_subclavian"):
        for signal in ("P", "U", "A"):
            assert artifact_id_for_path_signal(path_id, signal).startswith("path_")
    assert artifact_id_for_path_signal("aorta_foot", "P") == "path_aorta_foot_p"
    assert artifact_id_for_path_signal("aorta_foot", "U") == "path_aorta_foot_u"
    assert artifact_id_for_path_signal("aorta_foot", "A") == "path_aorta_foot_a"
    with pytest.raises(CapabilityError):
        artifact_id_for_path_signal("aorta_foot", "PPG")


def test_path_reader_preserves_exact_values_coordinates_provenance_and_reproduction(tmp_path: Path) -> None:
    source = tmp_path / "pwdb_data_w_aorta_foot_path_p.mat"
    expected = _synthetic_path_mat(source)
    derived = tmp_path / "derived"
    backend = _backend(source, derived)
    session = _compose_session(backend)
    subject = SubjectKey(session.identity, "1")
    result = session.waveform("pressure", subject=subject, location=PathPosition("aorta_foot", 1))
    assert np.asarray(result.values, dtype=np.float64).tobytes() == np.asarray(expected[1], dtype=np.float64).tobytes()
    assert result.quantity.canonical_name == "pressure"
    assert result.canonical_unit == "mmHg"
    assert result.source_unit == "mmHg"
    assert result.evidence is vq.EvidenceClass.SOURCE
    assert result.location == PathPosition("aorta_foot", 1)
    assert result.time_coordinate.values == (0.0, 0.002, 0.004)
    distance = next(item for item in result.coordinates if item.name == "path_distance")
    assert distance.values == 0.125 and distance.unit == "m"
    provenance = backend.provenance(result.provenance_ref)
    assert provenance.location == PathPosition("aorta_foot", 1)
    assert tuple(item.artifact_id for item in provenance.source_artifacts) == ("path_aorta_foot_p",)
    assert provenance.source_artifacts[0].checksum_value == load_manifest().artifact("path_aorta_foot_p").checksum_value
    assert any("derived cache" in assumption for assumption in provenance.assumptions)
    reproduced = session.reproduce(provenance)
    assert np.asarray(reproduced.values, dtype=np.float64).tobytes() == np.asarray(result.values, dtype=np.float64).tobytes()
    assert reproduced.location == result.location


def test_remote_range_path_reader_works_through_h5py_file_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_file = tmp_path / "source.mat"
    expected = _synthetic_path_mat(source_file)
    payload = source_file.read_bytes()
    artifact = load_manifest().artifact("path_aorta_foot_p")
    remote = CanonicalRemoteFile(url=artifact.source_locator, record_id=artifact.canonical_record_id, filename=artifact.filename, checksum_algorithm=artifact.checksum_algorithm, checksum_value=artifact.checksum_value)
    range_requests: list[str] = []

    def opener(request: Request, timeout: int = 0) -> _Response:
        if request.full_url == "https://zenodo.org/api/records/3275625":
            document = {"files": [{"key": artifact.filename, "size": len(payload), "checksum": f"{artifact.checksum_algorithm}:{artifact.checksum_value}"}]}
            return _Response(json.dumps(document).encode("utf-8"), status=200)
        value = request.get_header("Range")
        assert value is not None
        range_requests.append(value)
        start_text, end_text = value.removeprefix("bytes=").split("-", 1)
        start, end = int(start_text), int(end_text)
        return _Response(payload[start : end + 1], status=206, headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"})

    import vascuquest.backends.pwdb3275625.http_range as http_range
    monkeypatch.setattr(http_range, "urlopen", opener)

    def resolver(artifact_id: str):
        assert artifact_id == "path_aorta_foot_p"
        return remote

    backend = PWDB3275625PathBackend(resolver, derived_root=tmp_path / "derived")
    session = _compose_session(backend)
    result = session.waveform("pressure", subject=SubjectKey(session.identity, "1"), location=PathPosition("aorta_foot", 1))
    assert np.asarray(result.values, dtype=np.float64).tobytes() == np.asarray(expected[1], dtype=np.float64).tobytes()
    assert range_requests and all(item.startswith("bytes=") for item in range_requests)
    provenance = backend.provenance(result.provenance_ref)
    assert any("HTTP byte ranges" in item for item in provenance.assumptions)


def test_persistent_subject_cache_bypasses_matlab_reference_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "pwdb_data_w_aorta_foot_path_p.mat"
    expected = _synthetic_path_mat(source)
    derived = tmp_path / "derived"
    first_backend = _backend(source, derived)
    first_session = _compose_session(first_backend)
    subject = SubjectKey(first_session.identity, "1")
    first = first_session.waveform("pressure", subject=subject, location=PathPosition("aorta_foot", 0))
    assert tuple(first.values) == expected[0]
    cache = derived / "pwdb3275625" / "path-waveforms" / "path_aorta_foot_p" / "subject-0001.npz"
    assert cache.is_file()
    import vascuquest.backends.pwdb3275625.path_reader as path_reader
    def forbidden_hdf5_open():
        raise AssertionError("persistent cache hit must not traverse the MATLAB/HDF5 source")
    monkeypatch.setattr(path_reader, "_h5py_module", forbidden_hdf5_open)
    second_backend = _backend(source, derived)
    second_session = _compose_session(second_backend)
    second = second_session.waveform("pressure", subject=SubjectKey(second_session.identity, "1"), location=PathPosition("aorta_foot", 2))
    assert tuple(second.values) == expected[2]
    distance = next(item for item in second.coordinates if item.name == "path_distance")
    assert distance.values == 0.250


def test_path_reader_rejects_non_source_positions_without_interpolation(tmp_path: Path) -> None:
    source = tmp_path / "pwdb_data_w_aorta_foot_path_p.mat"
    _synthetic_path_mat(source)
    backend = _backend(source, tmp_path / "derived")
    session = _compose_session(backend)
    subject = SubjectKey(session.identity, "1")
    with pytest.raises(SelectionError, match="outside the source-supported range"):
        session.waveform("pressure", subject=subject, location=PathPosition("aorta_foot", 3))
