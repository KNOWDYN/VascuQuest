"""Canonical result retrieval services shared by Python and CLI adapters."""

from __future__ import annotations

from collections.abc import Iterable

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import SubjectKey
from vascuquest.domain.location import VascularLocation
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.domain.subject import VirtualSubject
from vascuquest.errors import SelectionError
from vascuquest.ports.backend import (
    DatasetBackend,
    GeometryRequest,
    QuantityRequest,
    WaveformRequest,
)

from .selection import SelectionService


SubjectSelector = str | SubjectKey | VirtualSubject
QuantitySubjects = SubjectSelector | Cohort | Iterable[str] | None


class RetrievalService:
    """Normalize public selections into backend scientific requests."""

    __slots__ = ("_backend", "_selection")

    def __init__(self, backend: DatasetBackend, selection: SelectionService) -> None:
        if not isinstance(backend, DatasetBackend):
            raise TypeError("backend must conform to DatasetBackend")
        if not isinstance(selection, SelectionService):
            raise TypeError("selection must be a SelectionService")
        self._backend = backend
        self._selection = selection

    def get(
        self,
        quantity: str,
        *,
        subjects: QuantitySubjects = None,
        location: VascularLocation | None = None,
    ) -> ScientificResult:
        subject, cohort = self._normalize_quantity_subjects(subjects)
        return self._backend.get_quantity(
            QuantityRequest(
                quantity=quantity,
                subject=subject,
                cohort=cohort,
                location=location,
            )
        )

    def waveform(
        self,
        signal: str,
        *,
        subject: SubjectSelector,
        location: VascularLocation,
    ) -> Waveform:
        key = self._subject_key(subject)
        return self._backend.get_waveform(
            WaveformRequest(signal=signal, subject=key, location=location)
        )

    def geometry(
        self,
        *,
        subject: SubjectSelector,
        location: VascularLocation | None = None,
    ) -> ScientificResult:
        key = self._subject_key(subject)
        return self._backend.geometry(GeometryRequest(subject=key, location=location))

    def _normalize_quantity_subjects(
        self,
        subjects: QuantitySubjects,
    ) -> tuple[SubjectKey | None, Cohort | None]:
        if subjects is None:
            return None, None
        if isinstance(subjects, Cohort):
            self._require_dataset(subjects.dataset_identity)
            return None, subjects
        if isinstance(subjects, (str, SubjectKey, VirtualSubject)):
            return self._subject_key(subjects), None
        if isinstance(subjects, Iterable):
            cohort = self._selection.select(subject_ids=tuple(subjects))
            return None, cohort
        raise TypeError("subjects must be a subject selector, Cohort, iterable of IDs, or None")

    def _subject_key(self, subject: SubjectSelector) -> SubjectKey:
        if isinstance(subject, str):
            cohort = self._selection.select(subject_ids=(subject,))
            if len(cohort.canonical_subject_ids) != 1:
                raise SelectionError(f"unknown subject {subject!r}")
            return SubjectKey(cohort.dataset_identity, subject)
        if isinstance(subject, VirtualSubject):
            key = subject.key
        elif isinstance(subject, SubjectKey):
            key = subject
        else:
            raise TypeError("subject must be a subject ID, SubjectKey, or VirtualSubject")
        self._require_dataset(key.dataset_identity)
        return key

    def _require_dataset(self, identity: object) -> None:
        if identity != self._backend.identity():
            raise SelectionError("selection belongs to a different dataset identity")


__all__ = ["QuantitySubjects", "RetrievalService", "SubjectSelector"]
