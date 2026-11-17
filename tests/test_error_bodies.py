"""Every error body the engine and the API answer with surfaces as a
RushDBError carrying the message, the code where the body names one, and the
HTTP status."""

import io
import json
import urllib.error
from unittest import mock

import pytest

from rushdb import RushDB, RushDBError
from rushdb.common import parse_error_body
from rushdb.direct import DirectEngine

ENVELOPE = {
    "protocolVersion": 1,
    "error": {
        "code": "unauthorized",
        "message": "capability lacks the write permission",
        "retryable": False,
    },
}

# (body, expected message or None for the status fallback, expected code)
SHAPES = {
    "envelope": (
        json.dumps(ENVELOPE),
        "capability lacks the write permission",
        "unauthorized",
    ),
    "bare string error": ('{"error":"unauthorized"}', "unauthorized", "unauthorized"),
    "bare string that is no code": (
        '{"error":"route not found"}',
        "route not found",
        None,
    ),
    "flat boot error": (
        '{"code":"unavailable","message":"node is starting (replay)","retryable":true}',
        "node is starting (replay)",
        "unavailable",
    ),
    "api error": (
        '{"statusCode":401,"message":"Invalid token","error":"Unauthorized"}',
        "Invalid token",
        None,
    ),
    "api validation list": (
        '{"statusCode":400,"message":["a is required","b must be a string"]}',
        "a is required; b must be a string",
        None,
    ),
    "plain text": ("Unauthorized\n", "Unauthorized", None),
    "html from a proxy": ("<html><body>502 Bad Gateway</body></html>", None, None),
    "json that is no object": ('["unauthorized"]', None, None),
    "empty": ("", None, None),
}


@pytest.mark.parametrize("body,message,code", SHAPES.values(), ids=SHAPES.keys())
def test_parse_error_body(body, message, code):
    parsed_message, details, parsed_code = parse_error_body(body.encode("utf-8"))
    assert parsed_message == message
    assert parsed_code == code
    assert isinstance(details, dict)


def refusing(status, body):
    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, status, "error", {}, io.BytesIO(body.encode("utf-8"))
        )

    return refuse


@pytest.mark.parametrize("body,message,code", SHAPES.values(), ids=SHAPES.keys())
def test_direct_mode_raises_rushdb_error(body, message, code):
    db = RushDB("BAD", direct=True, engine_url="http://engine:3000")
    with mock.patch.object(
        DirectEngine, "_send", return_value=(401, body.encode("utf-8"))
    ):
        with pytest.raises(RushDBError) as failure:
            db.records.create("Book", {"title": "Dune"})
    assert str(failure.value) == (message or "engine request failed (HTTP 401)")
    assert failure.value.code == code
    assert failure.value.status == 401


@pytest.mark.parametrize("body,message,code", SHAPES.values(), ids=SHAPES.keys())
def test_cloud_client_raises_rushdb_error(body, message, code):
    db = RushDB("BAD", base_url="http://cloud:3000")
    with mock.patch("urllib.request.urlopen", side_effect=refusing(401, body)):
        with pytest.raises(RushDBError) as failure:
            db.records.find({"labels": ["Book"]})
    assert str(failure.value) == (message or "HTTP 401")
    assert failure.value.code == code
    assert failure.value.status == 401


@pytest.mark.parametrize("body,message,code", SHAPES.values(), ids=SHAPES.keys())
def test_raw_upload_raises_rushdb_error(body, message, code):
    db = RushDB("BAD", base_url="http://cloud:3000")
    with mock.patch("urllib.request.urlopen", side_effect=refusing(403, body)):
        with pytest.raises(RushDBError) as failure:
            db._send_raw("PUT", "http://storage/part", b"x", what="upload failed")
    assert str(failure.value) == (message or "upload failed (HTTP 403)")
    assert failure.value.code == code
    assert failure.value.status == 403


@pytest.mark.parametrize(
    "error", [ENVELOPE["error"], "unauthorized"], ids=["object", "string"]
)
def test_direct_mode_error_in_a_200_body(error):
    answer = json.dumps({"protocolVersion": 1, "error": error}).encode()
    db = RushDB("BAD", direct=True, engine_url="http://engine:3000")
    with mock.patch.object(DirectEngine, "_send", return_value=(200, answer)):
        with pytest.raises(RushDBError) as failure:
            db.records.create("Book", {"title": "Dune"})
    assert failure.value.code == "unauthorized"
