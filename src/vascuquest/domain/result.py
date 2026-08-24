"""Storage-independent scientific result value objects.

Scientific results couple values with the scientific context required to
interpret them. The domain intentionally does not choose a persistent array,
table, dataframe, provenance-store, or source-reader representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .cohort import Cohort
from .evidence import EvidenceClass
from .identity import DatasetIdentity, SubjectKey
from .location import MeasurementSite, PathPosition, SegmentLocation, VascularLocation
from .quantity import QuantityDefinition


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


def _validate_optional_text(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_text(value, field_name)


def _validate_text_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    unique: bool = False,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple of strings")

    seen: set[str] = set()
    for value in values:
        _validate_text(value, field_name)
        if unique and value in seen:
            raise ValueError(f"{field_name} must not contain duplicate values")
        seen.add(value)


class ValueState(str, Enum):
    """Scientific availability state for a result value/context."""

    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValidityState(str, Enum):
    """Validity/admissibility state, deliberately separate from evidence."""

    VALID = "VALID"
    VALID_WITH_WARNING = "VALID_WITH_WARNING"
    OUT_OF_DECLARED_DOMAIN = "OUT_OF_DECLARED_DOMAIN"
    INVALID = "INVALID"
    INVALID_INPUT = "INVALID_INPUT"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True, eq=False)
class Coordinate:
    """Named coordinate values giving scientific meaning to a result axis/context."""

    name: str
    values: object
    unit: str | None = None

    __hash__ = None

    def __post_init__(self) -> None:
        _validate_text(self.name, "name")
        _validate_optional_text(self.unit, "unit")


@dataclass(frozen=True, slots=True, eq=False)
class ScientificResult:
    """Values coupled to canonical scientific identity and interpretation.

    ``values`` and coordinate values are intentionally storage-agnostic. They
    may be scalars, immutable Python structures, or array-like objects supplied
    by later layers. This frozen wrapper expresses logical read-only semantics;
    it does not claim to deep-freeze an external array object.

    ``provenance_ref`` is a domain-level reference. The concrete serializable
    provenance record is implemented by the later provenance layer so the
    scientific domain does not depend on that implementation package.
    """

    dataset_identity: DatasetIdentity
    quantity: QuantityDefinition
    values: object
    provenance_ref: str
    dimensions: tuple[str, ...] = ()
    coordinates: tuple[Coordinate, ...] = ()
    source_unit: str | None = None
    source_label: str | None = None
    subject: SubjectKey | None = None
    cohort: Cohort | None = None
    location: VascularLocation | None = None
    evidence: EvidenceClass = EvidenceClass.SOURCE
    value_state: ValueState = ValueState.PRESENT
    validity: ValidityState = ValidityState.NOT_EVALUATED
    warnings: tuple[str, ...] = ()
    method_id: str | None = None

    __hash__ = None

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_identity, DatasetIdentity):
            raise TypeError("dataset_identity must be a DatasetIdentity")
        if not isinstance(self.quantity, QuantityDefinition):
            raise TypeError("quantity must be a QuantityDefinition")
        if self.quantity.schema_version != self.dataset_identity.schema_version:
            raise ValueError("quantity schema_version must match dataset_identity schema_version")

        _validate_text(self.provenance_ref, "provenance_ref")
        _validate_text_tuple(self.dimensions, "dimensions", unique=True)
        if not isinstance(self.coordinates, tuple):
            raise TypeError("coordinates must be a tuple of Coordinate values")

        coordinate_names: set[str] = set()
        for coordinate in self.coordinates:
            if not isinstance(coordinate, Coordinate):
                raise TypeError("coordinates must contain only Coordinate values")
            if coordinate.name in coordinate_names:
                raise ValueError("coordinates must not contain duplicate names")
            coordinate_names.add(coordinate.name)

        _validate_optional_text(self.source_unit, "source_unit")
        _validate_optional_text(self.source_label, "source_label")

        if self.subject is not None:
            if not isinstance(self.subject, SubjectKey):
                raise TypeError("subject must be a SubjectKey")
            if self.subject.dataset_identity != self.dataset_identity:
                raise ValueError("subject dataset_identity must match result dataset_identity")

        if self.cohort is not None:
            if not isinstance(self.cohort, Cohort):
                raise TypeError("cohort must be a Cohort")
            if self.cohort.dataset_identity != self.dataset_identity:
                raise ValueError("cohort dataset_identity must match result dataset_identity")

        if self.subject is not None and self.cohort is not None:
            if self.subject.canonical_subject_id not in self.cohort.canonical_subject_ids:
                raise ValueError("subject must belong to cohort when both contexts are supplied")

        if self.location is not None and not isinstance(
            self.location,
            (SegmentLocation, MeasurementSite, PathPosition),
        ):
            raise TypeError("location must be a supported VascularLocation")

        if not isinstance(self.evidence, EvidenceClass):
            raise TypeError("evidence must be an EvidenceClass")
        if not isinstance(self.value_state, ValueState):
            raise TypeError("value_state must be a ValueState")
        if not isinstance(self.validity, ValidityState):
            raise TypeError("validity must be a ValidityState")

        _validate_text_tuple(self.warnings, "warnings")
        _validate_optional_text(self.method_id, "method_id")
        if self.evidence is not EvidenceClass.SOURCE and self.method_id is None:
            raise ValueError("non-SOURCE results must identify the producing method")

    @property
    def canonical_unit(self) -> str | None:
        """Canonical unit supplied by the quantity definition."""

        return self.quantity.canonical_unit

    @property
    def physical_dimension(self) -> str | None:
        """Canonical physical dimension supplied by the quantity definition."""

        return self.quantity.physical_dimension


@dataclass(frozen=True, slots=True, eq=False)
class Waveform(ScientificResult):
    """Time-resolved scientific result for one subject and vascular location."""

    missing_mask: object | None = None
    padding_mask: object | None = None

    __hash__ = None

    def __post_init__(self) -> None:
        super(Waveform, self).__post_init__()

        if self.subject is None:
            raise ValueError("waveform requires subject context")
        if self.location is None:
            raise ValueError("waveform requires vascular location context")
        if "time" not in self.dimensions:
            raise ValueError("waveform dimensions must include 'time'")
        if not any(coordinate.name == "time" for coordinate in self.coordinates):
            raise ValueError("waveform requires an explicit time coordinate")

    @property
    def time_coordinate(self) -> Coordinate:
        """Return the explicit time coordinate required by the waveform contract."""

        for coordinate in self.coordinates:
            if coordinate.name == "time":
                return coordinate
        raise RuntimeError("validated waveform is missing its time coordinate")


__all__ = [
    "Coordinate",
    "ScientificResult",
    "ValidityState",
    "ValueState",
    "Waveform",
]
