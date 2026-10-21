"""Canonical PWDB specialization of the generic remote path reader."""
from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from .remote_path import PWDBRemotePathClient as _BaseClient, RemoteArtifactIdentity


class PWDBRemotePathClient(_BaseClient):
    """PWDB remote client using canonical direct file locators after metadata verification.

    Zenodo API ``files[].links.self`` may identify the file metadata resource rather
    than its binary content. The canonical VascuQuest manifest already declares the
    exact direct file locator, so this specialization verifies filename/checksum/size
    through Zenodo metadata and then uses that manifest locator for byte-range HDF5
    access.
    """

    def verify_remote_identity(self, *, refresh: bool = False) -> Mapping[str, RemoteArtifactIdentity]:
        identities = dict(super().verify_remote_identity(refresh=refresh))
        fixed: dict[str, RemoteArtifactIdentity] = {}
        for artifact_id, identity in identities.items():
            artifact = self.manifest.artifact(artifact_id)
            fixed[artifact_id] = replace(identity, source_url=artifact.source_locator)
        self._identities = fixed
        return dict(fixed)


__all__ = ["PWDBRemotePathClient"]
