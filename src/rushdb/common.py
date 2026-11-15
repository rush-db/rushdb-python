import json
import re
from typing import Any, Dict, Optional, Tuple

# A bare ``{"error": "unauthorized"}`` names a code; ``"route not found"`` does not.
_CODE_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


def parse_error_body(raw: Any) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
    """Read an HTTP error body into ``(message, details, code)``.

    Accepts every shape the engine and the API answer with:

    - the protocol envelope ``{"protocolVersion": 1, "error": {"code", "message",
      "retryable"}}``;
    - a bare string ``{"error": "unauthorized"}`` (engine auth failures);
    - flat ``{"code", "message", "retryable"}`` (engine boot) and the API's
      ``{"statusCode", "message", "error"}``, where ``message`` may be a list;
    - plain text, HTML from a proxy, or an empty body.

    ``message`` is ``None`` when the body has nothing worth showing; callers
    fall back to a message built from the HTTP status. ``details`` is the
    parsed JSON object (``{}`` otherwise).
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = (raw or "").strip()
    if not text:
        return None, {}, None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Plain text is the message; an HTML error page from a proxy is not.
        if text.startswith("<"):
            return None, {}, None
        return text[:500], {}, None
    if not isinstance(parsed, dict):
        return None, {}, None

    message: Any = parsed.get("message")
    code: Any = parsed.get("code")
    error = parsed.get("error")
    if isinstance(error, dict):
        message = error.get("message") or message
        code = error.get("code") or code
    elif isinstance(error, str) and error and not message:
        message = error
        if not code and _CODE_PATTERN.fullmatch(error):
            code = error
    if isinstance(message, list):
        message = "; ".join(str(item) for item in message)
    return (
        str(message) if message else None,
        parsed,
        code if isinstance(code, str) and code else None,
    )


class RushDBError(Exception):
    """Custom exception for RushDB client errors.

    Attributes:
        details: Parsed error response body from the server, if any.
        status: HTTP status code for server errors (e.g. 403 for a write attempt
            with a read-only API key, 408 for a server-side transaction timeout).
            ``None`` for client-side errors such as connection failures.
        code: Optional stable error code (e.g. ``IMPORT_LINK_SPEC_INVALID``) from
            client-side validation or the server response body.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict] = None,
        status: Optional[int] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.details = details or {}
        self.status = status
        self.code = code or (details or {}).get("code")


class NonUniqueResultError(Exception):
    """Raised by ``records.find_uniq()`` when more than one record matches the query."""

    def __init__(self, count: int):
        super().__init__(
            f"Expected at most one record but found {count}. "
            "Refine your search query or use records.find() instead."
        )
        self.count = count


class CloudOnlyError(RushDBError):
    """A RushDB Cloud feature was called on a client in direct mode (a
    standalone engine). Raised before any request is sent.

    Attributes:
        method: The SDK method, e.g. ``ai.search``.
        reason: What the method needs from RushDB Cloud.
    """

    def __init__(self, method: str, reason: str):
        super().__init__(
            f"{method} requires RushDB Cloud: {reason}. It is not available in direct mode.",
            code="CLOUD_ONLY",
        )
        self.method = method
        self.reason = reason


class DirectModeError(RushDBError):
    """A call a standalone engine supports, made in a form direct mode cannot
    carry out (for example a write that would have to be staged into a
    transaction the engine protocol cannot address). Raised before any
    request is sent, so nothing runs half-way."""

    def __init__(self, message: str):
        super().__init__(message, code="DIRECT_MODE_UNSUPPORTED")
