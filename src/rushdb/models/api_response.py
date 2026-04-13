from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class ApiResponse(Generic[T]):
    """Wraps a server response with typed data, success flag, and optional total count.

    Mirrors the TypeScript ``ApiResponse<T>`` type used throughout the JS SDK::

        type ApiResponse<T> = { data: T; success: boolean; total?: number }

    All ``db.ai.*`` methods return ``ApiResponse`` so callers can access
    ``response.data`` directly without unpacking a raw dict.

    Attributes:
        data: The typed payload returned by the server.
        success: Whether the request succeeded (always ``True`` for non-error paths).
        total: Optional total count (e.g. for list endpoints).

    Example:
        >>> response = db.ai.get_ontology_markdown()
        >>> schema_md = response.data          # str
        >>> response = db.ai.indexes.find()
        >>> indexes = response.data            # list[dict]
    """

    def __init__(self, data: T, success: bool = True, total: Optional[int] = None):
        self.data = data
        self.success = success
        self.total = total

    def __repr__(self) -> str:
        return f"ApiResponse(success={self.success}, total={self.total}, data={self.data!r})"
