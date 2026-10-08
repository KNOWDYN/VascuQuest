"""HEMOSPACE path-reader contract tests using MATLAB-v7.3/HDF5 fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from vascuquest.hemospace.path import PATH_ARTIFACTS, path_profile


def _matlab_char(text: str) -> np.ndarray:
    return np.asarray([ord(char) for char in text], dtype=np.uint16).reshape((-1, 1))


def _write_fixture(
    path: Path,
    path_name: str,
    *,
    signals: tuple[str, ...],
    subjects: int = 3,
    points: int = 4,
    samples: int = 5,
) -> None:
    ref_dtype = h5py.ref_dtype
    with h5py.File(path, "w", userblock_size=512) as handle:
        data = handle.create_group("data")
        data.attrs["MATLAB_class"] = np.bytes_("struct")
        path_waves = data.create_group("path_waves")
        path_waves.attrs["MATLAB_class"] = np.bytes_("struct")
        group = path_waves.create_group(path_name)
        group.attrs["MATLAB_class"] = np.bytes_("struct")
        refs = handle.create_group("#refs#")

        field_refs = {
            field: np.empty((1, subjects), dtype=ref_dtype)
            for field in (
                "dist",
                "artery_dist",
                "onset_time",
                "artery",
                "segment_no",
                *signals,
            )
        }

        names = (
            "Ascending Aorta",
            "Aortic Arch I",
            "Descending Thoracic Aorta I",
            "Abdominal Aorta I",
        )

        for subject in range(subjects):
            distance = np.asarray([0.0, 0.1, 0.2, 0.3]) + 0.001 * subject
            artery_distance = np.asarray([0.0, 0.1, 0.0, 0.1])
            onset = distance / 5.0 + 0.01 * subject

            for field, values in (
                ("dist", distance),
                ("artery_dist", artery_distance),
                ("onset_time", onset),
            ):
                dataset = refs.create_dataset(
                    f"{field}_{subject}", data=values.reshape((-1, 1), order="F")
                )
                dataset.attrs["MATLAB_class"] = np.bytes_("double")
                field_refs[field][0, subject] = dataset.ref

            artery_cells = refs.create_dataset(
                f"artery_cell_{subject}", (points, 1), dtype=ref_dtype
            )
            artery_cells.attrs["MATLAB_class"] = np.bytes_("cell")
            segment_cells = refs.create_dataset(
                f"segment_cell_{subject}", (points, 1), dtype=ref_dtype
            )
            segment_cells.attrs["MATLAB_class"] = np.bytes_("cell")
            for point, name in enumerate(names):
                artery = refs.create_dataset(
                    f"artery_{subject}_{point}", data=_matlab_char(name)
                )
                artery.attrs["MATLAB_class"] = np.bytes_("char")
                artery_cells[point, 0] = artery.ref
                segment = refs.create_dataset(
                    f"segment_{subject}_{point}",
                    data=np.asarray([[point + 1]], dtype=float),
                )
                segment.attrs["MATLAB_class"] = np.bytes_("double")
                segment_cells[point, 0] = segment.ref
            field_refs["artery"][0, subject] = artery_cells.ref
            field_refs["segment_no"][0, subject] = segment_cells.ref

            time = np.linspace(0.0, 1.0, samples)
            for signal in signals:
                cells = refs.create_dataset(
                    f"{signal}_cell_{subject}", (points, 1), dtype=ref_dtype
                )
                cells.attrs["MATLAB_class"] = np.bytes_("cell")
                for point in range(points):
                    if signal == "P":
                        values = 80.0 + 20.0 * np.sin(2.0 * np.pi * time) + point
                    elif signal == "U":
                        values = 0.5 + 0.1 * np.sin(2.0 * np.pi * time) + 0.01 * point
                    else:
                        values = 3e-4 + 1e-5 * np.sin(2.0 * np.pi * time) + 1e-6 * point
                    wave = refs.create_dataset(
                        f"{signal}_{subject}_{point}",
                        data=values.reshape((-1, 1), order="F"),
                    )
                    wave.attrs["MATLAB_class"] = np.bytes_("double")
                    cells[point, 0] = wave.ref
                field_refs[signal][0, subject] = cells.ref

        for field, refs_array in field_refs.items():
            group.create_dataset(field, data=refs_array, dtype=ref_dtype)

    # MATLAB v7.3 reserves an HDF5 userblock for the MAT-file header. HEMOSPACE
    # intentionally depends only on the HDF5 structure, but include the header
    # signature to make the fixture representation faithful.
    header = b"MATLAB 7.3 MAT-file, Platform: synthetic HEMOSPACE qualification"
    with path.open("r+b") as handle:
        handle.write(header.ljust(128, b" "))


def test_path_reader_matches_authoritative_exporter_contract(tmp_path: Path) -> None:
    resolved: dict[str, Path] = {}
    for path_name, signal_map in PATH_ARTIFACTS.items():
        grouped: dict[str, list[str]] = {}
        for signal, artifact_id in signal_map.items():
            grouped.setdefault(artifact_id, []).append(signal)
        for artifact_id, signals in grouped.items():
            source = tmp_path / f"{artifact_id}.mat"
            _write_fixture(source, path_name, signals=tuple(signals))
            resolved[artifact_id] = source

    def resolver(artifact_id: str) -> Path:
        return resolved[artifact_id]

    for path_name in PATH_ARTIFACTS:
        profile = path_profile(resolver, "2", path_name)
        assert profile.path_name == path_name
        assert len(profile.distance_m) == 4
        assert profile.artery[0] == "Ascending Aorta"
        assert profile.segment_no == (1, 2, 3, 4)
        assert set(profile.signal_summaries) == {"P", "U", "A"}
        assert profile.reconstructed_flow_summaries is not None
        assert len(profile.reconstructed_flow_summaries) == 4
        assert profile.apparent_path_pwv_m_per_s == pytest.approx(5.0)
        assert profile.onset_distance_r2 == pytest.approx(1.0)
        assert profile.pressure_pulse_amplification_terminal_to_root == pytest.approx(1.0)


def test_aorta_foot_uses_three_aligned_signal_artifacts(tmp_path: Path) -> None:
    resolved: dict[str, Path] = {}
    for signal, artifact_id in PATH_ARTIFACTS["aorta_foot"].items():
        source = tmp_path / f"{artifact_id}.mat"
        _write_fixture(source, "aorta_foot", signals=(signal,))
        resolved[artifact_id] = source

    profile = path_profile(resolved.__getitem__, "3", "aorta_foot")
    assert profile.source_artifacts == (
        "path_aorta_foot_p",
        "path_aorta_foot_u",
        "path_aorta_foot_a",
    )
    assert set(profile.signal_summaries) == {"P", "U", "A"}
    assert profile.reconstructed_flow_summaries is not None
