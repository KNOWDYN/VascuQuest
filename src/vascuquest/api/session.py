"""Stable user-facing dataset session facade."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity
from vascuquest.domain.location import VascularLocation
from vascuquest.domain.quantity import QuantityDefinition
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.domain.subject import VirtualSubject
from vascuquest.provenance.model import ProvenanceRecord
from vascuquest.services import (
    DatasetService,
    DatasetStatus,
    ExecutionService,
    ExportingService,
    ReproductionService,
    RetrievalService,
    SelectionService,
)


class DatasetSession:
    """One coherent scientific facade over a single exact dataset identity."""

    __slots__ = (
        "_datasets",
        "_selection",
        "_retrieval",
        "_execution",
        "_exporting",
        "_reproduction",
    )

    def __init__(
        self,
        *,
        datasets: DatasetService,
        selection: SelectionService,
        retrieval: RetrievalService,
        execution: ExecutionService,
        exporting: ExportingService,
        reproduction: ReproductionService,
    ) -> None:
        for value, expected, name in (
            (datasets, DatasetService, "datasets"),
            (selection, SelectionService, "selection"),
            (retrieval, RetrievalService, "retrieval"),
            (execution, ExecutionService, "execution"),
            (exporting, ExportingService, "exporting"),
            (reproduction, ReproductionService, "reproduction"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be a {expected.__name__}")
        self._datasets = datasets
        self._selection = selection
        self._retrieval = retrieval
        self._execution = execution
        self._exporting = exporting
        self._reproduction = reproduction

    @property
    def identity(self) -> DatasetIdentity:
        return self._datasets.identity

    def status(self) -> DatasetStatus:
        return self._datasets.status()

    def capabilities(self) -> frozenset[str]:
        return self._datasets.capabilities()

    def quantities(self) -> tuple[QuantityDefinition, ...]:
        return self._datasets.quantities()

    def locations(self) -> tuple[VascularLocation, ...]:
        return self._datasets.locations()

    def subject(self, subject_id: str) -> VirtualSubject:
        return self._datasets.subject(subject_id)

    def subjects(
        self,
        *,
        where: Mapping[str, object] | None = None,
    ) -> tuple[VirtualSubject, ...]:
        if where is None:
            return self._datasets.subjects()
        cohort = self._selection.select(where=where)
        selected = set(cohort.canonical_subject_ids)
        return tuple(
            subject
            for subject in self._datasets.subjects()
            if subject.canonical_subject_id in selected
        )

    def select(
        self,
        *,
        subject_ids: Iterable[str] | None = None,
        where: Mapping[str, object] | None = None,
    ) -> Cohort:
        return self._selection.select(subject_ids=subject_ids, where=where)

    def get(
        self,
        quantity: str,
        *,
        subjects: object = None,
        location: VascularLocation | None = None,
    ) -> ScientificResult:
        return self._retrieval.get(quantity, subjects=subjects, location=location)

    def waveform(
        self,
        signal: str,
        *,
        subject: object,
        location: VascularLocation,
    ) -> Waveform:
        return self._retrieval.waveform(signal, subject=subject, location=location)

    def geometry(
        self,
        *,
        subject: object,
        location: VascularLocation | None = None,
    ) -> ScientificResult:
        return self._retrieval.geometry(subject=subject, location=location)

    def derive(
        self,
        method: str,
        *,
        inputs: Mapping[str, ScientificResult] | None = None,
        subjects: object = None,
        location: VascularLocation | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        return self._execution.derive(
            method,
            inputs=inputs,
            subjects=subjects,
            location=location,
            parameters=parameters,
        )

    def model(
        self,
        operator: str,
        *,
        inputs: Mapping[str, ScientificResult] | None = None,
        subjects: object = None,
        location: VascularLocation | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        return self._execution.model(
            operator,
            inputs=inputs,
            subjects=subjects,
            location=location,
            parameters=parameters,
        )

    def discover(
        self,
        method: str,
        *,
        cohort: Cohort,
        inputs: Mapping[str, ScientificResult] | None = None,
        parameters: Mapping[str, object] | None = None,
    ) -> ScientificResult:
        return self._execution.discover(
            method,
            cohort=cohort,
            inputs=inputs,
            parameters=parameters,
        )

    def export(
        self,
        result: ScientificResult,
        exporter: str,
        destination: object,
        *,
        options: Mapping[str, object] | None = None,
    ) -> object:
        return self._exporting.export(
            result,
            exporter,
            destination,
            options=options,
        )

    def reproduce(self, provenance: ProvenanceRecord) -> ScientificResult:
        return self._reproduction.reproduce(provenance)


__all__ = ["DatasetSession"]
