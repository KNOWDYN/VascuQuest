"""Backend integration tests for Batch-7 geometry and common-site waveforms."""

from __future__ import annotations

import math
from pathlib import Path
import zipfile

from vascuquest.backends.pwdb3275625 import PWDB3275625Backend
from vascuquest.domain.identity import SubjectKey
from vascuquest.domain.location import MeasurementSite, SegmentLocation
from vascuquest.domain.result import Waveform
from vascuquest.ports.backend import GeometryRequest, WaveformRequest


def _zip(path: Path, members: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _backend(tmp_path: Path) -> PWDB3275625Backend:
    sources = {
        "geometry": _zip(tmp_path / "geo.zip", {"geo/pwdb_geo_0001.csv": (
            "seg_no,inlet_node,outlet_node,length,inlet_radius,outlet_radius,peripheral_c,peripheral_r\n"
            "1,1,2,0.10,0.012,0.011,0,0\n"
            "2,2,3,0.08,0.011,0.010,1.2e-10,8.5e8\n"
        )}),
        "common_site_waveforms_csv": _zip(tmp_path / "PWs_csv.zip", {
            "PWs_csv/PWs_Radial_P.csv": "Subject Number,pt1,pt2,pt3,pt4\n1,70,75,nan,nan\n",
            "PWs_csv/PWs_AorticRoot_U.csv": "Subject Number,pt1,pt2,pt3\n1,0.1,0.2,0.3\n",
        }),
    }
    def resolve(artifact_id: str) -> Path:
        return sources[artifact_id]
    return PWDB3275625Backend(resolve)


def test_backend_returns_canonical_waveform_with_time_masks_and_provenance(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    result = backend.get_waveform(WaveformRequest(signal="pressure", subject=subject, location=MeasurementSite("Radial")))
    assert isinstance(result, Waveform)
    assert result.quantity.canonical_name == "pressure"
    assert result.source_label == "P"
    assert result.source_unit == "mmHg"
    assert result.time_coordinate.unit == "s"
    assert result.time_coordinate.values[:3] == (0.0, 0.002, 0.004)
    assert result.padding_mask == (False, False, True, True)
    assert result.missing_mask == (False, False, False, False)
    assert math.isnan(result.values[2])
    provenance = backend.provenance(result.provenance_ref)
    assert provenance.source_artifacts[0].artifact_id == "common_site_waveforms_csv"
    assert "P" in provenance.source_fields
    assert "PWs_csv/PWs_Radial_P.csv" in provenance.source_fields


def test_backend_accepts_unique_source_alias_but_returns_canonical_identity(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    result = backend.get_waveform(WaveformRequest(signal="U", subject=subject, location=MeasurementSite("AorticRoot")))
    assert result.quantity.canonical_name == "flow_velocity"
    assert result.source_unit == "m/s"
    assert result.values == (0.1, 0.2, 0.3)


def test_backend_geometry_returns_source_segments_without_invented_coordinates(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    result = backend.geometry(GeometryRequest(subject=subject))
    assert result.quantity.canonical_name == "vascular_geometry"
    assert result.quantity.canonical_unit is None
    assert result.dimensions == ("segment",)
    assert result.coordinates[0].values == ("1", "2")
    assert tuple(segment.segment_id for segment in result.values) == ("1", "2")
    assert result.values[1].length_m == 0.08
    provenance = backend.provenance(result.provenance_ref)
    assert provenance.source_artifacts[0].artifact_id == "geometry"
    assert "geo/pwdb_geo_0001.csv" in provenance.source_fields


def test_backend_geometry_can_select_one_source_segment(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    subject = SubjectKey(backend.identity(), "1")
    result = backend.geometry(GeometryRequest(subject=subject, location=SegmentLocation("2")))
    assert result.values.segment_id == "2"
    assert result.location == SegmentLocation("2")
    assert result.dimensions == ()
