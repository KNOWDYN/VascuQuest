"""Dataset-backend port and storage-independent scientific read requests.

The backend port translates a concrete virtual-population source into canonical
VascuQuest domain objects. It deliberately contains no source filenames,
reader-library types, acquisition logic, or dataset-specific equations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias, runtime_checkable

from vascuquest.domain.cohort import Cohort
from vascuquest.domain.identity import DatasetIdentity, SubjectKey
from vascuquest.domain.location import (
    MeasurementSite,
    PathPosition,
    SegmentLocation,
    VascularLocation,
)
from vascuquest.domain.result import ScientificResult, Waveform
from vascuquest.domain.subject import VirtualSubject


CapabilitySet: TypeAlias = frozenset[str]
_LOCATION_TYPES = (SegmentLocation, MeasurementSite, PathPosition)


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _validate_location(value: object | None, field_name: str) -> None:
    if value is not None and not isinstance(value, _LOCATION_TYPES):
        raise TypeError(f"{field_name} must be a supported VascularLocation")


@dataclass(frozen=True, slots=True)
class QuantityRequest:
    """Canonical request for one quantity in an optional scientific context."""

    quantity: str
    subject: SubjectKey | None = None
    cohort: Cohort | None = None
    location: VascularLocation | None = None

    def __post_init__(self) -> None:
        _required_text(self.quantity, "quantity")
        if self.subject is not None and not isinstance(self.subject, SubjectKey):
            raise TypeError("subject must be a SubjectKey")
        if self.cohort is not None and not isinstance(self.cohort, Cohort):
            raise TypeError("cohort must be a Cohort")
        _validate_location(self.location, "location")
        if self.subject is not None and self.cohort is not None:
            if self.subject.dataset_identity != self.cohort.dataset_identity:
                raise ValueError("subject and cohort must belong to the same dataset")
            if self.subject.canonical_subject_id not in self.cohort.canonical_subject_ids:
                raise ValueError("subject must belong to cohort when both are supplied")


@dataclass(frozen=True, slots=True)
class WaveformRequest:
    """Canonical request for one subject signal at one vascular location."""

    signal: str
    subject: SubjectKey
    location: VascularLocation

    def __post_init__(self) -> None:
        _required_text(self.signal, "signal")
        if not isinstance(self.subject, SubjectKey):
            raise TypeError("subject must be a SubjectKey")
        _validate_location(self.location, "location")


@dataclass(frozen=True, slots=True)
class GeometryRequest:
    """Canonical request for source-supported geometry context."""

    subject: SubjectKey | None = None
    location: VascularLocation | None = None

    def __post_init__(self) -> None:
        if self.subject is not None and not isinstance(self.subject, SubjectKey):
            raise TypeError("subject must be a SubjectKey")
        _validate_location(self.location, "location")


@runtime_checkable
class DatasetBackend(Protocol):
    """Structural port implemented by one canonical dataset backend.

    ``descriptor`` is intentionally typed as ``object`` here. The concrete
    plugin layer validates that it is a VascuQuest ``ComponentDescriptor``;
    keeping that implementation type out of this module preserves the approved
    ports-to-domain dependency direction.
    """

    @property
    def descriptor(self) -> object:
        """Component metadata validated by the plugin registry."""

        ...

    def identity(self) -> DatasetIdentity:
        """Return the exact canonical dataset identity implemented by the backend."""

        ...

    def capabilities(self) -> CapabilitySet:
        """Advertise canonical capabilities before expensive source access."""

        ...

    def subjects(self, request: object | None = None) -> tuple[VirtualSubject, ...]:
        """Return lightweight virtual-subject identities/metadata references."""

        ...

    def locations(self, request: object | None = None) -> tuple[VascularLocation, ...]:
        """Return source-supported canonical vascular locations."""

        ...

    def get_quantity(self, request: QuantityRequest) -> ScientificResult:
        """Return a canonical scientific result for one quantity request."""

        ...

    def get_waveform(self, request: WaveformRequest) -> Waveform:
        """Return a canonical time-resolved source waveform."""

        ...

    def geometry(self, request: GeometryRequest) -> ScientificResult:
        """Return source-supported geometry as a canonical scientific result."""

        ...


__all__ = [
    "CapabilitySet",
    "DatasetBackend",
    "GeometryRequest",
    "QuantityRequest",
    "WaveformRequest",
]
