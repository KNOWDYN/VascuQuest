"""Contract tests for managed paths, artifact states, integrity, and source precedence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vascuquest.data import (
    ArtifactState,
    DataPaths,
    SourceKind,
    SourceRegistry,
    compute_checksum,
    probe_artifact,
    require_verified_artifact,
    verify_artifact,
)
from vascuquest.errors import IntegrityError
from vascuquest.schema import ArtifactManifestEntry


def _artifact(
    payload: bytes = b"canonical-bytes",
    *,
    reported_size_bytes: int | None = None,
) -> ArtifactManifestEntry:
    return ArtifactManifestEntry(
        artifact_id="synthetic_artifact",
        filename="synthetic.bin",
        canonical_record_id="3275625",
        canonical_doi="10.5281/zenodo.3275625",
        role="generated_contract_fixture",
        reported_size_bytes=reported_size_bytes,
        checksum_algorithm="md5",
        checksum_value=hashlib.md5(payload).hexdigest(),
        source_locator="https://example.invalid/synthetic.bin",
        container_format="binary",
        compression=None,
        capabilities_provided=("synthetic",),
    )


def test_managed_paths_keep_persistence_namespaces_separate(tmp_path: Path) -> None:
    paths = DataPaths.under(tmp_path)
    paths.ensure()

    assert len({paths.source, paths.work, paths.derived, paths.results, paths.state}) == 5
    assert all(path.is_dir() for path in (paths.source, paths.work, paths.derived, paths.results, paths.state))
    assert paths.source_artifact("PWs_csv.zip") == paths.source / "PWs_csv.zip"
    assert paths.incomplete_download("PWs_csv.zip").name == "PWs_csv.zip.part"

    for unsafe in ("../escape", "sub/file", "sub\\file", ".", ".."):
        with pytest.raises(ValueError):
            paths.source_artifact(unsafe)


def test_artifact_state_has_exact_five_contract_values() -> None:
    assert tuple(state.value for state in ArtifactState) == (
        "missing",
        "present_unverified",
        "verified",
        "checksum_failed",
        "unreadable",
    )


def test_probe_never_treats_presence_as_verification(tmp_path: Path) -> None:
    artifact = _artifact()
    path = tmp_path / artifact.filename

    missing = probe_artifact(path, artifact)
    assert missing.state is ArtifactState.MISSING
    assert not missing.usable_as_canonical_source

    path.write_bytes(b"canonical-bytes")
    present = probe_artifact(path, artifact)
    assert present.state is ArtifactState.PRESENT_UNVERIFIED
    assert not present.usable_as_canonical_source


def test_streaming_checksum_and_verification_use_manifest_identity(tmp_path: Path) -> None:
    payload = b"0123456789" * 100
    artifact = _artifact(payload)
    path = tmp_path / artifact.filename
    path.write_bytes(payload)

    assert compute_checksum(path, "md5", chunk_size=7) == hashlib.md5(payload).hexdigest()
    inspection = verify_artifact(path, artifact, chunk_size=11)
    assert inspection.state is ArtifactState.VERIFIED
    assert inspection.observed_checksum == artifact.checksum_value
    assert require_verified_artifact(path, artifact) == path

    path.write_bytes(payload + b"tampered")
    failed = verify_artifact(path, artifact)
    assert failed.state is ArtifactState.CHECKSUM_FAILED
    assert not failed.usable_as_canonical_source
    with pytest.raises(IntegrityError):
        require_verified_artifact(path, artifact)


def test_exact_reported_size_is_checked_when_present(tmp_path: Path) -> None:
    payload = b"abc"
    artifact = _artifact(payload, reported_size_bytes=4)
    path = tmp_path / artifact.filename
    path.write_bytes(payload)

    inspection = verify_artifact(path, artifact)
    assert inspection.state is ArtifactState.CHECKSUM_FAILED
    assert inspection.observed_checksum is None
    assert inspection.detail is not None and "size mismatch" in inspection.detail


def test_non_file_source_path_is_unreadable(tmp_path: Path) -> None:
    artifact = _artifact()
    path = tmp_path / artifact.filename
    path.mkdir()
    inspection = probe_artifact(path, artifact)
    assert inspection.state is ArtifactState.UNREADABLE


def test_source_registry_persists_without_modifying_external_source(tmp_path: Path) -> None:
    paths = DataPaths.under(tmp_path / "managed")
    paths.ensure()
    external = tmp_path / "external"
    external.mkdir()
    source_file = external / "synthetic.bin"
    source_file.write_bytes(b"canonical-bytes")
    before = source_file.read_bytes()

    state_file = paths.state_file("sources.json")
    registry = SourceRegistry(state_file)
    assert registry.register_local(external) == external.resolve()
    assert registry.register_mirror("https://mirror.example.test/pwdb/") == "https://mirror.example.test/pwdb"

    assert source_file.read_bytes() == before
    reloaded = SourceRegistry(state_file)
    assert reloaded.local_roots == (external.resolve(),)
    assert reloaded.mirrors == ("https://mirror.example.test/pwdb",)


def test_source_candidates_follow_frozen_precedence_and_offline_rule(tmp_path: Path) -> None:
    paths = DataPaths.under(tmp_path / "managed")
    paths.ensure()
    external = tmp_path / "external"
    external.mkdir()
    registry = SourceRegistry(paths.state_file("sources.json"))
    registry.register_local(external)
    registry.register_mirror("https://mirror.example.test/pwdb")
    artifact = _artifact()

    online = registry.candidates(artifact, paths, offline=False)
    assert tuple(candidate.kind for candidate in online) == (
        SourceKind.REGISTERED_LOCAL,
        SourceKind.VERIFIED_CACHE,
        SourceKind.MIRROR,
        SourceKind.CANONICAL,
    )
    assert online[0].local_path == external.resolve() / artifact.filename
    assert online[1].local_path == paths.source_artifact(artifact.filename)
    assert online[2].locator == "https://mirror.example.test/pwdb/synthetic.bin"
    assert online[3].locator == artifact.source_locator

    offline = registry.candidates(artifact, paths, offline=True)
    assert tuple(candidate.kind for candidate in offline) == (
        SourceKind.REGISTERED_LOCAL,
        SourceKind.VERIFIED_CACHE,
    )


def test_corrupted_registry_state_cannot_reintroduce_unsafe_sources(tmp_path: Path) -> None:
    state_file = tmp_path / "sources.json"
    state_file.write_text(
        json.dumps(
            {
                "format_version": 1,
                "local_roots": ["relative/path"],
                "mirrors": ["http://not-secure.example.test"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        SourceRegistry(state_file)
