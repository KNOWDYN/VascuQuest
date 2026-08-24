"""Immutable vascular-location value objects.

The core distinguishes arterial segments, named measurement sites, and
source-supported positions along arterial paths. Richer topology, geometry,
coordinate, and source-mapping metadata are supplied by schema/backend layers
rather than inferred by these identity objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


def _validate_location_id(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")


@dataclass(frozen=True, slots=True)
class SegmentLocation:
    """Canonical reference to one source-defined arterial segment."""

    canonical_segment_id: str

    def __post_init__(self) -> None:
        _validate_location_id(self.canonical_segment_id, "canonical_segment_id")


@dataclass(frozen=True, slots=True)
class MeasurementSite:
    """Canonical named site at which source signals or quantities are reported."""

    canonical_site_id: str

    def __post_init__(self) -> None:
        _validate_location_id(self.canonical_site_id, "canonical_site_id")


@dataclass(frozen=True, slots=True)
class PathPosition:
    """One source-supported indexed position along a canonical arterial path.

    The canonical position index refers to an actually supported stored
    position; it does not imply interpolation between stored positions. Source
    point indices, path distance, units, orientation, segment mapping, and
    within-segment distance remain explicit schema/result metadata when
    available.
    """

    canonical_path_id: str
    position_index: int

    def __post_init__(self) -> None:
        _validate_location_id(self.canonical_path_id, "canonical_path_id")
        if isinstance(self.position_index, bool) or not isinstance(self.position_index, int):
            raise TypeError("position_index must be an integer")
        if self.position_index < 0:
            raise ValueError("position_index must be non-negative")


VascularLocation: TypeAlias = SegmentLocation | MeasurementSite | PathPosition


__all__ = [
    "MeasurementSite",
    "PathPosition",
    "SegmentLocation",
    "VascularLocation",
]
