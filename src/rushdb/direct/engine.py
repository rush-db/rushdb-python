"""Direct engine transport for the RushDB Python SDK.

Executes protocol operations against a standalone ``rushdb``
(``POST /protocol/v1/execute``) over HTTP. This is the SDK's "direct mode":
no RushDB Cloud. The tenant scope (multitenant engines) is the
``X-RushDB-Tenant`` header and auth is the engine token. The REST calls of the
SDK are answered from these operations by :mod:`rushdb.direct.router`.

Connections are kept alive: each thread reuses one ``http.client`` connection
to the engine, so a call does not pay for a new TCP (and TLS) handshake.
"""

import http.client
import json
import os
import select
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from ..common import RushDBError, parse_error_body

DEFAULT_TIMEOUT = 120.0
"""Seconds to wait for the engine to connect or answer."""

# The engine may close an idle keep-alive connection at any time. A request sent
# on such a connection fails with one of these before any answer arrives.
_STALE_CONNECTION_ERRORS = (
    http.client.RemoteDisconnected,
    http.client.BadStatusLine,
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
)


def _is_read(operation: Dict[str, Any]) -> bool:
    """Whether ``operation`` only reads, so sending it twice is harmless.

    A Cypher or SQL statement can write, so it does not count as a read.
    """
    kind = operation.get("kind")
    if kind == "describe":
        return True
    if kind == "query":
        query = operation.get("query")
        return isinstance(query, dict) and query.get("kind") != "statement"
    return False


def _is_dropped(conn: http.client.HTTPConnection) -> bool:
    """Whether the engine closed ``conn`` while it sat idle.

    An idle keep-alive socket has nothing to read; once it turns readable the
    engine has closed it (or sent something unexpected), so it is not reused.
    """
    sock = conn.sock
    if sock is None:
        return True
    try:
        if hasattr(select, "poll"):
            poller = select.poll()
            poller.register(sock, select.POLLIN)
            return bool(poller.poll(0))
        return bool(select.select([sock], [], [], 0)[0])
    except (OSError, ValueError):
        return True


class DirectEngine:
    """Client for a standalone ``rushdb`` protocol endpoint.

    Each thread keeps one connection to the engine and reuses it across calls.
    A connection the engine closed while idle is replaced before the next
    request. If a reused connection fails before the engine answers, a read is
    sent once more on a new connection; a write is not, and the error is
    raised. When a proxy applies to ``engine_url`` (``HTTP_PROXY`` /
    ``HTTPS_PROXY``), every call goes through ``urllib`` and the proxy instead.

    Args:
        engine_url (str): Base URL of the standalone engine, e.g.
            ``"http://127.0.0.1:3000"``.
        token (str): The engine boot token (``--token`` / ``RUSHDB_TOKEN``).
        scope (Optional[str], optional): Tenant scope. When provided it is sent
            both in the envelope context and the ``X-RushDB-Tenant`` header
            (multitenant engines).
        timeout (float, optional): Seconds to wait for the engine to connect or
            answer. Default 120.
    """

    def __init__(
        self,
        engine_url: str,
        token: str,
        scope: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = engine_url.rstrip("/")
        self.token = token
        self.scope = scope
        self.timeout = timeout
        url = urllib.parse.urlsplit(self.base_url)
        self._https = url.scheme == "https"
        self._host = url.hostname or ""
        self._port = url.port
        self._path = f"{url.path}/protocol/v1/execute"
        self._proxied = bool(
            urllib.request.getproxies().get(url.scheme)
        ) and not urllib.request.proxy_bypass(url.netloc)
        # One connection per thread, with the process it was opened in.
        self._connections: Dict[
            threading.Thread, Tuple[http.client.HTTPConnection, int]
        ] = {}
        self._lock = threading.Lock()

    # ── transport ───────────────────────────────────────────────────────────

    def execute(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Run one protocol operation and return its ``response``.

        Raises:
            RushDBError: When the engine refuses the operation (``status`` is the
                engine's HTTP status) or cannot be reached.
            TimeoutError: When the engine does not answer within ``timeout``.
        """
        envelope: Dict[str, Any] = {"protocolVersion": 1, "operation": operation}
        if self.scope:
            envelope["context"] = {"scope": self.scope}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if self.scope:
            headers["X-RushDB-Tenant"] = self.scope
        data = json.dumps(envelope).encode("utf-8")
        status, raw = self._send(data, headers, _is_read(operation))
        if status >= 400:
            message, details, code = parse_error_body(raw)
            raise RushDBError(
                message or f"engine request failed (HTTP {status})",
                details,
                status=status,
                code=code,
            )
        body = json.loads(raw.decode("utf-8") or "{}")
        if body.get("error"):
            message, details, code = parse_error_body(json.dumps(body))
            raise RushDBError(message or "engine request failed", details, code=code)
        return body.get("response", {})

    def close(self) -> None:
        """Close the connections this client keeps open, in every thread.

        The next call opens a new one.
        """
        with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for conn, pid in connections:
            if pid == os.getpid():
                conn.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 - nothing to report to at teardown
            pass

    def _send(
        self, data: bytes, headers: Dict[str, str], is_read: bool
    ) -> Tuple[int, bytes]:
        """POST ``data`` to the engine; return the HTTP status and the raw body."""
        if self._proxied:
            return self._send_via_urllib(data, headers)
        conn, reused = self._connection()
        try:
            return self._exchange(conn, data, headers)
        except _STALE_CONNECTION_ERRORS as exc:
            conn.close()
            if not (reused and is_read):
                raise RushDBError(f"Connection error: {exc}") from exc
        conn, _ = self._connection()
        try:
            return self._exchange(conn, data, headers)
        except _STALE_CONNECTION_ERRORS as exc:
            conn.close()
            raise RushDBError(f"Connection error: {exc}") from exc

    def _exchange(
        self, conn: http.client.HTTPConnection, data: bytes, headers: Dict[str, str]
    ) -> Tuple[int, bytes]:
        """One request and its answer on ``conn``. Lost-connection errors are
        left to the caller; on any other failure ``conn`` is closed."""
        try:
            conn.request("POST", self._path, body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        except _STALE_CONNECTION_ERRORS:
            raise
        except TimeoutError:
            conn.close()
            raise
        except (OSError, http.client.HTTPException) as exc:
            conn.close()
            raise RushDBError(f"Connection error: {exc}") from exc

    def _connection(self) -> Tuple[http.client.HTTPConnection, bool]:
        """This thread's open connection, and whether it served a call before."""
        thread = threading.current_thread()
        pid = os.getpid()
        entry = self._connections.get(thread)
        # After a fork the inherited socket belongs to the parent: leave it be.
        if entry is not None and entry[1] == pid:
            if not _is_dropped(entry[0]):
                return entry[0], True
            entry[0].close()
        conn: http.client.HTTPConnection
        if self._https:
            conn = http.client.HTTPSConnection(
                self._host, self._port, timeout=self.timeout
            )
        else:
            conn = http.client.HTTPConnection(
                self._host, self._port, timeout=self.timeout
            )
        try:
            conn.connect()
        except TimeoutError:
            conn.close()
            raise
        except OSError as exc:
            conn.close()
            raise RushDBError(f"Connection error: {exc}") from exc
        with self._lock:
            # Close what threads that have ended left open.
            for other, (other_conn, other_pid) in list(self._connections.items()):
                if not other.is_alive():
                    del self._connections[other]
                    if other_pid == pid:
                        other_conn.close()
            self._connections[thread] = (conn, pid)
        return conn, False

    def _send_via_urllib(
        self, data: bytes, headers: Dict[str, str]
    ) -> Tuple[int, bytes]:
        """One request through ``urllib``, which applies the proxy settings."""
        req = urllib.request.Request(
            f"{self.base_url}/protocol/v1/execute",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout
            ) as resp:  # noqa: S310
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read()
            except OSError:
                raw = b""
            return exc.code, raw
        except urllib.error.URLError as exc:
            raise RushDBError(f"Connection error: {exc}") from exc
