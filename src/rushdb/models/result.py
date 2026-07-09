import io
from typing import TYPE_CHECKING, Any, Dict, Generic, Iterator, List, Optional, TypeVar

from .record import Record
from .search_query import SearchQuery

if TYPE_CHECKING:
    from ..client import RushDB

# Generic type for result items
T = TypeVar("T")


class SearchResult(Generic[T]):
    """
    Container for search results following Python SDK best practices.

    Provides both list-like access and iteration support, along with metadata
    about the search operation (total count, pagination info, etc.).

    This class follows common Python SDK patterns used by libraries like:
    - boto3 (AWS SDK)
    - google-cloud libraries
    - requests libraries
    """

    def __init__(
        self,
        data: List[T],
        total: Optional[int] = None,
        search_query: Optional[SearchQuery] = None,
        client: Optional["RushDB"] = None,
        warnings: Optional[List[str]] = None,
    ):
        """
        Initialize search result.

        Args:
            data: List of result items
            total: Total number of matching records (may be larger than len(data))
            search_query: The search query used to generate this result
            client: Optional RushDB client instance (required for delete_all, next, set_properties)
            warnings: Optional warnings returned by AI-assisted query generation
        """
        self._data = data
        self._total = total or len(data)
        self._search_query = search_query or {}
        self._client = client
        self._warnings = warnings or []

    @property
    def data(self) -> List[T]:
        """Get the list of result items."""
        return self._data

    @property
    def total(self) -> int:
        """Get the total number of matching records."""
        return self._total

    @property
    def search_query(self) -> SearchQuery:
        """Get the search query used to generate this result."""
        return self._search_query

    @property
    def warnings(self) -> List[str]:
        """Get warnings returned by AI-assisted query generation."""
        return self._warnings

    @property
    def has_more(self) -> bool:
        """Check if there are more records available beyond this result set."""
        return self._total > (self.skip + len(self._data))

    @property
    def skip(self) -> int:
        """Get the number of records that were skipped."""
        return self._search_query.get("skip") or 0

    @property
    def limit(self) -> Optional[int]:
        """Get the limit that was applied to the search."""
        return self._search_query.get("limit")

    def __len__(self) -> int:
        """Get the number of records in this result set."""
        return len(self._data)

    def __iter__(self) -> Iterator[T]:
        """Iterate over the result items."""
        return iter(self._data)

    def __getitem__(self, index) -> T:
        """Get an item by index or slice."""
        return self._data[index]

    def __bool__(self) -> bool:
        """Check if the result set contains any items."""
        return len(self._data) > 0

    def __repr__(self) -> str:
        """String representation of the search result."""
        return f"SearchResult(count={len(self._data)}, total={self._total})"

    def to_dict(self) -> dict:
        """
        Return the result in a standardized dictionary format.

        Returns:
            Dict with keys: total, data, search_query
        """
        return {
            "total": self.total,
            "data": self.data,
            "search_query": self.search_query,
            "warnings": self.warnings,
        }

    def get_page_info(self) -> dict:
        """Get pagination information."""
        return {
            "total": self.total,
            "loaded": len(self.data),
            "has_more": self.has_more,
            "skip": self.skip,
            "limit": self.limit,
        }

    def _get_client(self) -> "RushDB":
        """Resolve the client from stored reference or first record."""
        if self._client is not None:
            return self._client
        if self._data and hasattr(self._data[0], "_client"):
            return self._data[0]._client  # type: ignore[attr-defined]
        raise RuntimeError(
            "SearchResult: no client available. "
            "This method requires a client-aware SearchResult."
        )

    def delete_all(self, transaction=None) -> Dict[str, Any]:
        """Delete all records in this result set.

        Args:
            transaction: Optional transaction or transaction ID

        Returns:
            Server response dict with operation status
        """
        ids = [r.id for r in self._data]  # type: ignore[attr-defined]
        if not ids:
            return {"success": True}
        return self._get_client().records.delete_by_id(ids, transaction)

    def next(self, preserve_data: bool = False) -> "SearchResult":
        """Fetch the next page of results.

        Args:
            preserve_data: If True, appends new records to this instance's data
                           and returns self. Otherwise returns a new SearchResult.

        Returns:
            SearchResult with the next page (or self when preserve_data=True)

        Raises:
            RuntimeError: If no search_query was provided at construction
        """
        if not self._search_query:
            raise RuntimeError(
                "SearchResult: cannot paginate — no search_query was provided."
            )
        current_skip = self._search_query.get("skip") or 0
        current_limit = self._search_query.get("limit") or 100
        next_query: SearchQuery = {
            **self._search_query,
            "skip": current_skip + current_limit,
        }
        result = self._get_client().records.find(next_query)
        if preserve_data:
            self._data = self._data + result._data  # type: ignore[operator]
            self._total = result._total
            self._search_query = next_query
            return self
        return result

    def export_csv(self) -> str:
        """Serialize this result set to a CSV string.

        System fields (__id, __label, __proptypes) are excluded from the output,
        matching the behaviour of the JavaScript SDK's exportCsv().

        Returns:
            CSV string with a header row followed by one row per record.
            Returns an empty string if the result set is empty.
        """
        if not self._data:
            return ""

        _EXCLUDE = {"__id", "__label", "__proptypes"}
        first = self._data[0]
        headers = [
            k
            for k in first.data.keys()  # type: ignore[attr-defined]
            if k not in _EXCLUDE
        ]

        def _escape(value: Any) -> str:
            s = "" if value is None else str(value)
            if any(c in s for c in (",", '"', "\n")):
                return '"' + s.replace('"', '""') + '"'
            return s

        output = io.StringIO()
        output.write(",".join(headers) + "\n")
        for record in self._data:
            row = [_escape(record.data.get(h)) for h in headers]  # type: ignore[attr-defined]
            output.write(",".join(row) + "\n")
        return output.getvalue()

    def set_properties(self, patch: Dict[str, Any], transaction=None) -> None:
        """Update properties across all records in this result set.

        Records are updated in batches of 100, mirroring the JavaScript SDK's
        setProperties() method.

        Args:
            patch: Fields to update and their new values
            transaction: Optional transaction or transaction ID
        """
        BATCH_SIZE = 100
        for i in range(0, len(self._data), BATCH_SIZE):
            batch = self._data[i : i + BATCH_SIZE]
            for record in batch:
                record.update(patch, transaction)  # type: ignore[attr-defined]

    def to_dataframe(self, exclude_internal: bool = True):
        """Convert this result set to a pandas DataFrame.

        Args:
            exclude_internal: If True, columns starting with '__' are excluded

        Returns:
            pandas.DataFrame with one row per record

        Raises:
            ImportError: If pandas is not installed
        """
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). Install it with: pip install pandas"
            )
        rows = [r.get_data(exclude_internal=exclude_internal) for r in self._data]  # type: ignore[attr-defined]
        return pd.DataFrame(rows)


class RecordSearchResult(SearchResult[Record]):
    """Search result specialized for ``Record`` items.

    A real subclass (not a ``SearchResult[Record]`` alias) so that
    ``isinstance(result, RecordSearchResult)`` works — isinstance checks against
    subscripted generics raise ``TypeError`` at runtime.
    """
