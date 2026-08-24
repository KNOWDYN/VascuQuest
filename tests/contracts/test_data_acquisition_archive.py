"""Contract tests for streamed acquisition and safe ZIP extraction."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import stat
from urllib.error import URLError
import zipfile

import pytest

from vascuquest.data import ArtifactAcquirer, DataPaths, SourceRegistry, safe_extract_zip
from vascuquest.errors import DatasetUnavailableError, IntegrityError
from vascuquest.schema import ArtifactManifestEntry, CanonicalManifest


def _artifact(payload: bytes = b"canonical-download") -> ArtifactManifestEntry:
    return ArtifactManifestEntry(
        artifact_id="synthetic_artifact",
        filename="synthetic.bin",
        canonical_record_id="3275625",
        canonical_doi="10.5281/zenodo.3275625",
        role="generated_contract_fixture",
        reported_size_bytes=len(payload),
        checksum_algorithm="md5",
        checksum_value=hashlib.md5(payload).hexdigest(),
        source_locator="https://canonical.example.test/synthetic.bin",
        container_format="binary",
        compression=None,
        capabilities_provided=("synthetic",),
    )


def _manifest(artifact: ArtifactManifestEntry) -> CanonicalManifest:
    return CanonicalManifest(
        manifest_version=1,
        canonical_record_id="3275625",
        canonical_doi="10.5281/zenodo.3275625",
        canonical_record_url="https://zenodo.org/records/3275625",
        artifacts=(artifact,),
    )


class _Response:
    def __init__(self, payload: bytes, *, fail_on_read: int | None = None) -> None:
        self._buffer = io.BytesIO(payload)
        self._reads = 0
        self._fail_on_read = fail_on_read
        self.closed = False

    def read(self, size: int) -> bytes:
        self._reads += 1
        if self._fail_on_read is not None and self._reads == self._fail_on_read:
            raise OSError("interrupted transfer")
        return self._buffer.read(size)

    def close(self) -> None:
        self.closed = True
        self._buffer.close()


def _acquirer(
    tmp_path: Path,
    artifact: ArtifactManifestEntry,
    opener,
) -> tuple[ArtifactAcquirer, DataPaths, SourceRegistry]:
    paths = DataPaths.under(tmp_path / "managed")
    paths.ensure()
    registry = SourceRegistry(paths.state_file("sources.json"))
    return (
        ArtifactAcquirer(
            paths,
            registry,
            manifest=_manifest(artifact),
            opener=opener,
            chunk_size=4,
        ),
        paths,
        registry,
    )


def test_registered_verified_local_source_is_used_without_copy_or_network(tmp_path: Path) -> None:
    payload = b"canonical-download"
    artifact = _artifact(payload)

    def forbidden_opener(url: str):
        raise AssertionError(f"network must not be used: {url}")

    acquirer, paths, registry = _acquirer(tmp_path, artifact, forbidden_opener)
    external = tmp_path / "external"
    external.mkdir()
    source = external / artifact.filename
    source.write_bytes(payload)
    registry.register_local(external)

    resolved = acquirer.acquire(artifact.artifact_id, offline=True)
    assert resolved == source.resolve()
    assert resolved.read_bytes() == payload
    assert not paths.source_artifact(artifact.filename).exists()


def test_offline_mode_never_invokes_network_when_artifact_is_missing(tmp_path: Path) -> None:
    artifact = _artifact()
    calls: list[str] = []

    def opener(url: str):
        calls.append(url)
        return _Response(b"canonical-download")

    acquirer, _, _ = _acquirer(tmp_path, artifact, opener)
    with pytest.raises(DatasetUnavailableError):
        acquirer.acquire(artifact.artifact_id, offline=True)
    assert calls == []


def test_successful_network_acquisition_streams_verifies_and_atomically_promotes(tmp_path: Path) -> None:
    payload = b"canonical-download"
    artifact = _artifact(payload)
    calls: list[str] = []

    def opener(url: str):
        calls.append(url)
        return _Response(payload)

    acquirer, paths, _ = _acquirer(tmp_path, artifact, opener)
    resolved = acquirer.acquire(artifact.artifact_id)

    assert resolved == paths.source_artifact(artifact.filename)
    assert resolved.read_bytes() == payload
    assert calls == [artifact.source_locator]
    assert list(paths.work.iterdir()) == []


def test_network_checksum_failure_is_never_promoted(tmp_path: Path) -> None:
    artifact = _artifact(b"canonical-download")

    def opener(url: str):
        return _Response(b"wrong-bytes")

    acquirer, paths, _ = _acquirer(tmp_path, artifact, opener)
    with pytest.raises(IntegrityError):
        acquirer.acquire(artifact.artifact_id)

    assert not paths.source_artifact(artifact.filename).exists()
    assert list(paths.work.iterdir()) == []


def test_interrupted_download_remains_incomplete_and_is_cleaned(tmp_path: Path) -> None:
    artifact = _artifact(b"canonical-download")

    def opener(url: str):
        return _Response(b"canonical-download", fail_on_read=2)

    acquirer, paths, _ = _acquirer(tmp_path, artifact, opener)
    with pytest.raises(DatasetUnavailableError):
        acquirer.acquire(artifact.artifact_id)

    assert not paths.source_artifact(artifact.filename).exists()
    assert list(paths.work.iterdir()) == []


def test_mirror_network_failure_falls_back_to_canonical_source(tmp_path: Path) -> None:
    payload = b"canonical-download"
    artifact = _artifact(payload)
    calls: list[str] = []

    def opener(url: str):
        calls.append(url)
        if url.startswith("https://mirror.example.test/"):
            raise URLError("mirror unavailable")
        return _Response(payload)

    acquirer, paths, registry = _acquirer(tmp_path, artifact, opener)
    registry.register_mirror("https://mirror.example.test/pwdb")
    resolved = acquirer.acquire(artifact.artifact_id)

    assert resolved == paths.source_artifact(artifact.filename)
    assert calls == [
        "https://mirror.example.test/pwdb/synthetic.bin",
        artifact.source_locator,
    ]


def test_valid_zip_extraction_is_repeatable_and_preserves_source_archive(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("folder/a.txt", b"alpha")
        handle.writestr("b.txt", b"beta")

    destination = tmp_path / "derived"
    first = safe_extract_zip(archive, destination)
    second = safe_extract_zip(archive, destination)

    assert {path.relative_to(destination).as_posix() for path in first} == {"folder/a.txt", "b.txt"}
    assert {path.relative_to(destination).as_posix() for path in second} == {"folder/a.txt", "b.txt"}
    assert (destination / "folder/a.txt").read_bytes() == b"alpha"
    assert (destination / "b.txt").read_bytes() == b"beta"
    assert not (destination / ".vascuquest-extraction-incomplete").exists()
    assert archive.exists()


@pytest.mark.parametrize(
    "member_name",
    ["../escape.txt", "/absolute.txt", "C:/drive.txt", "folder\\escape.txt"],
)
def test_zip_path_traversal_and_absolute_members_are_rejected(
    tmp_path: Path,
    member_name: str,
) -> None:
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(member_name, b"bad")

    destination = tmp_path / "derived"
    with pytest.raises(IntegrityError):
        safe_extract_zip(archive, destination)

    assert (destination / ".vascuquest-extraction-incomplete").exists()
    assert not (tmp_path / "escape.txt").exists()
    assert archive.exists()


def test_zip_symbolic_link_member_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(info, "../outside")

    destination = tmp_path / "derived"
    with pytest.raises(IntegrityError):
        safe_extract_zip(archive, destination)
    assert (destination / ".vascuquest-extraction-incomplete").exists()


def test_selective_zip_extraction_requires_requested_member_to_exist(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("a.txt", b"alpha")
        handle.writestr("b.txt", b"beta")

    destination = tmp_path / "derived"
    extracted = safe_extract_zip(archive, destination, members=("a.txt",))
    assert tuple(path.name for path in extracted) == ("a.txt",)
    assert not (destination / "b.txt").exists()

    failed_destination = tmp_path / "failed"
    with pytest.raises(IntegrityError):
        safe_extract_zip(archive, failed_destination, members=("missing.txt",))
    assert (failed_destination / ".vascuquest-extraction-incomplete").exists()
