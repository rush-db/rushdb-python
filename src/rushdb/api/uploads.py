"""Sending an import file's bytes as the server's upload instructions say.

``s3-multipart`` puts parts to presigned URLs (no API auth header) a few at a
time and returns their ETags for the completion call; ``direct`` puts the
bytes to the API with the usual auth header.
"""

import functools
import os
import threading
import time
import urllib.parse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from ..common import RushDBError
from ..models.ingest import ImportFileUpload, ImportUploadProgress

if TYPE_CHECKING:
    from ..client import RushDB

UploadData = Union[str, "os.PathLike[str]", bytes, bytearray, memoryview, IO[bytes]]
"""File contents for an upload: a file path, bytes, or a binary file object."""

ProgressCallback = Callable[[ImportUploadProgress], None]

DEFAULT_UPLOAD_PARALLELISM = 4
DEFAULT_UPLOAD_RETRIES = 3
DEFAULT_UPLOAD_TIMEOUT = 600.0
"""Per-request timeout in seconds."""

T = TypeVar("T")


def _backoff(attempt: int) -> None:
    time.sleep(min(8.0, 0.25 * 2**attempt))


def _read_exactly(stream: IO[bytes], size: int) -> bytes:
    """Up to ``size`` bytes; fewer only at the end of the stream."""
    chunks: List[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("Upload file objects must be opened in binary mode ('rb')")
        chunks.append(bytes(chunk))
        remaining -= len(chunk)
    return b"".join(chunks)


class _Source:
    """Upload data: random access (can be re-read for a retry) or a stream."""

    size: Optional[int] = None
    random_access = True

    def read_range(self, start: int, end: int) -> bytes:
        raise NotImplementedError

    def stream(self) -> IO[bytes]:
        raise NotImplementedError


class _BytesSource(_Source):
    def __init__(self, data: Union[bytes, bytearray, memoryview]):
        self._view = memoryview(data).cast("B")
        self.size = self._view.nbytes

    def read_range(self, start: int, end: int) -> bytes:
        return bytes(self._view[start:end])


class _PathSource(_Source):
    def __init__(self, path: Union[str, "os.PathLike[str]"]):
        self._path = Path(path)
        self.size = self._path.stat().st_size

    def read_range(self, start: int, end: int) -> bytes:
        with open(self._path, "rb") as f:
            f.seek(start)
            return _read_exactly(f, end - start)


class _FileSource(_Source):
    def __init__(self, f: IO[bytes]):
        self._file = f
        self._lock = threading.Lock()
        seekable = False
        try:
            seekable = bool(f.seekable())
        except (AttributeError, OSError, ValueError):
            pass
        if seekable:
            self._start = f.tell()
            end = f.seek(0, os.SEEK_END)
            f.seek(self._start)
            self.size = end - self._start
        else:
            self._start = 0
            self.size = None
            self.random_access = False

    def read_range(self, start: int, end: int) -> bytes:
        with self._lock:
            self._file.seek(self._start + start)
            return _read_exactly(self._file, end - start)

    def stream(self) -> IO[bytes]:
        return self._file


def size_of_file_object(f: Any) -> Optional[int]:
    """Bytes left in a seekable file object, or ``None``."""
    return _FileSource(f).size


def source_of(data: UploadData) -> _Source:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return _BytesSource(data)
    if isinstance(data, (str, os.PathLike)):
        return _PathSource(data)
    if hasattr(data, "read"):
        return _FileSource(data)
    raise TypeError(
        "Unsupported upload data: pass a file path, bytes or a binary file object"
    )


def _is_retryable(error: BaseException) -> bool:
    if not isinstance(error, RushDBError):
        return False
    status = error.status
    return status is None or status == 429 or status >= 500


def _with_retries(attempts: int, run: Callable[[], T]) -> T:
    attempts = max(1, attempts)
    for attempt in range(attempts):
        try:
            return run()
        except RushDBError as error:
            if not _is_retryable(error) or attempt == attempts - 1:
                raise
            _backoff(attempt)
    raise AssertionError("unreachable")


def _header(headers: Dict[str, str], name: str) -> Optional[str]:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def upload_file_content(
    client: "RushDB",
    file: ImportFileUpload,
    data: UploadData,
    parallelism: int = DEFAULT_UPLOAD_PARALLELISM,
    retries: int = DEFAULT_UPLOAD_RETRIES,
    timeout: float = DEFAULT_UPLOAD_TIMEOUT,
    on_progress: Optional[ProgressCallback] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Sends one file's bytes as its upload instructions say.

    Returns the parts with their ETags for ``s3-multipart``, ``None`` for
    ``direct``.
    """
    source = source_of(data)
    total = file["size"]
    if source.size is not None and source.size != total:
        raise ValueError(
            f"File {file['id']} was announced as {total} bytes "
            f"but the data has {source.size}"
        )

    progress_lock = threading.Lock()
    loaded = 0

    def progress(sent: int) -> None:
        nonlocal loaded
        with progress_lock:
            loaded += sent
            if on_progress is not None:
                on_progress({"fileId": file["id"], "loaded": loaded, "total": total})

    upload = file["upload"]
    if upload["mode"] == "direct":
        url = urllib.parse.urljoin(client.base_url + "/", upload["path"])
        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(total),
        }
        method = upload.get("method") or "PUT"

        if source.random_access:

            def send_all() -> None:
                if isinstance(source, _PathSource):
                    with open(source._path, "rb") as f:
                        client._send_raw(
                            method, url, f, headers, timeout, "upload failed"
                        )
                elif isinstance(source, _FileSource):
                    with source._lock:
                        source._file.seek(source._start)
                        client._send_raw(
                            method, url, source._file, headers, timeout, "upload failed"
                        )
                else:
                    client._send_raw(
                        method,
                        url,
                        source.read_range(0, total),
                        headers,
                        timeout,
                        "upload failed",
                    )

            _with_retries(retries, send_all)
        else:
            # A stream is read once: no retry.
            client._send_raw(
                method, url, source.stream(), headers, timeout, "upload failed"
            )
        progress(total)
        return None

    part_size = upload["partSize"]
    urls = {part["partNumber"]: part["url"] for part in upload["parts"]}

    def jobs() -> Iterator[Tuple[int, Callable[[], bytes]]]:
        if source.random_access:
            for part in upload["parts"]:
                number = part["partNumber"]
                start = (number - 1) * part_size
                end = min(start + part_size, total)
                yield number, functools.partial(source.read_range, start, end)
            return
        stream = source.stream()
        number = 0
        sent = 0
        while True:
            body = _read_exactly(stream, part_size)
            if not body:
                break
            number += 1
            sent += len(body)
            if number not in urls or sent > total:
                raise ValueError(
                    f"File {file['id']} has more data than the {total} bytes announced"
                )
            yield number, functools.partial(bytes, body)
        if sent != total:
            raise ValueError(
                f"File {file['id']} was announced as {total} bytes "
                f"but the stream had {sent}"
            )

    def put_part(number: int, read: Callable[[], bytes]) -> Dict[str, Any]:
        body = read()

        def attempt() -> str:
            _, headers, _ = client._send_raw(
                "PUT",
                urls[number],
                body,
                {"Content-Type": "application/octet-stream"},
                timeout,
                f"upload of part {number} failed",
            )
            etag = _header(headers, "ETag")
            if not etag:
                raise RushDBError(
                    f"Part {number} uploaded but the storage returned no ETag header",
                    status=400,
                )
            return etag

        etag = _with_retries(retries, attempt)
        progress(len(body))
        return {"partNumber": number, "etag": etag}

    done: List[Dict[str, Any]] = []
    failure: Optional[BaseException] = None
    running: Set["Future[Dict[str, Any]]"] = set()

    def collect(finished: Set["Future[Dict[str, Any]]"]) -> None:
        nonlocal failure
        for future in finished:
            running.discard(future)
            error = future.exception()
            if error is not None:
                failure = failure or error
            else:
                done.append(future.result())

    with ThreadPoolExecutor(max_workers=max(1, parallelism)) as pool:
        try:
            for number, read in jobs():
                running.add(pool.submit(put_part, number, read))
                if len(running) >= max(1, parallelism):
                    finished, _ = wait(running, return_when=FIRST_COMPLETED)
                    collect(finished)
                if failure is not None:
                    break
        except (
            BaseException
        ) as error:  # the source failed: stop after the parts in flight
            failure = failure or error
        finished, _ = wait(running)
        collect(finished)
    if failure is not None:
        raise failure
    return sorted(done, key=lambda part: part["partNumber"])
