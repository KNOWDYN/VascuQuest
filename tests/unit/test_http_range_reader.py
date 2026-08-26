from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

import vascuquest.backends.pwdb3275625.http_range as http_range_module
from vascuquest.backends.pwdb3275625.http_range import (
    CanonicalRemoteFile,
    HTTPRangeReader,
    verify_zenodo_file_identity,
)
from vascuquest.errors import IntegrityError


class _Response:
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = {} if headers is None else headers

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def close(self) -> None:
        self._body.close()

    def getcode(self) -> int:
        return self.status


def test_http_range_reader_reads_only_requested_blocks_and_seeks() -> None:
    payload = bytes(range(64))
    requests: list[str] = []

    def opener(request: Request, timeout: int = 0) -> _Response:
        assert timeout == 60
        value = request.get_header("Range")
        assert value is not None
        requests.append(value)
        start_text, end_text = value.removeprefix("bytes=").split("-", 1)
        start, end = int(start_text), int(end_text)
        return _Response(
            payload[start : end + 1],
            status=206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
        )

    reader = HTTPRangeReader(
        "https://example.test/large.mat",
        size_bytes=len(payload),
        block_size=8,
        max_blocks=2,
        opener=opener,
    )
    with reader:
        assert reader.read(3) == payload[:3]
        reader.seek(10)
        assert reader.read(4) == payload[10:14]
        reader.seek(-2, io.SEEK_END)
        assert reader.read(2) == payload[-2:]
        assert reader.bytes_transferred < len(payload)
        assert reader.range_requests == len(requests)
        assert all(request.startswith("bytes=") for request in requests)


def test_http_range_reader_retries_same_range_after_transient_504(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = bytes(range(32))
    ranges: list[str] = []
    sleeps: list[float] = []

    def opener(request: Request, timeout: int = 0) -> _Response:
        assert timeout == 60
        value = request.get_header("Range")
        assert value is not None
        ranges.append(value)
        if len(ranges) == 1:
            raise HTTPError(request.full_url, 504, "Gateway Time-out", hdrs=None, fp=io.BytesIO(b""))
        start_text, end_text = value.removeprefix("bytes=").split("-", 1)
        start, end = int(start_text), int(end_text)
        return _Response(
            payload[start : end + 1],
            status=206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
        )

    monkeypatch.setattr(http_range_module.time, "sleep", sleeps.append)
    reader = HTTPRangeReader(
        "https://example.test/large.mat",
        size_bytes=len(payload),
        block_size=8,
        opener=opener,
    )
    with reader:
        assert reader.read(4) == payload[:4]
    assert ranges == ["bytes=0-7", "bytes=0-7"]
    assert sleeps == [1.0]
    assert reader.bytes_transferred == 8
    assert reader.range_requests == 1


def test_http_range_reader_does_not_retry_or_fallback_on_permanent_404(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[str] = []
    sleeps: list[float] = []

    def opener(request: Request, timeout: int = 0) -> _Response:
        value = request.get_header("Range")
        assert value is not None
        requests.append(value)
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b""))

    monkeypatch.setattr(http_range_module.time, "sleep", sleeps.append)
    reader = HTTPRangeReader(
        "https://example.test/large.mat",
        size_bytes=32,
        block_size=8,
        opener=opener,
    )
    with reader:
        with pytest.raises(HTTPError) as exc_info:
            reader.read(1)
    assert exc_info.value.code == 404
    assert requests == ["bytes=0-7"]
    assert sleeps == []


def test_http_range_reader_refuses_server_that_ignores_range() -> None:
    def opener(request: Request, timeout: int = 0) -> _Response:
        return _Response(b"x" * 100, status=200)

    reader = HTTPRangeReader(
        "https://example.test/large.mat",
        size_bytes=100,
        block_size=8,
        opener=opener,
    )
    with reader:
        with pytest.raises(OSError, match="did not honor HTTP Range"):
            reader.read(1)


def test_zenodo_metadata_must_match_manifest_checksum_and_size() -> None:
    source = CanonicalRemoteFile(
        url="https://zenodo.org/records/3275625/files/example.mat?download=1",
        record_id="3275625",
        filename="example.mat",
        checksum_algorithm="md5",
        checksum_value="abc123",
    )
    document = {
        "files": [
            {
                "key": "example.mat",
                "size": 987654321,
                "checksum": "md5:abc123",
            }
        ]
    }

    def opener(request: Request, timeout: int = 0) -> _Response:
        assert request.full_url == "https://zenodo.org/api/records/3275625"
        return _Response(json.dumps(document).encode("utf-8"), status=200)

    metadata = verify_zenodo_file_identity(source, opener=opener)
    assert metadata.size_bytes == 987654321
    assert metadata.checksum_algorithm == "md5"
    assert metadata.checksum_value == "abc123"

    document["files"][0]["checksum"] = "md5:deadbeef"
    with pytest.raises(IntegrityError, match="canonical checksum mismatch"):
        verify_zenodo_file_identity(source, opener=opener)
