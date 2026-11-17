"""The direct engine transport keeps its connection alive: one connection per
thread serves every call, a connection the engine closed is replaced, a read
that lost its connection is sent once more and a write is not."""

import json
import shutil
import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import pytest

from rushdb import RushDBError
from rushdb.direct import DirectEngine
from rushdb.direct.engine import _is_read

READ = {"kind": "describe", "describe": {"kind": "buildInfo"}}
WRITE = {"kind": "mutate", "mutation": {"kind": "createRecord", "label": "Book"}}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with self.server.lock:
            self.server.connections += 1

    def log_message(self, *args):
        pass

    def do_POST(self):
        server = self.server
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with server.lock:
            server.requests.append((self.path, dict(self.headers), body))
            mode = server.modes.pop(0) if server.modes else "ok"
        if mode == "drop":
            # Read the request, then close without answering.
            self.close_connection = True
            return
        if mode == "slow":
            time.sleep(0.5)
        status, answer = (
            (401, {"error": "unauthorized"})
            if mode == "refuse"
            else (200, {"response": {"ok": True}})
        )
        payload = json.dumps(answer).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if mode == "close":
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        if mode == "idle-close":
            # Close after answering, without announcing it.
            self.close_connection = True


def _serving(context=None):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.daemon_threads = True
    httpd.lock = threading.Lock()
    httpd.connections = 0
    httpd.requests = []
    httpd.modes = []
    httpd.engines = []
    if context is not None:
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    threading.Thread(target=httpd.serve_forever, args=(0.02,), daemon=True).start()
    return httpd


def _stop(httpd):
    for engine in httpd.engines:
        engine.close()
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def server():
    httpd = _serving()
    yield httpd
    _stop(httpd)


def engine_for(server, scheme="http", **extra):
    host, port = server.server_address
    engine = DirectEngine(f"{scheme}://{host}:{port}", "TOKEN", **extra)
    server.engines.append(engine)
    return engine


def test_one_connection_serves_every_call(server):
    engine = engine_for(server, scope="tenant-1")
    for _ in range(20):
        assert engine.execute(READ) == {"ok": True}
    engine.execute(WRITE)
    assert server.connections == 1
    assert len(server.requests) == 21
    path, headers, body = server.requests[0]
    assert path == "/protocol/v1/execute"
    assert headers["Authorization"] == "Bearer TOKEN"
    assert headers["X-RushDB-Tenant"] == "tenant-1"
    assert body == {
        "protocolVersion": 1,
        "operation": READ,
        "context": {"scope": "tenant-1"},
    }


def test_url_path_prefix_is_kept(server):
    host, port = server.server_address
    engine = DirectEngine(f"http://{host}:{port}/engine/", "TOKEN")
    server.engines.append(engine)
    engine.execute(READ)
    assert server.requests[0][0] == "/engine/protocol/v1/execute"


def test_a_refusal_keeps_the_connection(server):
    engine = engine_for(server)
    server.modes = ["refuse"]
    with pytest.raises(RushDBError) as failure:
        engine.execute(READ)
    assert failure.value.status == 401
    assert failure.value.code == "unauthorized"
    engine.execute(READ)
    assert server.connections == 1


@pytest.mark.parametrize("operation", [READ, WRITE], ids=["read", "write"])
def test_connection_closed_while_idle_is_replaced(server, operation):
    engine = engine_for(server)
    server.modes = ["idle-close"]
    engine.execute(READ)
    time.sleep(0.05)  # let the close reach the client
    assert engine.execute(operation) == {"ok": True}
    assert server.connections == 2
    assert len(server.requests) == 2


def test_announced_close_opens_a_new_connection(server):
    engine = engine_for(server)
    server.modes = ["close"]
    engine.execute(WRITE)
    engine.execute(WRITE)
    assert server.connections == 2


def test_read_that_lost_its_connection_is_sent_once_more(server):
    engine = engine_for(server)
    engine.execute(READ)
    server.modes = ["drop"]
    assert engine.execute(READ) == {"ok": True}
    assert len(server.requests) == 3
    assert server.connections == 2


def test_write_that_lost_its_connection_is_not_sent_again(server):
    engine = engine_for(server)
    engine.execute(READ)
    server.modes = ["drop"]
    with pytest.raises(RushDBError, match="Connection error"):
        engine.execute(WRITE)
    assert len(server.requests) == 2
    # The next call works on a new connection.
    engine.execute(WRITE)
    assert server.connections == 2


def test_read_is_sent_at_most_twice(server):
    engine = engine_for(server)
    engine.execute(READ)
    server.modes = ["drop", "drop"]
    with pytest.raises(RushDBError, match="Connection error"):
        engine.execute(READ)
    assert len(server.requests) == 3


def test_lost_first_connection_is_not_retried(server):
    engine = engine_for(server)
    server.modes = ["drop"]
    with pytest.raises(RushDBError, match="Connection error"):
        engine.execute(READ)
    assert len(server.requests) == 1


def test_timeout_is_honoured(server):
    engine = engine_for(server, timeout=0.2)
    server.modes = ["slow"]
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        engine.execute(READ)
    assert time.monotonic() - started < 0.45
    assert engine.execute(READ) == {"ok": True}


def test_unreachable_engine_raises_rushdb_error():
    engine = DirectEngine("http://127.0.0.1:1", "TOKEN")
    with pytest.raises(RushDBError, match="Connection error"):
        engine.execute(READ)


def test_one_connection_per_thread(server):
    engine = engine_for(server)
    errors = []

    def calls():
        try:
            for _ in range(10):
                engine.execute(READ)
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=calls) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(server.requests) == 40
    assert server.connections == 4
    # The next new connection closes those of the threads that have ended.
    engine.execute(READ)
    assert list(engine._connections) == [threading.current_thread()]


def test_close_drops_the_connection(server):
    engine = engine_for(server)
    engine.execute(READ)
    engine.close()
    engine.execute(READ)
    assert server.connections == 2


def test_proxy_settings_send_through_urllib(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    engine = DirectEngine("http://engine.example:3000", "TOKEN")

    class Response:
        status = 200

        def read(self):
            return b'{"response": {"ok": true}}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    with mock.patch("urllib.request.urlopen", return_value=Response()) as urlopen:
        assert engine.execute(READ) == {"ok": True}
    request = urlopen.call_args.args[0]
    assert request.full_url == "http://engine.example:3000/protocol/v1/execute"


def test_reads_are_told_apart_from_writes():
    assert _is_read(READ)
    assert _is_read({"kind": "query", "query": {"kind": "records", "query": {}}})
    assert not _is_read(
        {"kind": "query", "query": {"kind": "statement", "language": "cypher"}}
    )
    assert not _is_read(WRITE)
    assert not _is_read({"kind": "transaction", "transaction": {"kind": "begin"}})
    assert not _is_read({"kind": "ingest", "ingest": {}})
    assert not _is_read({"kind": "index", "index": {"kind": "drop"}})


@pytest.fixture
def tls_server(tmp_path, monkeypatch):
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    httpd = _serving(context)
    yield httpd, cert
    _stop(httpd)


def test_tls_connection_is_verified_and_reused(tls_server, monkeypatch):
    httpd, cert = tls_server
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    engine = engine_for(httpd, scheme="https")
    for _ in range(5):
        assert engine.execute(READ) == {"ok": True}
    assert httpd.connections == 1


def test_tls_certificate_is_not_trusted_blindly(tls_server, monkeypatch):
    httpd, _ = tls_server
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    with pytest.raises(RushDBError, match="CERTIFICATE_VERIFY_FAILED"):
        engine_for(httpd, scheme="https").execute(READ)
