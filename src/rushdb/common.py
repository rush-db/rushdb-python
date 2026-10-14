from typing import Dict, Optional


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
