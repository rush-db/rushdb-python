from typing import Dict, Optional


class RushDBError(Exception):
    """Custom exception for RushDB client errors."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}


class NonUniqueResultError(Exception):
    """Raised by ``records.find_uniq()`` when more than one record matches the query."""

    def __init__(self, count: int):
        super().__init__(
            f"Expected at most one record but found {count}. "
            "Refine your search query or use records.find() instead."
        )
        self.count = count
