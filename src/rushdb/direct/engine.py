"""Direct engine transport for the RushDB Python SDK.

Executes protocol operations against a standalone ``rushdb``
(``POST /protocol/v1/execute``) over HTTP. This is the SDK's "direct mode":
no RushDB Cloud. The tenant scope (multitenant engines) is the
``X-RushDB-Tenant`` header and auth is the engine token. The REST calls of the
SDK are answered from these operations by :mod:`rushdb.direct.router`.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from ..common import RushDBError


class DirectEngine:
    """Client for a standalone ``rushdb`` protocol endpoint.

    Args:
        engine_url (str): Base URL of the standalone engine, e.g.
            ``"http://127.0.0.1:3000"``.
        token (str): The engine boot token (``--token`` / ``RUSHDB_TOKEN``).
        scope (Optional[str], optional): Tenant scope. When provided it is sent
            both in the envelope context and the ``X-RushDB-Tenant`` header
            (multitenant engines).
    """

    def __init__(
        self,
        engine_url: str,
        token: str,
        scope: Optional[str] = None,
    ):
        self.base_url = engine_url.rstrip("/")
        self.token = token
        self.scope = scope

    # ── transport ───────────────────────────────────────────────────────────

    def execute(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Run one protocol operation and return its ``response``.

        Raises:
            RushDBError: When the engine refuses the operation; ``status`` is the
                engine's HTTP status.
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
        req = urllib.request.Request(
            f"{self.base_url}/protocol/v1/execute",
            data=json.dumps(envelope).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
                body = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                message = parsed.get("error", {}).get("message", raw)
            except json.JSONDecodeError:
                message = raw or f"engine request failed ({exc.code})"
            raise RushDBError(message, status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise RushDBError(f"Connection error: {exc}") from exc
        if body.get("error"):
            raise RushDBError(body["error"].get("message", "engine request failed"))
        return body.get("response", {})
