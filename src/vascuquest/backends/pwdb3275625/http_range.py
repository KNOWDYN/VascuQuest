"""Bounded HTTP byte-range access for canonical large source artifacts.

This module deliberately refuses servers that ignore Range requests. It exists so
the multi-gigabyte PWDB MATLAB-v7.3 path artifacts can be accessed sparsely
without turning them into package assets or mandatory local downloads.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import io
import json
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from vascuquest.errors import IntegrityError

_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")
_DEFAULT_BLOCK_SIZE = 2 * 1024 * 1024
_DEFAULT_MAX_BLOCKS = 32


@dataclass(frozen=True, slots=True)
class CanonicalRemoteFile:
    """Manifest-pinned remote canonical file identity."""

    url: str
    record_id: str
    filename: str
    checksum_algorithm: str
    checksum_value: str

    def __post_init__(self) -> None:
        for field_name in (
            "url",
            "record_id",
            "filename",
            "checksum_algorithm",
            "checksum_value",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{field_name} must be a non-empty trimmed string")
        if not self.url.startswith(("https://", "http://")):
            raise ValueError("remote canonical file URL must use HTTP(S)")


@dataclass(frozen=True, slots=True)
class RemoteFileMetadata:
    """Small-record metadata used to bind sparse reads to a canonical object."""

    size_bytes: int
    checksum_algorithm: str
    checksum_value: str

    def __post_init__(self) -> None:
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise TypeError("size_bytes must be an integer")
        if self.size_bytes <= 0:
            raise ValueError("size_bytes must be positive")


def _call_opener(opener: Callable[..., Any], request: Request):
    try:
        return opener(request, timeout=60)
    except TypeError:
        return opener(request)


def _normalise_checksum(raw: str) -> tuple[str, str]:
    value = raw.strip().lower()
    if ":" in value:
        algorithm, digest = value.split(":", 1)
    else:
        algorithm, digest = "md5", value
    if not algorithm or not digest:
        raise IntegrityError(f"invalid remote checksum metadata {raw!r}")
    return algorithm, digest


def _file_entries(document: dict[str, Any]) -> list[dict[str, Any]]:
    files = document.get("files")
    if isinstance(files, list):
        return [item for item in files if isinstance(item, dict)]
    if isinstance(files, dict):
        entries = files.get("entries")
        if isinstance(entries, dict):
            return [item for item in entries.values() if isinstance(item, dict)]
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
    return []


def _parse_zenodo_file_metadata(
    document: dict[str, Any],
    *,
    filename: str,
) -> RemoteFileMetadata:
    matches: list[dict[str, Any]] = []
    for entry in _file_entries(document):
        key = entry.get("key") or entry.get("filename") or entry.get("name")
        if key == filename:
            matches.append(entry)
    if len(matches) != 1:
        raise IntegrityError(
            f"Zenodo record metadata does not identify exactly one file {filename!r}"
        )
    entry = matches[0]
    checksum_raw = entry.get("checksum")
    size_raw = entry.get("size")
    if not isinstance(checksum_raw, str):
        raise IntegrityError(f"Zenodo metadata lacks checksum for {filename!r}")
    if isinstance(size_raw, bool) or not isinstance(size_raw, int) or size_raw <= 0:
        raise IntegrityError(f"Zenodo metadata lacks a valid size for {filename!r}")
    algorithm, digest = _normalise_checksum(checksum_raw)
    return RemoteFileMetadata(
        size_bytes=size_raw,
        checksum_algorithm=algorithm,
        checksum_value=digest,
    )


def verify_zenodo_file_identity(
    source: CanonicalRemoteFile,
    *,
    opener: Callable[..., Any] | None = None,
) -> RemoteFileMetadata:
    """Verify small Zenodo record metadata before any sparse HDF5 read.

    This does not recompute a whole-file digest. Instead it verifies that the
    published record identifies the requested filename with the manifest-pinned
    checksum and obtains the exact byte size used to validate every Content-Range.
    """

    if not isinstance(source, CanonicalRemoteFile):
        raise TypeError("source must be a CanonicalRemoteFile")
    resolved_opener = urlopen if opener is None else opener
    request = Request(
        f"https://zenodo.org/api/records/{source.record_id}",
        headers={"Accept": "application/json", "User-Agent": "VascuQuest/1"},
    )
    response = _call_opener(resolved_opener, request)
    try:
        payload = response.read()
    finally:
        response.close()
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("unable to decode canonical Zenodo record metadata") from exc
    if not isinstance(document, dict):
        raise IntegrityError("canonical Zenodo record metadata is not a JSON object")
    metadata = _parse_zenodo_file_metadata(document, filename=source.filename)
    expected_algorithm = source.checksum_algorithm.lower()
    expected_digest = source.checksum_value.lower()
    if metadata.checksum_algorithm != expected_algorithm:
        raise IntegrityError(
            f"canonical checksum algorithm mismatch for {source.filename!r}: "
            f"manifest {expected_algorithm}, Zenodo {metadata.checksum_algorithm}"
        )
    if metadata.checksum_value != expected_digest:
        raise IntegrityError(
            f"canonical checksum mismatch for {source.filename!r}: "
            f"manifest {expected_digest}, Zenodo {metadata.checksum_value}"
        )
    return metadata


class HTTPRangeReader(io.RawIOBase):
    """Seekable, read-only HTTP file backed exclusively by bounded Range requests."""

    def __init__(
        self,
        url: str,
        *,
        size_bytes: int,
        block_size: int = _DEFAULT_BLOCK_SIZE,
        max_blocks: int = _DEFAULT_MAX_BLOCKS,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(url, str) or not url or url != url.strip():
            raise ValueError("url must be a non-empty trimmed string")
        if not url.startswith(("https://", "http://")):
            raise ValueError("url must use HTTP(S)")
        for name, value in (
            ("size_bytes", size_bytes),
            ("block_size", block_size),
            ("max_blocks", max_blocks),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self._url = url
        self._size = size_bytes
        self._block_size = block_size
        self._max_blocks = max_blocks
        self._opener = urlopen if opener is None else opener
        self._position = 0
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._bytes_transferred = 0
        self._range_requests = 0

    @property
    def size_bytes(self) -> int:
        return self._size

    @property
    def bytes_transferred(self) -> int:
        return self._bytes_transferred

    @property
    def range_requests(self) -> int:
        return self._range_requests

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        self._checkClosed()
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self._checkClosed()
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("offset must be an integer")
        if whence == io.SEEK_SET:
            target = offset
        elif whence == io.SEEK_CUR:
            target = self._position + offset
        elif whence == io.SEEK_END:
            target = self._size + offset
        else:
            raise ValueError(f"unsupported whence {whence!r}")
        if target < 0:
            raise OSError("negative seek position")
        self._position = target
        return target

    def read(self, size: int = -1) -> bytes:
        self._checkClosed()
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("size must be an integer")
        if size < 0:
            raise OSError("unbounded reads are disabled for remote canonical artifacts")
        if size == 0 or self._position >= self._size:
            return b""
        stop = min(self._position + size, self._size)
        chunks: list[bytes] = []
        while self._position < stop:
            block_index = self._position // self._block_size
            block = self._block(block_index)
            block_start = block_index * self._block_size
            start_in_block = self._position - block_start
            take = min(stop - self._position, len(block) - start_in_block)
            if take <= 0:
                raise OSError("remote range cache returned an incomplete block")
            chunks.append(block[start_in_block : start_in_block + take])
            self._position += take
        return b"".join(chunks)

    def readinto(self, buffer: Any) -> int:
        view = memoryview(buffer).cast("B")
        data = self.read(len(view))
        view[: len(data)] = data
        return len(data)

    def close(self) -> None:
        self._cache.clear()
        super().close()

    def _block(self, block_index: int) -> bytes:
        cached = self._cache.get(block_index)
        if cached is not None:
            self._cache.move_to_end(block_index)
            return cached

        start = block_index * self._block_size
        if start >= self._size:
            return b""
        end = min(start + self._block_size, self._size) - 1
        request = Request(
            self._url,
            headers={
                "Range": f"bytes={start}-{end}",
                "Accept-Encoding": "identity",
                "User-Agent": "VascuQuest/1",
            },
        )
        response = _call_opener(self._opener, request)
        try:
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            if status != 206:
                raise OSError(
                    "remote source did not honor HTTP Range; refusing an unbounded full-file transfer"
                )
            content_range = response.headers.get("Content-Range")
            if not isinstance(content_range, str):
                raise OSError("remote range response lacks Content-Range")
            match = _CONTENT_RANGE.match(content_range.strip())
            if match is None:
                raise OSError(f"invalid remote Content-Range {content_range!r}")
            observed_start, observed_end, observed_total = (
                int(value) for value in match.groups()
            )
            if (observed_start, observed_end, observed_total) != (
                start,
                end,
                self._size,
            ):
                raise OSError(
                    "remote Content-Range does not match the requested canonical byte interval"
                )
            data = response.read()
        finally:
            response.close()

        expected = end - start + 1
        if not isinstance(data, (bytes, bytearray)) or len(data) != expected:
            observed = len(data) if isinstance(data, (bytes, bytearray)) else "non-bytes"
            raise OSError(
                f"remote range returned {observed} bytes; expected {expected}"
            )
        payload = bytes(data)
        self._bytes_transferred += len(payload)
        self._range_requests += 1
        self._cache[block_index] = payload
        self._cache.move_to_end(block_index)
        while len(self._cache) > self._max_blocks:
            self._cache.popitem(last=False)
        return payload


__all__ = [
    "CanonicalRemoteFile",
    "HTTPRangeReader",
    "RemoteFileMetadata",
    "verify_zenodo_file_identity",
]
