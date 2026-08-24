"""Unit tests for canonical vascular-location value objects."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vascuquest.domain.location import MeasurementSite, PathPosition, SegmentLocation


def test_location_kinds_remain_distinct_value_types() -> None:
    segment = SegmentLocation("segment:1")
    site = MeasurementSite("site:1")
    path_position = PathPosition("path:aorta-finger", 0)

    assert segment != site
    assert segment != path_position
    assert site != path_position
    assert type(segment) is SegmentLocation
    assert type(site) is MeasurementSite
    assert type(path_position) is PathPosition


def test_location_objects_have_value_semantics() -> None:
    assert SegmentLocation("segment:1") == SegmentLocation("segment:1")
    assert MeasurementSite("site:1") == MeasurementSite("site:1")
    assert PathPosition("path:aorta-finger", 3) == PathPosition("path:aorta-finger", 3)

    assert SegmentLocation("segment:1") != SegmentLocation("segment:2")
    assert MeasurementSite("site:1") != MeasurementSite("site:2")
    assert PathPosition("path:aorta-finger", 3) != PathPosition("path:aorta-finger", 4)


def test_location_identifiers_reject_empty_or_padded_text() -> None:
    with pytest.raises(ValueError):
        SegmentLocation("")

    with pytest.raises(ValueError):
        MeasurementSite(" site:1")

    with pytest.raises(ValueError):
        PathPosition("path:aorta-finger ", 0)


def test_location_identifiers_reject_non_string_values() -> None:
    with pytest.raises(TypeError):
        SegmentLocation(1)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        MeasurementSite(1)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        PathPosition(1, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("position_index", [-1, -10])
def test_path_position_rejects_negative_index(position_index: int) -> None:
    with pytest.raises(ValueError):
        PathPosition("path:aorta-finger", position_index)


@pytest.mark.parametrize("position_index", [True, False, 1.0, "1"])
def test_path_position_requires_integer_index(position_index: object) -> None:
    with pytest.raises(TypeError):
        PathPosition("path:aorta-finger", position_index)  # type: ignore[arg-type]


def test_path_position_does_not_expose_interpolation_or_source_storage_fields() -> None:
    position = PathPosition("path:aorta-finger", 2)

    assert position.canonical_path_id == "path:aorta-finger"
    assert position.position_index == 2
    assert not hasattr(position, "source_point_index")
    assert not hasattr(position, "distance")
    assert not hasattr(position, "interpolated")


def test_location_objects_are_immutable_and_hashable() -> None:
    segment = SegmentLocation("segment:1")
    site = MeasurementSite("site:1")
    position = PathPosition("path:aorta-finger", 0)

    assert {segment}
    assert {site}
    assert {position}

    with pytest.raises(FrozenInstanceError):
        segment.canonical_segment_id = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        site.canonical_site_id = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        position.position_index = 1  # type: ignore[misc]
