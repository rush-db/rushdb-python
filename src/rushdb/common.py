from typing import Dict, Optional


class RushDBError(Exception):
    """Custom exception for RushDB client errors."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}
