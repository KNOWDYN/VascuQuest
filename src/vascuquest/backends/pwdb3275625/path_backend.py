"""Batch-9 path-resolved extension of the canonical PWDB backend."""

from __future__ import annotations

from pathlib import Path

from vascuquest.data import ArtifactAcquirer, DataPaths
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.location import PathPosition
from vascuquest.domain.result import Coordinate, ValidityState, ValueState, Waveform
from vascuquest.errors import SchemaError
from vascuquest.ports.backend import CapabilitySet, WaveformRequest
from vascuquest.schema import CanonicalManifest, CanonicalSchema, load_manifest

from .backend import ArtifactResolver, PWDB3275625Backend
from .http_range import CanonicalRemoteFile
from .path_reader import (
    PATH_ARTIFACT_SPECS,
    PATH_CAPABILITIES,
    PathWaveformReader,
    artifact_id_for_path_signal,
)

_PATH_CACHE_PROVENANCE = (
    "runtime path access may use a rebuildable exact-fidelity derived cache keyed "
    "to the canonical artifact checksum; the canonical PWDB artifact remains the source"
)
_REMOTE_RANGE_PROVENANCE = (
    "large canonical PWDB path artifacts may be accessed through bounded HTTP byte ranges "
    "after Zenodo record metadata is matched to the manifest-pinned filename, size and checksum; "
    "the full remote file is not rehashed on every sparse read"
)


class PWDB3275625PathBackend(PWDB3275625Backend):
    """Canonical PWDB backend with production path-position waveform access."""

    __slots__ = ("_derived_root", "_path_readers")

    def __init__(
        self,
        artifact_resolver: ArtifactResolver,
        *,
        schema: CanonicalSchema | None = None,
        manifest: CanonicalManifest | None = None,
        derived_root: Path | None = None,
    ) -> None:
        super().__init__(artifact_resolver, schema=schema, manifest=manifest)
        resolved_root = DataPaths.default().derived if derived_root is None else derived_root
        if not isinstance(resolved_root, Path):
            raise TypeError("derived_root must be a pathlib.Path or None")
        self._derived_root = resolved_root
        self._path_readers: dict[str, PathWaveformReader] = {}

    @classmethod
    def from_acquirer(
        cls,
        acquirer: ArtifactAcquirer,
        *,
        offline: bool = False,
        schema: CanonicalSchema | None = None,
        manifest: CanonicalManifest | None = None,
    ) -> "PWDB3275625PathBackend":
        """Compose local-first path access without forcing giant network downloads."""

        if not isinstance(acquirer, ArtifactAcquirer):
            raise TypeError("acquirer must be an ArtifactAcquirer")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        resolved_manifest = load_manifest() if manifest is None else manifest
        if not isinstance(resolved_manifest, CanonicalManifest):
            raise TypeError("manifest must be a CanonicalManifest")

        def resolve(artifact_id: str):
            if artifact_id in PATH_ARTIFACT_SPECS:
                local = acquirer.resolve_local(artifact_id)
                if local is not None:
                    return local
                if offline:
                    return acquirer.acquire(artifact_id, offline=True)
                artifact = resolved_manifest.artifact(artifact_id)
                return CanonicalRemoteFile(
                    url=artifact.source_locator,
                    record_id=artifact.canonical_record_id,
                    filename=artifact.filename,
                    checksum_algorithm=artifact.checksum_algorithm,
                    checksum_value=artifact.checksum_value,
                )
            return acquirer.acquire(artifact_id, offline=offline)

        return cls(resolve, schema=schema, manifest=resolved_manifest)

    def capabilities(self) -> CapabilitySet:
        return super().capabilities() | PATH_CAPABILITIES

    def get_waveform(self, request: WaveformRequest) -> Waveform:
        if not isinstance(request, WaveformRequest):
            raise TypeError("request must be a WaveformRequest")
        if not isinstance(request.location, PathPosition):
            return super().get_waveform(request)

        self._require_subject_identity(request.subject)
        quantity_schema = self._waveform_quantity(request.signal)
        mapping = quantity_schema.source_mappings[0]
        source_signal = mapping.source_field
        artifact_id = artifact_id_for_path_signal(
            request.location.canonical_path_id,
            source_signal,
        )
        reader = self._path_reader(artifact_id)
        series = reader.read(
            subject_id=request.subject.canonical_subject_id,
            source_signal=source_signal,
            position_index=request.location.position_index,
        )

        present_count = sum(not missing for missing in series.missing_mask)
        missing_count = sum(series.missing_mask)
        value_state = ValueState.PRESENT if present_count else ValueState.MISSING
        warnings = (
            (f"{missing_count} internal path-waveform samples are missing",)
            if missing_count
            else ()
        )
        validity = ValidityState.VALID_WITH_WARNING if warnings else ValidityState.NOT_EVALUATED
        assumptions = [_PATH_CACHE_PROVENANCE]
        if series.source_access_mode == "zenodo_manifest_pinned_http_range":
            assumptions.append(_REMOTE_RANGE_PROVENANCE)
        provenance = self._provenance_builder().build(
            evidence=EvidenceClass.SOURCE,
            validity=validity,
            value_state=value_state,
            source_artifacts=(self._artifact_reference(artifact_id),),
            subject=request.subject,
            location=request.location,
            source_fields=(source_signal, series.source_dataset, series.distance_dataset),
            assumptions=tuple(assumptions),
            citations=quantity_schema.definition.citations,
            warnings=warnings,
            output_identity=(
                f"{quantity_schema.definition.canonical_name}@path:"
                f"{request.location.canonical_path_id}[{request.location.position_index}]"
            ),
        )
        self._provenance[provenance.record_id] = provenance

        return Waveform(
            dataset_identity=self._identity,
            quantity=quantity_schema.definition,
            values=series.values,
            provenance_ref=provenance.record_id,
            dimensions=("time",),
            coordinates=(
                Coordinate("time", series.time_seconds, unit="s"),
                Coordinate("path_distance", series.path_distance_m, unit="m"),
            ),
            source_unit=mapping.source_unit,
            source_label=source_signal,
            subject=request.subject,
            location=request.location,
            evidence=EvidenceClass.SOURCE,
            value_state=value_state,
            validity=validity,
            warnings=warnings,
            missing_mask=series.missing_mask,
            padding_mask=series.padding_mask,
        )

    def _path_reader(self, artifact_id: str) -> PathWaveformReader:
        cached = self._path_readers.get(artifact_id)
        if cached is not None:
            return cached
        try:
            spec = PATH_ARTIFACT_SPECS[artifact_id]
        except KeyError as exc:
            raise SchemaError(f"unknown PWDB path artifact {artifact_id!r}") from exc
        source = self._artifact_resolver(artifact_id)
        if not isinstance(source, (Path, CanonicalRemoteFile)):
            raise TypeError("path artifact resolver must return pathlib.Path or CanonicalRemoteFile values")
        try:
            artifact = self._manifest.artifact(artifact_id)
        except KeyError as exc:
            raise SchemaError(f"canonical manifest lacks path artifact {artifact_id!r}") from exc
        reader = PathWaveformReader(
            source,
            self._derived_root,
            spec,
            source_checksum=artifact.checksum_value,
        )
        self._path_readers[artifact_id] = reader
        return reader

    def _provenance_builder(self):
        """Return the backend's canonical provenance builder without changing its environment."""
        from vascuquest.provenance import ProvenanceBuilder

        return ProvenanceBuilder(self._identity)


__all__ = ["PWDB3275625PathBackend"]
