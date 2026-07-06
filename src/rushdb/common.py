from typing import Dict, Optional


class RushDBError(Exception):
    """Custom exception for RushDB client errors.

    Attributes:
        details: Parsed error response body from the server, if any.
        status: HTTP status code for server errors (e.g. 403 for a write attempt
            with a read-only API key, 408 for a server-side transaction timeout).
            ``None`` for client-side errors such as connection failures.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict] = None,
        status: Optional[int] = None,
    ):
        super().__init__(message)
        self.details = details or {}
        self.status = status


class NonUniqueResultError(Exception):
    """Raised by ``records.find_uniq()`` when more than one record matches the query."""

    def __init__(self, count: int):
        super().__init__(
            f"Expected at most one record but found {count}. "
            "Refine your search query or use records.find() instead."
        )
        self.count = count
