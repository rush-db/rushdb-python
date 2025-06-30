from typing import Generic, Iterator, List, Optional, TypeVar

from .record import Record
from .search_query import SearchQuery

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
    ):
        """
        Initialize search result.

        Args:
            data: List of result items
            total: Total number of matching records (may be larger than len(data))
            search_query: The search query used to generate this result
        """
        self._data = data
        self._total = total or len(data)
        self._search_query = search_query or {}

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


# Type alias for record search results
RecordSearchResult = SearchResult[Record]
