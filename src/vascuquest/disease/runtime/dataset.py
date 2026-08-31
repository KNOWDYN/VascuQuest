"""In-memory VascuQuest-compatible dataset facade for one Virtual Disease run."""

from __future__ import annotations

from collections.abc import Iterable

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.evidence import EvidenceClass
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import MeasurementSite, SegmentLocation, VascularLocation
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import Coordinate, ScientificResult, ValidityState, ValueState, Waveform
from vascuquest.domain.subject import VirtualSubject
from vascuquest.disease.model import DiseaseQuantityStatus, DiseaseRunIdentity
from vascuquest.errors import CapabilityError, SelectionError
from vascuquest.provenance import ProvenanceBuilder, ProvenanceRecord

from .identity import runtime_dataset_identity
from .materialize import RuntimeSubjectState
from .provenance import RUNTIME_METHOD_ID, runtime_component
from .quantities import canonical_quantity

_SIGNAL_ALIASES = {
    "P": "pressure",
    "pressure": "pressure",
    "U": "flow_velocity",
    "flow_velocity": "flow_velocity",
    "A": "luminal_area",
    "luminal_area": "luminal_area",
    "Q": "flow_rate",
    "flow_rate": "flow_rate",
}


class RuntimeDiseaseDataset:
    """One complete in-memory disease population with preserved PWDB subject IDs."""

    __slots__ = (
        "_identity",
        "_parent_identity",
        "_run_identity",
        "_cohort",
        "_states",
        "_status",
        "_provenance",
    )

    def __init__(
        self,
        *,
        identity: DatasetIdentity,
        parent_identity: DatasetIdentity,
        run_identity: DiseaseRunIdentity,
        cohort: Cohort,
        subject_states: tuple[RuntimeSubjectState, ...],
        quantity_statuses: tuple[tuple[str, DiseaseQuantityStatus], ...],
    ) -> None:
        if not isinstance(identity, DatasetIdentity):
            raise TypeError("identity must be a DatasetIdentity")
        if not isinstance(parent_identity, DatasetIdentity):
            raise TypeError("parent_identity must be a DatasetIdentity")
        if not isinstance(run_identity, DiseaseRunIdentity):
            raise TypeError("run_identity must be a DiseaseRunIdentity")
        if run_identity.parent_dataset_identity != parent_identity:
            raise ValueError("run parent identity must match parent_identity")
        if identity != runtime_dataset_identity(run_identity):
            raise ValueError("runtime dataset identity must be derived from its DiseaseRunIdentity")
        if not isinstance(cohort, Cohort) or cohort.dataset_identity != identity:
            raise ValueError("cohort must belong to the runtime dataset identity")
        if not isinstance(subject_states, tuple) or any(
            not isinstance(item, RuntimeSubjectState) for item in subject_states
        ):
            raise TypeError("subject_states must contain RuntimeSubjectState values")
        state_ids = tuple(item.subject.canonical_subject_id for item in subject_states)
        if state_ids != cohort.canonical_subject_ids or state_ids != run_identity.canonical_subject_ids:
            raise ValueError("runtime subject IDs/order must exactly preserve the selected PWDB cohort")
        if any(item.subject.dataset_identity != identity for item in subject_states):
            raise ValueError("all runtime subjects must belong to the runtime dataset identity")

        if not isinstance(quantity_statuses, tuple):
            raise TypeError("quantity_statuses must be a tuple")
        status = dict(quantity_statuses)
        if len(status) != len(quantity_statuses) or any(
            not isinstance(item, DiseaseQuantityStatus) for item in status.values()
        ):
            raise ValueError("quantity_statuses must contain unique DiseaseQuantityStatus entries")

        provenance: dict[str, ProvenanceRecord] = {}
        for state in subject_states:
            for record in state.provenance_records:
                existing = provenance.get(record.record_id)
                if existing is not None and existing != record:
                    raise ValueError("conflicting runtime provenance record IDs")
                provenance[record.record_id] = record

        self._identity = identity
        self._parent_identity = parent_identity
        self._run_identity = run_identity
        self._cohort = cohort
        self._states = subject_states
        self._status = status
        self._provenance = provenance

    @property
    def identity(self) -> DatasetIdentity:
        return self._identity

    @property
    def parent_identity(self) -> DatasetIdentity:
        return self._parent_identity

    @property
    def run_identity(self) -> DiseaseRunIdentity:
        return self._run_identity

    @property
    def cohort(self) -> Cohort:
        return self._cohort

    @property
    def run_id(self) -> str:
        return self._run_identity.run_id

    def subjects(self) -> tuple[VirtualSubject, ...]:
        return tuple(state.subject for state in self._states)

    def state(self, subject_id: str) -> RuntimeSubjectState:
        if not isinstance(subject_id, str) or not subject_id:
            raise SelectionError("subject_id must be non-empty")
        for state in self._states:
            if state.subject.canonical_subject_id == subject_id:
                return state
        raise SelectionError(f"runtime disease dataset has no subject {subject_id!r}")

    def subject(self, subject_id: str) -> VirtualSubject:
        return self.state(subject_id).subject

    def locations(self) -> tuple[MeasurementSite, ...]:
        seen: set[str] = set()
        result: list[MeasurementSite] = []
        for item in self._states[0].results:
            if isinstance(item.location, MeasurementSite):
                site_id = item.location.canonical_site_id
                if site_id not in seen:
                    seen.add(site_id)
                    result.append(item.location)
        return tuple(result)

    def quantities(self) -> tuple[QuantityDefinition, ...]:
        names: list[str] = []
        for state in self._states:
            for result in state.results:
                name = result.quantity.canonical_name
                if name not in names:
                    names.append(name)
        return tuple(canonical_quantity(name) for name in names)

    def quantity_status(self, quantity: str) -> DiseaseQuantityStatus:
        if not isinstance(quantity, str) or not quantity:
            raise ValueError("quantity must be non-empty")
        try:
            return self._status[quantity]
        except KeyError as exc:
            raise CapabilityError(f"Virtual Disease v1 has no status for quantity {quantity!r}") from exc

    def quantity_statuses(self) -> tuple[tuple[str, DiseaseQuantityStatus], ...]:
        return tuple(sorted(self._status.items()))

    def provenance(self, record_id: str) -> ProvenanceRecord:
        if not isinstance(record_id, str) or not record_id:
            raise ValueError("record_id must be non-empty")
        try:
            return self._provenance[record_id]
        except KeyError as exc:
            raise KeyError(f"unknown runtime provenance record {record_id!r}") from exc

    def _ids(self, subjects: str | Iterable[str] | None) -> tuple[str, ...]:
        if subjects is None:
            ids = self._cohort.canonical_subject_ids
        elif isinstance(subjects, str):
            ids = (subjects,)
        else:
            ids = tuple(subjects)
        if not ids or any(not isinstance(item, str) or not item for item in ids):
            raise SelectionError("subjects must contain non-empty canonical subject IDs")
        if len(ids) != len(set(ids)):
            raise SelectionError("subjects must not contain duplicate IDs")
        known = set(self._cohort.canonical_subject_ids)
        if any(item not in known for item in ids):
            raise SelectionError("subjects contain IDs outside the runtime disease cohort")
        return ids

    def get(
        self,
        quantity: str,
        *,
        subjects: str | Iterable[str] | None = None,
        location: VascularLocation | None = None,
    ) -> ScientificResult:
        status = self.quantity_status(quantity)
        if status is DiseaseQuantityStatus.NOT_SUPPORTED:
            raise CapabilityError(
                f"quantity {quantity!r} is explicitly NOT_SUPPORTED in Virtual Disease v1"
            )
        if quantity in {"pressure", "flow_velocity", "luminal_area", "flow_rate"}:
            raise CapabilityError("use waveform() for runtime waveform quantities")
        if quantity == "vascular_geometry":
            ids = self._ids(subjects)
            if len(ids) != 1:
                raise SelectionError("runtime geometry retrieval requires exactly one subject")
            if location is not None and not isinstance(location, SegmentLocation):
                raise SelectionError("runtime geometry location must be a SegmentLocation")
            return self.geometry(subject=ids[0], location=location)

        ids = self._ids(subjects)
        selected: list[ScientificResult] = []
        for subject_id in ids:
            matches = tuple(
                result
                for result in self.state(subject_id).results
                if result.quantity.canonical_name == quantity and result.location == location
            )
            if len(matches) != 1:
                raise CapabilityError(
                    f"no unique runtime result for {quantity!r} at location {location!r}"
                )
            selected.append(matches[0])
        if len(selected) == 1:
            return selected[0]
        return self._aggregate(quantity, location, ids, tuple(selected))

    def _aggregate(
        self,
        quantity: str,
        location: VascularLocation | None,
        ids: tuple[str, ...],
        selected: tuple[ScientificResult, ...],
    ) -> ScientificResult:
        cohort = Cohort(
            dataset_identity=self._identity,
            canonical_subject_ids=ids,
            ordering_rule=self._cohort.ordering_rule,
            selection_specification=self._cohort.selection_specification
            + (f"runtime_get_quantity={quantity}",),
        )
        provenance = ProvenanceBuilder(self._identity).build(
            evidence=EvidenceClass.MODELLED,
            validity=ValidityState.NOT_EVALUATED,
            value_state=ValueState.PRESENT,
            cohort=cohort,
            location=location,
            inputs=tuple(self.provenance(item.provenance_ref) for item in selected),
            method_id=RUNTIME_METHOD_ID,
            component=runtime_component(),
            parameters={"operation": "subject_axis_aggregation", "quantity": quantity},
            warnings=("Virtual Disease output is MODELLED and is not a clinical observation.",),
            output_identity=f"{quantity}@runtime-cohort:{self.run_id}",
        )
        self._provenance[provenance.record_id] = provenance
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=canonical_quantity(quantity),
            values=tuple(item.values for item in selected),
            provenance_ref=provenance.record_id,
            dimensions=("subject",),
            coordinates=(Coordinate("subject", ids),),
            source_unit=selected[0].source_unit,
            source_label=selected[0].source_label,
            cohort=cohort,
            location=location,
            evidence=EvidenceClass.MODELLED,
            value_state=ValueState.PRESENT,
            validity=ValidityState.NOT_EVALUATED,
            warnings=("Virtual Disease output is MODELLED and is not a clinical observation.",),
            method_id=RUNTIME_METHOD_ID,
        )

    def waveform(
        self,
        signal: str,
        *,
        subject: str,
        location: MeasurementSite,
    ) -> Waveform:
        if not isinstance(signal, str):
            raise TypeError("signal must be a string")
        try:
            quantity = _SIGNAL_ALIASES[signal]
        except KeyError as exc:
            raise CapabilityError(f"unknown runtime waveform signal {signal!r}") from exc
        if not isinstance(location, MeasurementSite):
            raise SelectionError("runtime waveform location must be a MeasurementSite")
        result = self.state(subject).result(quantity, location=location)
        if not isinstance(result, Waveform):
            raise RuntimeError("runtime waveform index resolved a non-Waveform result")
        return result

    def geometry(
        self,
        *,
        subject: str,
        location: SegmentLocation | None = None,
    ) -> ScientificResult:
        full = self.state(subject).result("vascular_geometry")
        if location is None:
            return full
        if not isinstance(location, SegmentLocation):
            raise SelectionError("runtime geometry location must be a SegmentLocation")
        matches = tuple(
            item for item in full.values
            if item.segment_id == location.canonical_segment_id
        )
        if len(matches) != 1:
            raise SelectionError(
                f"runtime geometry has no segment {location.canonical_segment_id!r}"
            )
        parent = self.provenance(full.provenance_ref)
        subject_key = SubjectKey(self._identity, subject)
        provenance = ProvenanceBuilder(self._identity).build(
            evidence=EvidenceClass.MODELLED,
            validity=ValidityState.NOT_EVALUATED,
            value_state=ValueState.PRESENT,
            subject=subject_key,
            location=location,
            inputs=(parent,),
            method_id=RUNTIME_METHOD_ID,
            component=runtime_component(),
            parameters={"operation": "segment_selection"},
            warnings=full.warnings,
            output_identity=(
                f"vascular_geometry@subject:{subject}@segment:{location.canonical_segment_id}"
            ),
        )
        self._provenance[provenance.record_id] = provenance
        return ScientificResult(
            dataset_identity=self._identity,
            quantity=full.quantity,
            values=matches[0],
            provenance_ref=provenance.record_id,
            source_label=full.source_label,
            subject=subject_key,
            location=location,
            evidence=EvidenceClass.MODELLED,
            value_state=ValueState.PRESENT,
            validity=ValidityState.NOT_EVALUATED,
            warnings=full.warnings,
            method_id=RUNTIME_METHOD_ID,
        )


__all__ = ["RuntimeDiseaseDataset"]
