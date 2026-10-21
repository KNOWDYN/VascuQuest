"""Seekable HTTP byte-range access for remote HDF5 files.

The reader exposes a binary, seekable file-object contract suitable for h5py's
``fileobj`` driver. It never falls back to downloading a complete remote file
when a server ignores Range requests.
"""
from __future__ import annotations

from collections import OrderedDict
import io
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from vascuquest.errors import CapabilityError, IntegrityError

_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", re.I)


class HTTPRangeReader(io.RawIOBase):
    """Read-only seekable HTTP file using cached Range requests."""

    def __init__(
        self,
        url: str,
        *,
        block_size: int = 1 << 20,
        max_cache_blocks: int = 64,
        timeout_s: float = 60.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError("url must be an absolute HTTP(S) URL")
        if block_size < 64 * 1024:
            raise ValueError("block_size must be at least 65536 bytes")
        if max_cache_blocks < 1:
            raise ValueError("max_cache_blocks must be positive")
        self.url = url
        self.block_size = int(block_size)
        self.max_cache_blocks = int(max_cache_blocks)
        self.timeout_s = float(timeout_s)
        self._opener = opener or urlopen
        self._position = 0
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self.requests = 0
        self.bytes_fetched = 0
        self.size = self._discover_size()

    def _open(self, request: Request):
        try:
            return self._opener(request, timeout=self.timeout_s)
        except TypeError:
            return self._opener(request)

    @staticmethod
    def _header(response: Any, name: str) -> str | None:
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        value = headers.get(name)
        return None if value is None else str(value)

    @staticmethod
    def _status(response: Any) -> int:
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        return int(status or 200)

    def _discover_size(self) -> int:
        head = Request(self.url, method="HEAD", headers={"Accept-Encoding": "identity"})
        try:
            with self._open(head) as response:
                length = self._header(response, "Content-Length")
                if length is not None and int(length) > 0:
                    return int(length)
        except Exception:
            pass

        req = Request(
            self.url,
            headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
        )
        try:
            with self._open(req) as response:
                self.requests += 1
                status = self._status(response)
                content_range = self._header(response, "Content-Range")
                if status != 206 or not content_range:
                    raise CapabilityError("remote server does not support HTTP byte-range access")
                match = _CONTENT_RANGE_RE.fullmatch(content_range.strip())
                if not match or match.group(3) == "*":
                    raise IntegrityError("remote Content-Range does not declare total file size")
                payload = response.read()
                self.bytes_fetched += len(payload)
                return int(match.group(3))
        except (CapabilityError, IntegrityError):
            raise
        except Exception as exc:
            raise CapabilityError(f"unable to probe remote byte-range source {self.url!r}") from exc

    def _fetch_block(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached
        start = index * self.block_size
        if start >= self.size:
            return b""
        end = min(self.size - 1, start + self.block_size - 1)
        req = Request(
            self.url,
            headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"},
        )
        try:
            with self._open(req) as response:
                self.requests += 1
                status = self._status(response)
                if status != 206:
                    raise CapabilityError(
                        "remote server ignored Range request; refusing whole-file fallback"
                    )
                content_range = self._header(response, "Content-Range")
                if content_range:
                    match = _CONTENT_RANGE_RE.fullmatch(content_range.strip())
                    if not match:
                        raise IntegrityError("invalid Content-Range response")
                    got_start, got_end = int(match.group(1)), int(match.group(2))
                    if got_start != start or got_end != end:
                        raise IntegrityError(
                            f"remote Range mismatch: requested {start}-{end}, got {got_start}-{got_end}"
                        )
                payload = response.read()
        except (CapabilityError, IntegrityError):
            raise
        except Exception as exc:
            raise CapabilityError(f"remote range read failed for {self.url!r}") from exc
        expected = end - start + 1
        if len(payload) != expected:
            raise IntegrityError(
                f"remote Range returned {len(payload)} bytes, expected {expected}"
            )
        self.bytes_fetched += len(payload)
        self._cache[index] = payload
        self._cache.move_to_end(index)
        while len(self._cache) > self.max_cache_blocks:
            self._cache.popitem(last=False)
        return payload

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = int(offset)
        elif whence == io.SEEK_CUR:
            position = self._position + int(offset)
        elif whence == io.SEEK_END:
            position = self.size + int(offset)
        else:
            raise ValueError("invalid whence")
        if position < 0:
            raise ValueError("negative seek position")
        self._position = position
        return position

    def readinto(self, buffer: bytearray | memoryview) -> int:
        view = memoryview(buffer).cast("B")
        if self._position >= self.size or not view:
            return 0
        remaining = min(len(view), self.size - self._position)
        copied = 0
        while copied < remaining:
            block_index = self._position // self.block_size
            block = self._fetch_block(block_index)
            offset = self._position - block_index * self.block_size
            take = min(remaining - copied, len(block) - offset)
            if take <= 0:
                break
            view[copied : copied + take] = block[offset : offset + take]
            copied += take
            self._position += take
        return copied

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = max(0, self.size - self._position)
        output = bytearray(min(int(size), max(0, self.size - self._position)))
        count = self.readinto(output)
        return bytes(output[:count])

    def close(self) -> None:
        self._cache.clear()
        super().close()

    @property
    def transfer_stats(self) -> dict[str, int]:
        return {
            "requests": int(self.requests),
            "bytes_fetched": int(self.bytes_fetched),
            "remote_size_bytes": int(self.size),
            "cached_blocks": int(len(self._cache)),
        }


def open_remote_hdf5(
    url: str,
    *,
    block_size: int = 1 << 20,
    max_cache_blocks: int = 64,
    timeout_s: float = 60.0,
    opener: Callable[..., Any] | None = None,
):
    """Open a remote HDF5 file through a byte-range reader.

    Returns ``(h5py.File, HTTPRangeReader)``. The caller owns both and should
    close the HDF5 file before closing the reader.
    """
    try:
        import h5py  # type: ignore
    except ImportError as exc:
        raise CapabilityError(
            "remote HDF5 access requires optional dependency h5py; install VascuQuest with the 'path' extra"
        ) from exc
    reader = HTTPRangeReader(
        url,
        block_size=block_size,
        max_cache_blocks=max_cache_blocks,
        timeout_s=timeout_s,
        opener=opener,
    )
    try:
        handle = h5py.File(reader, "r")
    except Exception:
        reader.close()
        raise
    return handle, reader


__all__ = ["HTTPRangeReader", "open_remote_hdf5"]
