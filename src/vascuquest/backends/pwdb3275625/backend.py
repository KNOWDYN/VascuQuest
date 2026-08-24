"""PWDB 3275625 lightweight scientific backend."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from vascuquest._version import __version__
from vascuquest.data import ArtifactAcquirer
from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, SegmentLocation, VascularLocation
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, ValueState, Waveform
from vascuquest.domain.subject import VirtualSubject
from vascuquest.errors import CapabilityError, SchemaError, SelectionError
from vascuquest.plugins.descriptor import ComponentDescriptor, ComponentKind, SUPPORTED_PROTOCOL_VERSION
from vascuquest.ports.backend import CapabilitySet, GeometryRequest, QuantityRequest, WaveformRequest
from vascuquest.provenance import ProvenanceBuilder, SourceArtifactReference
from vascuquest.schema import CanonicalManifest, CanonicalQuantitySchema, CanonicalSchema, SourceFieldMapping, load_canonical_schema, load_manifest

from .capabilities import BATCH7_CAPABILITIES, CANONICAL_DOI, CANONICAL_RECORD_ID, DATASET_FAMILY, PWDB_MEASUREMENT_SITE_IDS, PWDB_MEASUREMENT_SITES, artifact_id_for_source_scope
from .csv_reader import SubjectCSVTable
from .geometry_reader import GeometryCSVArchiveReader
from .waveform_reader import WaveformCSVArchiveReader

ArtifactResolver = Callable[[str], Path]

_FIXED_LOCATION_QUANTITIES = {
    "brachial_systolic_pressure": "Brachial",
    "aortic_augmentation_index": "AorticRoot",
}


class PWDB3275625Backend:
    """Canonical backend backed by verified PWDB source artifacts.

    ``artifact_resolver`` is an internal composition seam: it must return a
    verified artifact for the requested canonical manifest ID. Normal callers
    should use :meth:`from_acquirer`.
    """

    __slots__ = (
        "_artifact_resolver", "_schema", "_manifest", "_identity", "_tables",
        "_provenance", "_descriptor", "_geometry_reader", "_waveform_reader",
    )

    def __init__(self, artifact_resolver: ArtifactResolver, *, schema: CanonicalSchema | None = None, manifest: CanonicalManifest | None = None) -> None:
        if not callable(artifact_resolver):
            raise TypeError("artifact_resolver must be callable")
        self._schema = load_canonical_schema() if schema is None else schema
        self._manifest = load_manifest() if manifest is None else manifest
        if not isinstance(self._schema, CanonicalSchema):
            raise TypeError("schema must be a CanonicalSchema")
        if not isinstance(self._manifest, CanonicalManifest):
            raise TypeError("manifest must be a CanonicalManifest")
        if self._schema.dataset_family != DATASET_FAMILY or self._schema.canonical_record_id != CANONICAL_RECORD_ID or self._schema.canonical_doi != CANONICAL_DOI:
            raise SchemaError("PWDB backend requires the canonical record-3275625 schema")
        if self._manifest.canonical_record_id != CANONICAL_RECORD_ID or self._manifest.canonical_doi != CANONICAL_DOI:
            raise SchemaError("PWDB backend requires the canonical record-3275625 manifest")

        self._artifact_resolver = artifact_resolver
        self._identity = DatasetIdentity(dataset_family=DATASET_FAMILY, record_id=CANONICAL_RECORD_ID, persistent_identifier=CANONICAL_DOI, schema_version=self._schema.schema_version)
        self._tables: dict[str, SubjectCSVTable] = {}
        self._provenance: dict[str, object] = {}
        self._geometry_reader: GeometryCSVArchiveReader | None = None
        self._waveform_reader: WaveformCSVArchiveReader | None = None
        self._descriptor = ComponentDescriptor(
            kind=ComponentKind.BACKEND,
            name="PWDB 3275625",
            qualified_id="vascuquest:pwdb3275625",
            implementation_version=__version__,
            protocol_version=SUPPORTED_PROTOCOL_VERSION,
            distribution_name="vascuquest",
            distribution_version=__version__,
            summary="Canonical backend for PWDB Zenodo record 3275625.",
            citations=(f"doi:{CANONICAL_DOI}",),
        )

    @classmethod
    def from_acquirer(cls, acquirer: ArtifactAcquirer, *, offline: bool = False, schema: CanonicalSchema | None = None, manifest: CanonicalManifest | None = None) -> "PWDB3275625Backend":
        """Compose the backend with the verified Batch-5 acquisition layer."""
        if not isinstance(acquirer, ArtifactAcquirer):
            raise TypeError("acquirer must be an ArtifactAcquirer")
        if not isinstance(offline, bool):
            raise TypeError("offline must be a boolean")
        def resolve(artifact_id: str) -> Path:
            return acquirer.acquire(artifact_id, offline=offline)
        return cls(resolve, schema=schema, manifest=manifest)

    @property
    def descriptor(self) -> ComponentDescriptor:
        return self._descriptor

    def identity(self) -> DatasetIdentity:
        return self._identity

    def capabilities(self) -> CapabilitySet:
        return BATCH7_CAPABILITIES

    def subjects(self, request: object | None = None) -> tuple[VirtualSubject, ...]:
        if request is not None:
            raise CapabilityError("subject-query objects are not implemented in Batch 6")
        ids = self._table("model_configurations").subject_ids()
        return tuple(VirtualSubject(SubjectKey(self._identity, subject_id)) for subject_id in ids)

    def locations(self, request: object | None = None) -> tuple[VascularLocation, ...]:
        if request is not None:
            raise CapabilityError("location-query objects are not implemented in Batch 6")
        return PWDB_MEASUREMENT_SITES

    def get_quantity(self, request: QuantityRequest) -> ScientificResult:
        if not isinstance(request, QuantityRequest):
            raise TypeError("request must be a QuantityRequest")
        try:
            quantity_schema = self._schema.quantity_schema(request.quantity)
        except KeyError as exc:
            raise CapabilityError(f"canonical quantity {request.quantity!r} is not defined by schema {self._schema.schema_version}") from exc
        if quantity_schema.category in {"waveform_signal", "geometry_parameter"}:
            raise CapabilityError(f"{request.quantity!r} is not a Batch-6 scalar quantity")

        mapping, resolved_location = self._select_mapping(quantity_schema, request.location)
        table = self._table(mapping.source_scope)
        subject_ids, subject, cohort = self._selection_context(request, table)
        cells = tuple(table.numeric(subject_id, mapping.source_field) for subject_id in subject_ids)
        values = tuple(cell.value for cell in cells)
        missing_count = sum(cell.missing for cell in cells)

        if len(subject_ids) == 1 and subject is not None:
            result_values: object = values[0]
            dimensions: tuple[str, ...] = ()
            coordinates: tuple[Coordinate, ...] = ()
        else:
            result_values = values
            dimensions = ("subject",)
            coordinates = (Coordinate("subject", subject_ids),)

        value_state = ValueState.MISSING if missing_count == len(cells) else ValueState.PRESENT
        warnings = ((f"{missing_count} of {len(cells)} source values are missing",) if 0 < missing_count < len(cells) else ())
        validity = ValidityState.VALID_WITH_WARNING if warnings else ValidityState.NOT_EVALUATED

        artifact_id = artifact_id_for_source_scope(mapping.source_scope)
        provenance = ProvenanceBuilder(self._identity).build(
            evidence=EvidenceClass.SOURCE,
            validity=validity,
            value_state=value_state,
            source_artifacts=(self._artifact_reference(artifact_id),),
            subject=subject,
            cohort=cohort,
            location=resolved_location,
            source_fields=(mapping.source_field,),
            citations=quantity_schema.definition.citations,
            warnings=warnings,
            output_identity=self._output_identity(quantity_schema.definition.canonical_name, resolved_location),
        )
        self._provenance[provenance.record_id] = provenance

        return ScientificResult(
            dataset_identity=self._identity,
            quantity=quantity_schema.definition,
            values=result_values,
            provenance_ref=provenance.record_id,
            dimensions=dimensions,
            coordinates=coordinates,
            source_unit=mapping.source_unit,
            source_label=mapping.source_field,
            subject=subject,
            cohort=cohort,
            location=resolved_location,
            evidence=EvidenceClass.SOURCE,
            value_state=value_state,
            validity=validity,
            warnings=warnings,
        )

    def get_waveform(self, request: WaveformRequest) -> Waveform:
        if not isinstance(request, WaveformRequest):
            raise TypeError("request must be a WaveformRequest")
        self._require_subject_identity(request.subject)
        if not isinstance(request.location, MeasurementSite):
            raise CapabilityError("Batch 7 supports common-site waveforms only; path waveforms require Batch 9")
        if request.location.canonical_site_id not in PWDB_MEASUREMENT_SITE_IDS:
            raise SelectionError(f"unknown PWDB measurement site {request.location.canonical_site_id!r}")

        quantity_schema = self._waveform_quantity(request.signal)
        mapping = quantity_schema.source_mappings[0]
        series = self._get_waveform_reader().read(
            subject_id=request.subject.canonical_subject_id,
            site_id=request.location.canonical_site_id,
            source_signal=mapping.source_field,
        )
        present_count = sum(not missing and not padding for missing, padding in zip(series.missing_mask, series.padding_mask, strict=True))
        missing_count = sum(series.missing_mask)
        value_state = ValueState.PRESENT if present_count else ValueState.MISSING
        warnings = ((f"{missing_count} internal waveform samples are missing",) if missing_count else ())
        validity = ValidityState.VALID_WITH_WARNING if warnings else ValidityState.NOT_EVALUATED
        provenance = ProvenanceBuilder(self._identity).build(
            evidence=EvidenceClass.SOURCE,
            validity=validity,
            value_state=value_state,
            source_artifacts=(self._artifact_reference("common_site_waveforms_csv"),),
            subject=request.subject,
            location=request.location,
            source_fields=(mapping.source_field, series.source_member),
            citations=quantity_schema.definition.citations,
            warnings=warnings,
            output_identity=self._output_identity(quantity_schema.definition.canonical_name, request.location),
        )
        self._provenance[provenance.record_id] = provenance
        return Waveform(
            dataset_identity=self._identity,
            quantity=quantity_schema.definition,
            values=series.values,
            provenance_ref=provenance.record_id,
            dimensions=("time",),
            coordinates=(Coordinate("time", series.time_seconds, unit="s"),),
            source_unit=mapping.source_unit,
            source_label=mapping.source_field,
            subject=request.subject,
            location=request.location,
            evidence=EvidenceClass.SOURCE,
            value_state=value_state,
            validity=validity,
            warnings=warnings,
            missing_mask=series.missing_mask,
            padding_mask=series.padding_mask,
        )

    def geometry(self, request: GeometryRequest) -> ScientificResult:
        if not isinstance(request, GeometryRequest):
            raise TypeError("request must be a GeometryRequest")
        if request.subject is None:
            raise SelectionError("Batch-7 geometry retrieval requires one subject")
        self._require_subject_identity(request.subject)
        if request.location is not None and not isinstance(request.location, SegmentLocation):
            raise SelectionError("geometry location must be a SegmentLocation")

        source = self._get_geometry_reader().read_subject(request.subject.canonical_subject_id)
        values: object
        dimensions: tuple[str, ...]
        coordinates: tuple[Coordinate, ...]
        if isinstance(request.location, SegmentLocation):
            selected = tuple(segment for segment in source.segments if segment.segment_id == request.location.canonical_segment_id)
            if not selected:
                raise SelectionError(f"segment {request.location.canonical_segment_id!r} is absent for subject {request.subject.canonical_subject_id!r}")
            values = selected[0]
            dimensions = ()
            coordinates = ()
        else:
            values = source.segments
            dimensions = ("segment",)
            coordinates = (Coordinate("segment", tuple(segment.segment_id for segment in source.segments)),)

        quantity_schema = self._schema.quantity_schema("vascular_geometry")
        provenance = ProvenanceBuilder(self._identity).build(
            evidence=EvidenceClass.SOURCE,
            validity=ValidityState.NOT_EVALUATED,
            value_state=ValueState.PRESENT,
            source_artifacts=(self._artifact_reference("geometry"),),
            subject=request.subject,
            location=request.location,
            source_fields=("seg_no", "inlet_node", "outlet_node", "length", "inlet_radius", "outlet_radius", "peripheral_c", "peripheral_r", source.source_member),
            citations=quantity_schema.definition.citations,
            output_identity=self._geometry_output_identity(request.location),
        )
        self._provenance[provenance.record_id] = provenance
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=quantity_schema.definition,
            values=values,
            provenance_ref=provenance.record_id,
            dimensions=dimensions,
            coordinates=coordinates,
            source_label=source.source_member,
            subject=request.subject,
            location=request.location,
            evidence=EvidenceClass.SOURCE,
            value_state=ValueState.PRESENT,
            validity=ValidityState.NOT_EVALUATED,
        )

    def _waveform_quantity(self, signal: str) -> CanonicalQuantitySchema:
        try:
            quantity_schema = self._schema.quantity_schema(signal)
        except KeyError:
            matches = tuple(quantity for quantity in self._schema.quantities if quantity.category == "waveform_signal" and signal in quantity.definition.source_aliases)
            if len(matches) != 1:
                raise CapabilityError(f"unknown canonical/common-site waveform signal {signal!r}")
            quantity_schema = matches[0]
        if quantity_schema.category != "waveform_signal":
            raise CapabilityError(f"{signal!r} is not a waveform quantity")
        mappings = tuple(mapping for mapping in quantity_schema.source_mappings if mapping.source_scope == "common_site_waveforms")
        if len(mappings) != 1:
            raise SchemaError(f"waveform quantity {quantity_schema.definition.canonical_name!r} must have exactly one common-site source mapping")
        return CanonicalQuantitySchema(definition=quantity_schema.definition, category=quantity_schema.category, source_mappings=mappings, source_defects=quantity_schema.source_defects)

    def _get_geometry_reader(self) -> GeometryCSVArchiveReader:
        if self._geometry_reader is None:
            path = self._artifact_resolver("geometry")
            if not isinstance(path, Path):
                raise TypeError("artifact_resolver must return pathlib.Path values")
            self._geometry_reader = GeometryCSVArchiveReader(path)
        return self._geometry_reader

    def _get_waveform_reader(self) -> WaveformCSVArchiveReader:
        if self._waveform_reader is None:
            path = self._artifact_resolver("common_site_waveforms_csv")
            if not isinstance(path, Path):
                raise TypeError("artifact_resolver must return pathlib.Path values")
            self._waveform_reader = WaveformCSVArchiveReader(path)
        return self._waveform_reader

    def _geometry_output_identity(self, location: SegmentLocation | None) -> str:
        if location is None:
            return "vascular_geometry"
        return f"vascular_geometry@segment:{location.canonical_segment_id}"

    def provenance(self, record_id: str) -> object:
        """Return a provenance record produced by this backend instance."""
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be a non-empty string")
        try:
            return self._provenance[record_id]
        except KeyError as exc:
            raise KeyError(f"unknown backend provenance record {record_id!r}") from exc

    def _table(self, source_scope: str) -> SubjectCSVTable:
        cached = self._tables.get(source_scope)
        if cached is not None:
            return cached
        artifact_id = artifact_id_for_source_scope(source_scope)
        if source_scope in {"geometry", "common_site_waveforms"}:
            raise CapabilityError(f"{source_scope!r} is not a scalar CSV table")
        path = self._artifact_resolver(artifact_id)
        if not isinstance(path, Path):
            raise TypeError("artifact_resolver must return pathlib.Path values")
        table = SubjectCSVTable(path)
        self._tables[source_scope] = table
        return table

    def _selection_context(self, request: QuantityRequest, table: SubjectCSVTable) -> tuple[tuple[str, ...], SubjectKey | None, Cohort | None]:
        if request.subject is not None:
            self._require_subject_identity(request.subject)
            return ((request.subject.canonical_subject_id,), request.subject, None)
        if request.cohort is not None:
            if request.cohort.dataset_identity != self._identity:
                raise SelectionError("cohort dataset identity does not match PWDB 3275625")
            if not request.cohort.canonical_subject_ids:
                raise SelectionError("empty cohorts cannot produce scalar source results")
            return request.cohort.canonical_subject_ids, None, request.cohort
        return table.subject_ids(), None, None

    def _require_subject_identity(self, subject: SubjectKey) -> None:
        if subject.dataset_identity != self._identity:
            raise SelectionError("subject dataset identity does not match PWDB 3275625")

    def _select_mapping(self, quantity_schema: CanonicalQuantitySchema, location: VascularLocation | None) -> tuple[SourceFieldMapping, MeasurementSite | None]:
        name = quantity_schema.definition.canonical_name
        contexts = quantity_schema.definition.applicable_contexts
        resolved_location: MeasurementSite | None = None
        if "measurement_site" in contexts:
            if not isinstance(location, MeasurementSite):
                raise SelectionError(f"quantity {name!r} requires a MeasurementSite location")
            if location.canonical_site_id not in PWDB_MEASUREMENT_SITE_IDS:
                raise SelectionError(f"unknown PWDB measurement site {location.canonical_site_id!r}")
            resolved_location = location
        elif location is not None:
            raise SelectionError(f"quantity {name!r} does not accept a vascular location")
        fixed_site = _FIXED_LOCATION_QUANTITIES.get(name)
        if fixed_site is not None and (resolved_location is None or resolved_location.canonical_site_id != fixed_site):
            raise SelectionError(f"quantity {name!r} is defined at site {fixed_site!r}")
        mappings = quantity_schema.source_mappings
        if name == "pressure_onset_time":
            assert resolved_location is not None
            expected = f"{resolved_location.canonical_site_id}_P"
            mappings = tuple(mapping for mapping in mappings if mapping.source_field == expected)
        if not mappings:
            raise CapabilityError(f"no implemented source mapping for quantity {name!r} at the requested context")
        return mappings[0], resolved_location

    def _artifact_reference(self, artifact_id: str) -> SourceArtifactReference:
        try:
            artifact = self._manifest.artifact(artifact_id)
        except KeyError as exc:
            raise SchemaError(f"canonical manifest lacks artifact {artifact_id!r}") from exc
        return SourceArtifactReference(artifact_id=artifact.artifact_id, checksum_algorithm=artifact.checksum_algorithm, checksum_value=artifact.checksum_value)

    @staticmethod
    def _output_identity(quantity_name: str, location: MeasurementSite | None) -> str:
        if location is None:
            return quantity_name
        return f"{quantity_name}@site:{location.canonical_site_id}"


__all__ = ["ArtifactResolver", "PWDB3275625Backend"]
