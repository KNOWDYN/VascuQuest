from __future__ import annotations

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")

from vascuquest.errors import IntegrityError
from vascuquest.hemospace.remote_hdf5 import HTTPRangeReader
from vascuquest.hemospace.remote_path import RaggedPathWaveField


class _Response:
    def __init__(self, status: int, payload: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _opener_for(payload: bytes):
    def opener(request, timeout=None):
        if request.get_method() == "HEAD":
            return _Response(200, b"", {"Content-Length": str(len(payload))})
        headers = dict(request.header_items())
        range_value = headers.get("Range") or headers.get("range")
        if range_value is None:
            return _Response(200, payload, {"Content-Length": str(len(payload))})
        start, end = (int(v) for v in range_value.split("=", 1)[1].split("-", 1))
        body = payload[start : end + 1]
        return _Response(
            206,
            body,
            {
                "Content-Length": str(len(body)),
                "Content-Range": f"bytes {start}-{end}/{len(payload)}",
            },
        )

    return opener


def test_http_range_reader_allows_sparse_hdf5_reads(tmp_path) -> None:
    source = tmp_path / "large.h5"
    with h5py.File(source, "w") as handle:
        handle.create_dataset("values", data=np.arange(1_000_000, dtype=np.float64))
    payload = source.read_bytes()
    reader = HTTPRangeReader(
        "https://example.invalid/large.h5",
        block_size=65536,
        max_cache_blocks=16,
        opener=_opener_for(payload),
    )
    try:
        with h5py.File(reader, "r") as handle:
            got = np.asarray(handle["values"][100:110])
        assert np.array_equal(got, np.arange(100, 110, dtype=np.float64))
        assert reader.bytes_fetched < len(payload)
        assert reader.requests > 0
    finally:
        reader.close()


def _wave(n: int, offset: float = 0.0) -> np.ndarray:
    return np.arange(n, dtype=float) + offset


def test_ragged_path_preserves_unequal_full_path_and_qualifies_only_aligned_segment() -> None:
    field = RaggedPathWaveField(
        subject_id="1",
        path_name="aorta_brain",
        source_artifacts=("path_aorta_brain",),
        sampling_frequency_hz=1000.0,
        distance_m=(0.0, 0.1, 0.2, 0.3),
        artery=("A", "A", "B", "B"),
        segment_no=(10, 10, 20, 20),
        artery_distance_m=(0.0, 0.1, 0.0, 0.1),
        onset_time_s=(0.0, 0.01, 0.02, 0.03),
        signals={
            "P": (_wave(5), _wave(5, 1), _wave(5, 2), _wave(6, 3)),
            "U": (_wave(5), _wave(5, 1), _wave(5, 2), _wave(5, 3)),
            "A": (_wave(5, 1), _wave(5, 2), _wave(5, 3), _wave(5, 4)),
        },
    )
    assert field.point_lengths("P") == (5, 5, 5, 6)
    aligned = field.aligned_segment(10)
    assert aligned.field.matrix("P").shape == (2, 5)
    assert np.array_equal(aligned.time_s, np.arange(5) / 1000.0)
    with pytest.raises(IntegrityError, match="exact common time support"):
        field.aligned_segment(20)
