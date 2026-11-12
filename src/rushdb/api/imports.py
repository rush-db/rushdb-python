"""Background file imports for the RushDB Python SDK (RushDB Cloud only)."""

import os
import threading
import time
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
    cast,
)

from ..common import CloudOnlyError
from ..direct.capabilities import CLOUD_ONLY_METHODS
from ..models.api_response import ApiResponse
from ..models.ingest import (
    FINISHED_IMPORT_RUN_STATUSES,
    CreatedImport,
    ImportFile,
    ImportFileInput,
    ImportFileLink,
    ImportFileMapping,
    ImportFileSettings,
    ImportFilesLink,
    ImportFilesProgress,
    ImportFileUpload,
    ImportPreview,
    ImportRun,
    ImportRunKind,
)
from .base import BaseAPI
from .uploads import (
    DEFAULT_UPLOAD_PARALLELISM,
    DEFAULT_UPLOAD_RETRIES,
    DEFAULT_UPLOAD_TIMEOUT,
    ProgressCallback,
    UploadData,
    source_of,
    upload_file_content,
)

if TYPE_CHECKING:
    from ..client import RushDB

ImportFileSource = Union[str, "os.PathLike[str]", Any, Dict[str, Any]]
"""A file for ``imports.import_files``: a path, a binary file object, or a dict
``{"data", "name"?, "size"?, "label"?, "mapping"?}`` (``data`` is a path, bytes
or a binary file object)."""


def _wrap(response: Dict[str, Any]) -> ApiResponse:
    return ApiResponse(
        data=response.get("data"),
        success=response.get("success", True),
        total=response.get("total"),
    )


def _guard(client: "RushDB", namespace: str, method: str) -> None:
    if getattr(client, "direct", False) is True:
        name = f"{namespace}.{method}"
        raise CloudOnlyError(name, CLOUD_ONLY_METHODS[name])


class ImportsAPI(BaseAPI):
    """Background file imports (CSV, JSON, NDJSON, Parquet, optionally
    gzip-compressed). Create an import with its files, upload them, preview the
    mapping, start; the run continues on the server without the client.

    Accessed via ``db.imports``. **RushDB Cloud only**: in direct mode every
    method raises ``CloudOnlyError`` before sending anything.

    Example::

        >>> run = db.imports.import_files(
        ...     ["customers.csv", "orders.csv.gz"],
        ...     mappings={0: {"keyColumn": "id"}},
        ...     wait=True,
        ... )
        >>> run.data["status"], run.data["recordsWritten"]
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)
        # Upload instructions from `create`/`add_files`, so `upload` can take ids.
        self._uploads: Dict[str, ImportFileUpload] = {}
        self._uploads_lock = threading.Lock()

    def _guard(self, method: str) -> None:
        _guard(self.client, "imports", method)

    def _remember(self, import_id: str, files: Sequence[ImportFileUpload]) -> None:
        with self._uploads_lock:
            for file in files or []:
                self._uploads[f"{import_id}/{file['id']}"] = file

    def _forget(self, import_id: str, file_id: str) -> None:
        with self._uploads_lock:
            self._uploads.pop(f"{import_id}/{file_id}", None)

    def create(
        self, files: List[ImportFileInput], name: Optional[str] = None
    ) -> "ApiResponse[CreatedImport]":
        """Create a draft import with its files (name and exact size in bytes;
        up to 50). Each returned file carries its ``upload`` instructions.

        Args:
            files: ``[{"name": "orders.csv", "size": 1024, "label"?: "Order"}]``.
                The extension picks the parser.
            name: A name for the import.
        """
        self._guard("create")
        body: Dict[str, Any] = {"files": files}
        if name is not None:
            body["name"] = name
        response = _wrap(self.client._make_request("POST", "/imports", body))
        if isinstance(response.data, dict):
            self._remember(response.data["id"], response.data.get("files") or [])
        return response

    def add_files(
        self, import_id: str, files: List[ImportFileInput]
    ) -> "ApiResponse[List[ImportFileUpload]]":
        """Add files to a draft import."""
        self._guard("add_files")
        response = _wrap(
            self.client._make_request(
                "POST", f"/imports/{import_id}/files", {"files": files}
            )
        )
        if isinstance(response.data, list):
            self._remember(import_id, response.data)
        return response

    def remove_file(self, import_id: str, file_id: str) -> ApiResponse:
        """Remove a file from a draft import. ``data`` is ``{"deleted": True}``."""
        self._guard("remove_file")
        self._forget(import_id, file_id)
        return _wrap(
            self.client._make_request("DELETE", f"/imports/{import_id}/files/{file_id}")
        )

    def upload(
        self,
        import_id: str,
        file: Union[str, ImportFileUpload],
        data: UploadData,
        *,
        parallelism: int = DEFAULT_UPLOAD_PARALLELISM,
        retries: int = DEFAULT_UPLOAD_RETRIES,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
        on_progress: Optional[ProgressCallback] = None,
    ) -> "ApiResponse[ImportFile]":
        """Upload one file's bytes and complete it.

        With ``s3-multipart`` upload instructions, parts go to their presigned
        URLs ``parallelism`` at a time and their ETags are sent on completion;
        with ``direct``, the bytes go through the API. Failed requests (network
        errors, 429, 5xx) are retried; a non-seekable stream sent ``direct`` is
        read once and not retried.

        Args:
            import_id: The import's id.
            file: A file from ``create``/``add_files`` (with its ``upload``
                instructions), or its id when this client created it.
            data: A file path (``str`` or ``Path``), ``bytes``/``bytearray``/
                ``memoryview``, or a binary file object. Its size must match
                the size announced for the file.
            parallelism: Parts uploaded at once (``s3-multipart``). Default 4.
            retries: Attempts per part (or per direct upload). Default 3.
            timeout: Per-request timeout in seconds. Default 600.
            on_progress: Called with ``{"fileId", "loaded", "total"}`` as
                bytes are sent (from upload threads).

        Returns:
            ApiResponse: The completed file.
        """
        self._guard("upload")
        if isinstance(file, str):
            with self._uploads_lock:
                target = self._uploads.get(f"{import_id}/{file}")
            if target is None:
                raise ValueError(
                    f"No upload instructions for file {file}: pass the file "
                    "returned by imports.create() or imports.add_files()"
                )
        else:
            target = file
        parts = upload_file_content(
            self.client,
            target,
            data,
            parallelism=parallelism,
            retries=retries,
            timeout=timeout,
            on_progress=on_progress,
        )
        response = _wrap(
            self.client._make_request(
                "POST",
                f"/imports/{import_id}/files/{target['id']}/complete",
                {"parts": parts} if parts is not None else {},
            )
        )
        self._forget(import_id, target["id"])
        return response

    def preview(
        self,
        import_id: str,
        files: Optional[List[ImportFileSettings]] = None,
    ) -> "ApiResponse[ImportPreview]":
        """Column types, samples, personal-data hints, a suggested key per file
        and suggested links between files. Writes nothing.

        Args:
            files: Optional settings per file (``{"id", "label"?, "mapping"?}``).
        """
        self._guard("preview")
        body: Dict[str, Any] = {} if files is None else {"files": files}
        return _wrap(
            self.client._make_request("POST", f"/imports/{import_id}/preview", body)
        )

    def start(
        self,
        import_id: str,
        files: Optional[List[ImportFileSettings]] = None,
        links: Optional[List[ImportFileLink]] = None,
    ) -> "ApiResponse[ImportRun]":
        """Start the run with the files' labels and mappings and the links
        between files.

        Args:
            files: Settings per file: ``{"id", "label"?, "mapping"?}``, where a
                mapping is ``{"keyColumn", "skip", "hash", "rename", "types",
                "delimiter"}``.
            links: ``{"sourceFileId", "sourceColumn", "targetFileId",
                "targetColumn", "type"}``.
        """
        self._guard("start")
        body: Dict[str, Any] = {}
        if files is not None:
            body["files"] = files
        if links:
            body["links"] = links
        return _wrap(
            self.client._make_request("POST", f"/imports/{import_id}/start", body)
        )

    def get(self, import_id: str) -> "ApiResponse[ImportRun]":
        """One import run (a file import or a connection sync) with its progress."""
        self._guard("get")
        return _wrap(self.client._make_request("GET", f"/imports/{import_id}"))

    def list(
        self,
        kind: Optional[ImportRunKind] = None,
        connection_id: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> "ApiResponse[List[ImportRun]]":
        """Import runs of the project, newest first; ``total`` is the count.

        Args:
            kind: ``"file"`` or ``"sync"``.
            connection_id: Only the syncs of this connection.
            limit: 1–100.
            skip: Runs to skip.
        """
        self._guard("list")
        params: Dict[str, Any] = {
            key: value
            for key, value in (
                ("kind", kind),
                ("connectionId", connection_id),
                ("limit", limit),
                ("skip", skip),
            )
            if value is not None
        }
        return _wrap(
            self.client._make_request("GET", "/imports", params=params or None)
        )

    def cancel(self, import_id: str) -> "ApiResponse[ImportRun]":
        """Ask a queued or running run to stop; it ends ``cancelled``."""
        self._guard("cancel")
        return _wrap(
            self.client._make_request("POST", f"/imports/{import_id}/cancel", {})
        )

    def retry(self, import_id: str) -> "ApiResponse[ImportRun]":
        """Run a failed or partial file import again."""
        self._guard("retry")
        return _wrap(
            self.client._make_request("POST", f"/imports/{import_id}/retry", {})
        )

    def delete(self, import_id: str) -> ApiResponse:
        """Delete an import and its uploaded files (records already written stay)."""
        self._guard("delete")
        return _wrap(self.client._make_request("DELETE", f"/imports/{import_id}"))

    def wait(
        self,
        import_id: str,
        interval: float = 2.0,
        timeout: Optional[float] = None,
        on_progress: Optional[Callable[[ImportRun], None]] = None,
    ) -> "ApiResponse[ImportRun]":
        """Poll a run until it is ``completed``, ``partial``, ``failed`` or
        ``cancelled``, and return it.

        Args:
            interval: Seconds between polls. Default 2.
            timeout: Give up after this many seconds. Default: no limit.
            on_progress: Called with the run after every poll.

        Raises:
            TimeoutError: The run had not finished within ``timeout``.
        """
        self._guard("wait")
        interval = max(0.0, interval)
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            response = self.get(import_id)
            run = cast(ImportRun, response.data)
            if on_progress is not None:
                on_progress(run)
            if run["status"] in FINISHED_IMPORT_RUN_STATUSES:
                return response
            if deadline is not None and time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"Import {import_id} is still {run['status']} after {timeout} s"
                )
            time.sleep(interval)

    def import_files(
        self,
        files: Sequence[ImportFileSource],
        *,
        name: Optional[str] = None,
        links: Optional[List[ImportFilesLink]] = None,
        mappings: Optional[Mapping[Union[str, int], ImportFileMapping]] = None,
        wait: bool = False,
        wait_interval: float = 2.0,
        wait_timeout: Optional[float] = None,
        parallelism: int = DEFAULT_UPLOAD_PARALLELISM,
        retries: int = DEFAULT_UPLOAD_RETRIES,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
        on_progress: Optional[Callable[[ImportFilesProgress], None]] = None,
    ) -> "ApiResponse[ImportRun]":
        """Import files in one call: create → upload every file → start
        (→ wait when ``wait=True``).

        Args:
            files: Each a file path, a binary file object, or a dict
                ``{"data", "name"?, "size"?, "label"?, "mapping"?}``. Names
                and sizes come from the path, the file object or the bytes
                when not given; a non-seekable stream needs ``size``. The
                name's extension picks the parser.
            name: A name for the import.
            links: Links between files, naming them by position or name:
                ``{"source", "sourceColumn", "target", "targetColumn", "type"}``.
            mappings: Mappings by file name or position, in addition to
                ``mapping`` on each file.
            wait: Wait for the run to finish (default: return once started).
            wait_interval: Seconds between polls while waiting.
            wait_timeout: Give up waiting after this many seconds
                (``TimeoutError``).
            parallelism, retries, timeout: As for ``upload``.
            on_progress: Called with ``{"phase": "upload", "fileId", "loaded",
                "total"}`` while uploading, then ``{"phase": "run", "run"}``.

        Returns:
            ApiResponse: The started run, or the finished one with ``wait``.
        """
        self._guard("import_files")
        sources: List[Dict[str, Any]] = []
        for index, file in enumerate(files):
            entry: Dict[str, Any] = (
                dict(file) if isinstance(file, dict) else {"data": file}
            )
            data = entry.get("data")
            file_name = entry.get("name")
            if file_name is None:
                if isinstance(data, (str, os.PathLike)):
                    file_name = os.path.basename(os.fspath(data))
                elif isinstance(getattr(data, "name", None), str):
                    file_name = os.path.basename(data.name)  # type: ignore[union-attr]
            if not isinstance(file_name, str) or not file_name:
                raise ValueError(
                    f"File {index} needs a name (its extension picks the parser)"
                )
            size = entry.get("size")
            if size is None:
                size = source_of(data).size  # type: ignore[arg-type]
            if not isinstance(size, int):
                raise ValueError(
                    f"File {index} ({file_name}) is a stream: pass its size in bytes"
                )
            entry["name"] = file_name
            entry["size"] = size
            sources.append(entry)

        announced: List[ImportFileInput] = []
        for source in sources:
            item: ImportFileInput = {"name": source["name"], "size": source["size"]}
            if source.get("label"):
                item["label"] = source["label"]
            announced.append(item)
        created = self.create(announced, name=name)
        run = created.data
        run_files = run["files"]

        def file_id_of(ref: Union[int, str]) -> str:
            position = (
                ref
                if isinstance(ref, int)
                else next(
                    (i for i, source in enumerate(sources) if source["name"] == ref),
                    -1,
                )
            )
            if not 0 <= position < len(run_files):
                raise ValueError(f"No file {ref!r} in this import")
            return run_files[position]["id"]

        resolved_links: List[ImportFileLink] = []
        for link in links or []:
            resolved_links.append(
                {
                    "sourceFileId": file_id_of(link["source"]),
                    "sourceColumn": link["sourceColumn"],
                    "targetFileId": file_id_of(link["target"]),
                    "targetColumn": link["targetColumn"],
                    "type": link["type"],
                }
            )

        def upload_progress(progress: Any) -> None:
            if on_progress is not None:
                on_progress({"phase": "upload", **progress})

        for index, source in enumerate(sources):
            self.upload(
                run["id"],
                run_files[index],
                source["data"],
                parallelism=parallelism,
                retries=retries,
                timeout=timeout,
                on_progress=upload_progress,
            )

        settings: List[ImportFileSettings] = []
        for index, source in enumerate(sources):
            mapping = source.get("mapping")
            if mapping is None and mappings:
                mapping = mappings.get(source["name"])
                if mapping is None:
                    mapping = mappings.get(index)
                if mapping is None:
                    mapping = mappings.get(str(index))
            setting: ImportFileSettings = {"id": run_files[index]["id"]}
            if mapping:
                setting["mapping"] = mapping
            settings.append(setting)

        started = self.start(run["id"], files=settings, links=resolved_links or None)
        if on_progress is not None:
            on_progress({"phase": "run", "run": started.data})
        if not wait:
            return started

        def run_progress(current: ImportRun) -> None:
            if on_progress is not None:
                on_progress({"phase": "run", "run": current})

        return self.wait(
            run["id"],
            interval=wait_interval,
            timeout=wait_timeout,
            on_progress=run_progress,
        )
