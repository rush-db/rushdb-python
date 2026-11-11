"""db.imports against a mocked HTTP layer: S3 multipart and direct uploads,
waiting on a run, and import_files end to end."""

import io
import json
import threading
import urllib.error
import urllib.parse
from unittest import mock

import pytest

from rushdb import RushDB, RushDBError

API = "https://api.test/api/v1"
S3 = "https://bucket.s3.test/"


class _Resp:
    def __init__(self, status=200, body=b"", headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def json_answer(data, total=None):
    body = {"success": True, "data": data}
    if total is not None:
        body["total"] = total
    return _Resp(200, json.dumps(body).encode("utf-8"))


def http_error(url, status, body=b""):
    return urllib.error.HTTPError(url, status, "error", {}, io.BytesIO(body))


class Calls:
    """Records every request and answers it with ``answer(call, calls)``."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, request, timeout=None):
        data = request.data
        if data is not None and hasattr(data, "read"):
            data = data.read()
        headers = {key.lower(): value for key, value in request.header_items()}
        body = data
        if headers.get("content-type") == "application/json" and data:
            body = json.loads(data.decode("utf-8"))
        call = {
            "url": request.full_url,
            "method": request.get_method(),
            "headers": headers,
            "body": body,
            "timeout": timeout,
        }
        with self.lock:
            self.calls.append(call)
            snapshot = list(self.calls)
        result = self.answer(call, snapshot)
        if isinstance(result, Exception):
            raise result
        return result

    def api(self):
        return [call for call in self.calls if call["url"].startswith(API)]

    def s3(self):
        return [call for call in self.calls if call["url"].startswith(S3)]


@pytest.fixture
def http():
    """Patch urlopen; ``http(answer)`` installs the answer and returns the calls."""
    patches = []

    def install(answer):
        calls = Calls(answer)
        patcher = mock.patch("urllib.request.urlopen", side_effect=calls)
        patcher.start()
        patches.append(patcher)
        return calls

    with mock.patch("rushdb.api.uploads._backoff"):
        yield install
    for patcher in patches:
        patcher.stop()


def db():
    return RushDB("token", url="https://api.test")


def run(**patch):
    base = {
        "id": "imp-1",
        "kind": "file",
        "trigger": "api",
        "status": "draft",
        "name": None,
        "connectionId": None,
        "recordsWritten": 0,
        "recordsDeleted": 0,
        "linksCreated": 0,
        "errorCount": 0,
        "progress": {},
        "errorSample": [],
        "summary": None,
        "error": None,
        "startedBy": None,
        "startedAt": None,
        "finishedAt": None,
        "createdAt": "2026-01-01T00:00:00.000Z",
        "updatedAt": "2026-01-01T00:00:00.000Z",
    }
    base.update(patch)
    return base


def file_dto(file_id, name, size):
    return {
        "id": file_id,
        "name": name,
        "format": "csv",
        "compression": None,
        "size": size,
        "status": "uploading",
        "label": "Row",
        "mapping": None,
        "rowsDone": 0,
        "bytesDone": 0,
        "errorCount": 0,
        "error": None,
    }


def s3_file(file_id, size, part_size):
    count = max(1, -(-size // part_size))
    return {
        **file_dto(file_id, f"{file_id}.csv", size),
        "upload": {
            "mode": "s3-multipart",
            "partSize": part_size,
            "expiresAt": "2026-01-01T01:00:00.000Z",
            "parts": [
                {
                    "partNumber": n,
                    "url": f"{S3}{file_id}?partNumber={n}&X-Amz-Signature=sig",
                }
                for n in range(1, count + 1)
            ],
        },
    }


def direct_file(file_id, size):
    return {
        **file_dto(file_id, f"{file_id}.csv", size),
        "upload": {
            "mode": "direct",
            "method": "PUT",
            "path": f"/api/v1/imports/imp-1/files/{file_id}/content",
        },
    }


def data_of(length):
    return bytes(index % 251 for index in range(length))


def part_number(url):
    return int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["partNumber"][0])


def s3_and_api(api, fail_first=None):
    """Answers part PUTs with an ETag (``fail_first`` fails once with 503)."""

    def answer(call, calls):
        if call["url"].startswith(S3):
            number = part_number(call["url"])
            attempts = len([c for c in calls if c["url"] == call["url"]])
            if number == fail_first and attempts == 1:
                return http_error(call["url"], 503, b"<Error>SlowDown</Error>")
            return _Resp(200, b"", {"ETag": f'"etag-{number}"'})
        return api(call)

    return answer


# ── s3-multipart ─────────────────────────────────────────────────────────────


def test_multipart_puts_every_part_retries_a_failed_one_and_completes(http):
    file = s3_file("f1", 10, 4)

    def api(call):
        if call["url"] == f"{API}/imports":
            return json_answer({**run(), "files": [file]})
        if call["url"].endswith("/complete"):
            return json_answer({**file_dto("f1", "f1.csv", 10), "status": "uploaded"})
        return http_error(call["url"], 404)

    calls = http(s3_and_api(api, fail_first=2))
    client = db()

    created = client.imports.create([{"name": "f1.csv", "size": 10}])
    assert calls.calls[0]["method"] == "POST"
    assert calls.calls[0]["body"] == {"files": [{"name": "f1.csv", "size": 10}]}

    progress = []
    data = data_of(10)
    result = client.imports.upload(
        created.data["id"],
        "f1",
        data,
        parallelism=2,
        on_progress=lambda p: progress.append(p["loaded"]),
    )

    puts = calls.s3()
    assert len(puts) == 4  # three parts, one retried
    for put in puts:
        assert put["method"] == "PUT"
        assert "authorization" not in put["headers"]
    sizes = {part_number(put["url"]): len(put["body"]) for put in puts}
    assert sizes == {1: 4, 2: 4, 3: 2}
    third = next(put for put in puts if part_number(put["url"]) == 3)
    assert third["body"] == data[8:]

    complete = calls.calls[-1]
    assert complete["url"] == f"{API}/imports/imp-1/files/f1/complete"
    assert complete["method"] == "POST"
    assert complete["headers"]["authorization"] == "Bearer token"
    assert complete["body"] == {
        "parts": [
            {"partNumber": 1, "etag": '"etag-1"'},
            {"partNumber": 2, "etag": '"etag-2"'},
            {"partNumber": 3, "etag": '"etag-3"'},
        ]
    }
    assert progress[-1] == 10
    assert result.data["status"] == "uploaded"


def test_multipart_reads_parts_from_a_path(http, tmp_path):
    path = tmp_path / "f1.csv"
    data = data_of(9)
    path.write_bytes(data)
    calls = http(s3_and_api(lambda call: json_answer(file_dto("f1", "f1.csv", 9))))

    db().imports.upload("imp-1", s3_file("f1", 9, 4), path)

    bodies = {part_number(put["url"]): put["body"] for put in calls.s3()}
    assert bodies == {1: data[:4], 2: data[4:8], 3: data[8:]}
    assert len(calls.calls[-1]["body"]["parts"]) == 3


def test_multipart_cuts_a_non_seekable_stream_into_parts(http):
    data = data_of(9)

    class Pipe(io.RawIOBase):
        """Unseekable, and returns short reads."""

        def __init__(self):
            self._buffer = io.BytesIO(data)

        def readable(self):
            return True

        def seekable(self):
            return False

        def read(self, size=-1):
            return self._buffer.read(min(size, 3) if size > 0 else size)

    calls = http(s3_and_api(lambda call: json_answer(file_dto("f1", "f1.csv", 9))))

    db().imports.upload("imp-1", s3_file("f1", 9, 4), Pipe(), parallelism=1)

    bodies = sorted((part_number(put["url"]), put["body"]) for put in calls.s3())
    assert bodies == [(1, data[:4]), (2, data[4:8]), (3, data[8:])]


def test_multipart_uploads_a_file_object_from_its_position(http):
    data = data_of(10)
    f = io.BytesIO(b"xx" + data)
    f.read(2)
    calls = http(s3_and_api(lambda call: json_answer(file_dto("f1", "f1.csv", 10))))

    db().imports.upload("imp-1", s3_file("f1", 10, 4), f)

    bodies = {part_number(put["url"]): put["body"] for put in calls.s3()}
    assert b"".join(bodies[n] for n in sorted(bodies)) == data


def test_a_size_mismatch_fails_before_sending_anything(http):
    calls = http(s3_and_api(lambda call: json_answer({})))
    with pytest.raises(ValueError, match="announced as 10 bytes"):
        db().imports.upload("imp-1", s3_file("f1", 10, 4), data_of(9))
    assert calls.calls == []


def test_a_4xx_part_upload_is_not_retried(http):
    calls = http(lambda call, calls: http_error(call["url"], 403, b"<Error/>"))
    with pytest.raises(RushDBError) as raised:
        db().imports.upload("imp-1", s3_file("f1", 4, 4), data_of(4), retries=3)
    assert raised.value.status == 403
    assert len(calls.calls) == 1


def test_a_part_failing_every_attempt_stops_the_upload(http):
    calls = http(lambda call, calls: http_error(call["url"], 500))
    with pytest.raises(RushDBError):
        db().imports.upload("imp-1", s3_file("f1", 4, 4), data_of(4), retries=2)
    assert len(calls.calls) == 2  # no completion call


def test_upload_needs_the_file_object_for_files_this_client_did_not_create(http):
    http(lambda call, calls: json_answer({}))
    with pytest.raises(ValueError, match="No upload instructions"):
        db().imports.upload("imp-1", "f1", data_of(1))


# ── direct ───────────────────────────────────────────────────────────────────


def test_direct_puts_the_raw_bytes_with_the_auth_header_then_completes(http):
    calls = http(lambda call, calls: json_answer(file_dto("f1", "f1.csv", 5)))

    db().imports.upload("imp-1", direct_file("f1", 5), data_of(5))

    put, complete = calls.calls
    assert put["url"] == f"{API}/imports/imp-1/files/f1/content"
    assert put["method"] == "PUT"
    assert put["headers"]["authorization"] == "Bearer token"
    assert put["headers"]["content-type"] == "application/octet-stream"
    assert put["body"] == data_of(5)
    assert complete["url"] == f"{API}/imports/imp-1/files/f1/complete"
    assert complete["method"] == "POST"
    assert complete["body"] == {}


def test_direct_streams_a_path_and_retries_a_5xx(http, tmp_path):
    path = tmp_path / "f1.csv"
    path.write_bytes(b"a,b\n1,2")

    def answer(call, calls):
        if call["url"].endswith("/content") and len(calls) == 1:
            return http_error(call["url"], 502)
        return json_answer(file_dto("f1", "f1.csv", 7))

    calls = http(answer)

    db().imports.upload("imp-1", direct_file("f1", 7), str(path))

    puts = [call for call in calls.calls if call["url"].endswith("/content")]
    assert [put["body"] for put in puts] == [b"a,b\n1,2", b"a,b\n1,2"]
    assert puts[1]["headers"]["content-length"] == "7"


# ── runs ─────────────────────────────────────────────────────────────────────


def test_wait_polls_until_the_run_finishes(http):
    statuses = iter(["queued", "running", "completed"])
    calls = http(lambda call, calls: json_answer(run(status=next(statuses))))
    seen = []

    result = db().imports.wait(
        "imp-1", interval=0.001, on_progress=lambda r: seen.append(r["status"])
    )

    assert result.data["status"] == "completed"
    assert seen == ["queued", "running", "completed"]
    assert all(
        call["method"] == "GET" and call["url"] == f"{API}/imports/imp-1"
        for call in calls.calls
    )


def test_wait_gives_up_after_the_timeout(http):
    http(lambda call, calls: json_answer(run(status="running")))
    with pytest.raises(TimeoutError, match="still running"):
        db().imports.wait("imp-1", interval=0.005, timeout=0.012)


def test_list_filters_and_run_actions_map_to_their_routes(http):
    calls = http(lambda call, calls: json_answer([], total=0))
    client = db()

    listed = client.imports.list(kind="sync", connection_id="c 1", limit=10)
    client.imports.cancel("imp-1")
    client.imports.retry("imp-1")
    client.imports.delete("imp-1")
    client.imports.preview("imp-1", files=[{"id": "f1", "label": "Order"}])
    client.imports.start("imp-1")
    client.imports.add_files("imp-1", [{"name": "b.csv", "size": 3}])
    client.imports.remove_file("imp-1", "f2")

    assert listed.total == 0
    assert [f"{c['method']} {c['url'][len(API):]}" for c in calls.calls] == [
        "GET /imports?kind=sync&connectionId=c+1&limit=10",
        "POST /imports/imp-1/cancel",
        "POST /imports/imp-1/retry",
        "DELETE /imports/imp-1",
        "POST /imports/imp-1/preview",
        "POST /imports/imp-1/start",
        "POST /imports/imp-1/files",
        "DELETE /imports/imp-1/files/f2",
    ]
    assert calls.calls[4]["body"] == {"files": [{"id": "f1", "label": "Order"}]}
    assert calls.calls[5]["body"] == {}
    assert calls.calls[6]["body"] == {"files": [{"name": "b.csv", "size": 3}]}


def test_start_passes_hashed_columns_from_the_preview(http):
    preview = {
        "files": [
            {
                "fileId": "f1",
                "name": "customers.csv",
                "label": "Customer",
                "rows": 2,
                "columns": [
                    {"name": "id", "type": "number", "suggestion": "include"},
                    {
                        "name": "email",
                        "type": "string",
                        "samples": ["a***@example.com"],
                        "pii": {
                            "kind": "email",
                            "source": "name",
                            "confidence": 0.9,
                            "reason": "The name suggests an email",
                        },
                        "suggestion": "hash",
                    },
                ],
                "errors": [],
            }
        ],
        "links": [],
    }
    calls = http(lambda call, calls: json_answer(preview))
    client = db()

    data = client.imports.preview("imp-1").data
    email = next(c for c in data["files"][0]["columns"] if c["suggestion"] == "hash")
    assert email["pii"]["kind"] == "email"
    client.imports.start(
        "imp-1",
        files=[{"id": "f1", "mapping": {"keyColumn": "id", "hash": [email["name"]]}}],
    )
    assert calls.calls[1]["body"] == {
        "files": [{"id": "f1", "mapping": {"keyColumn": "id", "hash": ["email"]}}]
    }


# ── import_files ─────────────────────────────────────────────────────────────


def test_import_files_creates_uploads_starts_with_mappings_and_links_then_waits(
    http, tmp_path
):
    customers = tmp_path / "customers.csv"
    customers.write_bytes(data_of(3))
    files = [direct_file("f1", 3), direct_file("f2", 4)]
    polls = iter(["running", "completed"])

    def answer(call, calls):
        path = call["url"][len(API) :]
        if call["method"] == "POST" and path == "/imports":
            return json_answer({**run(), "files": files})
        if path.endswith("/content") or path.endswith("/complete"):
            return json_answer(file_dto("f", "f.csv", 1))
        if path.endswith("/start"):
            return json_answer(run(status="queued"))
        if call["method"] == "GET":
            return json_answer(run(status=next(polls)))
        return http_error(call["url"], 404)

    calls = http(answer)
    phases = []

    result = db().imports.import_files(
        [
            {"data": customers, "label": "Customer"},
            {"data": data_of(4), "name": "orders.csv"},
        ],
        name="CRM export",
        mappings={"customers.csv": {"keyColumn": "id"}},
        links=[
            {
                "source": "orders.csv",
                "sourceColumn": "customer_id",
                "target": 0,
                "targetColumn": "id",
                "type": "PLACED_BY",
            }
        ],
        wait=True,
        wait_interval=0.001,
        on_progress=lambda p: phases.append(p["phase"]),
    )

    assert result.data["status"] == "completed"
    assert calls.calls[0]["body"] == {
        "name": "CRM export",
        "files": [
            {"name": "customers.csv", "size": 3, "label": "Customer"},
            {"name": "orders.csv", "size": 4},
        ],
    }
    contents = [c["body"] for c in calls.calls if c["url"].endswith("/content")]
    assert contents == [data_of(3), data_of(4)]
    start = next(c for c in calls.calls if c["url"].endswith("/start"))
    assert start["body"] == {
        "files": [{"id": "f1", "mapping": {"keyColumn": "id"}}, {"id": "f2"}],
        "links": [
            {
                "sourceFileId": "f2",
                "sourceColumn": "customer_id",
                "targetFileId": "f1",
                "targetColumn": "id",
                "type": "PLACED_BY",
            }
        ],
    }
    assert "upload" in phases
    assert phases[-1] == "run"


def test_import_files_takes_paths_and_returns_once_started(http, tmp_path):
    path = tmp_path / "rows.ndjson"
    path.write_bytes(b'{"a":1}\n')

    def answer(call, calls):
        path_ = call["url"][len(API) :]
        if path_ == "/imports":
            return json_answer({**run(), "files": [direct_file("f1", 8)]})
        if path_.endswith("/start"):
            return json_answer(run(status="queued"))
        return json_answer(file_dto("f1", "rows.ndjson", 8))

    calls = http(answer)

    result = db().imports.import_files([path], mappings={0: {"keyColumn": "a"}})

    assert result.data["status"] == "queued"
    assert calls.calls[0]["body"] == {"files": [{"name": "rows.ndjson", "size": 8}]}
    assert calls.calls[-1]["body"] == {
        "files": [{"id": "f1", "mapping": {"keyColumn": "a"}}]
    }
    assert not any(c["method"] == "GET" for c in calls.calls)


def test_import_files_needs_a_size_for_a_stream_and_a_name_for_bytes(http):
    calls = http(lambda call, calls: json_answer({}))

    class Pipe(io.RawIOBase):
        def readable(self):
            return True

        def seekable(self):
            return False

    with pytest.raises(ValueError, match="pass its size"):
        db().imports.import_files([{"data": Pipe(), "name": "a.csv"}])
    with pytest.raises(ValueError, match="needs a name"):
        db().imports.import_files([{"data": b"x"}])
    assert calls.calls == []
