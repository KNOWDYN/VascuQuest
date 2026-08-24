"""Fixture validation for PWDB geometry and common-site waveform adapters."""

from __future__ import annotations

import math
from pathlib import Path
import zipfile

import pytest

from vascuquest.backends.pwdb3275625.geometry_reader import GeometryCSVArchiveReader
from vascuquest.backends.pwdb3275625.waveform_reader import SAMPLE_RATE_HZ, WaveformCSVArchiveReader
from vascuquest.errors import SchemaError


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def test_geometry_reader_preserves_segment_identity_topology_and_source_units(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "geo.zip", {"geo/pwdb_geo_0002.csv": (
        "seg_no,inlet_node,outlet_node,length,inlet_radius,outlet_radius,peripheral_c,peripheral_r\n"
        "1,1,2,0.10,0.012,0.011,0,0\n"
        "2,2,3,0.08,0.011,0.010,1.2e-10,8.5e8\n"
    )})
    source = GeometryCSVArchiveReader(archive).read_subject("2")
    assert source.source_member == "geo/pwdb_geo_0002.csv"
    assert tuple(segment.segment_id for segment in source.segments) == ("1", "2")
    assert source.segments[0].length_m == 0.10
    assert source.segments[0].inlet_radius_m == 0.012
    assert source.segments[1].inlet_node == 2
    assert source.segments[1].outlet_node == 3


def test_geometry_reader_rejects_nonpositive_length_or_radius(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "geo.zip", {"pwdb_geo_0001.csv": (
        "seg_no,inlet_node,outlet_node,length,inlet_radius,outlet_radius,peripheral_c,peripheral_r\n"
        "1,1,2,0,0.012,0.011,0,0\n"
    )})
    with pytest.raises(SchemaError, match="non-positive"):
        GeometryCSVArchiveReader(archive).read_subject("1")


def test_waveform_reader_uses_explicit_subject_id_and_500_hz_time_coordinate(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "PWs_csv.zip", {"PWs_csv/PWs_Radial_P.csv": (
        "Subject Number,pt1,pt2,pt3,pt4\n"
        "2,80,90,100,nan\n"
        "1,70,75,nan,nan\n"
    )})
    series = WaveformCSVArchiveReader(archive).read(subject_id="1", site_id="Radial", source_signal="P")
    assert series.values[:2] == (70.0, 75.0)
    assert math.isnan(series.values[2])
    assert series.time_seconds == (0.0, 1.0 / SAMPLE_RATE_HZ, 2.0 / SAMPLE_RATE_HZ, 3.0 / SAMPLE_RATE_HZ)
    assert series.missing_mask == (False, False, False, False)
    assert series.padding_mask == (False, False, True, True)


def test_waveform_reader_keeps_internal_missing_sample_distinct_from_padding(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "PWs_csv.zip", {"PWs_AorticRoot_U.csv": (
        "Subject Number,pt1,pt2,pt3,pt4\n"
        "1,0.1,nan,0.3,nan\n"
    )})
    series = WaveformCSVArchiveReader(archive).read(subject_id="1", site_id="AorticRoot", source_signal="U")
    assert series.missing_mask == (False, True, False, False)
    assert series.padding_mask == (False, False, False, True)
