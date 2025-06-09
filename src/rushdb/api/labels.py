import typing
from typing import List, Optional

from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class LabelsAPI(BaseAPI):
    """API client for managing labels in RushDB.

    The LabelsAPI provides functionality for discovering and working with record labels
    in the database. Labels are used to categorize and type records, similar to table
    names in relational databases or document types in NoSQL databases.

    This class handles:
    - Label discovery and listing
    - Label searching and filtering
    - Transaction support for operations

    Labels help organize and categorize records, making it easier to query and
    understand the structure of data within the database.

    Attributes:
        client: The underlying RushDB client instance for making HTTP requests.

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> labels_api = client.labels
        >>>
        >>> # Get all labels in the database
        >>> all_labels = labels_api.find()
        >>> print("Available labels:", all_labels)
        >>>
        >>> # Search for specific labels
        >>> from rushdb.models.search_query import SearchQuery
        >>> query = SearchQuery(where={"name":{"$contains": "alice"}})
        >>> user_labels = labels_api.find(query)
    """

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[str]:
        """Search for and retrieve labels matching the specified criteria.

        Discovers labels (record types) that exist in the database and can optionally
        filter them based on search criteria. Labels represent the different types
        or categories of records stored in the database.

        Args:
            search_query (Optional[SearchQuery], optional): The search criteria to filter labels.
                If None, returns all labels in the database. Can include filters for
                label names, patterns, or other metadata. Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            List[str]: List of label names (strings) matching the search criteria.
                Each string represents a unique label/type used in the database.

        Raises:
            RequestError: If the server request fails.

        Example:
            >>> from rushdb.models.search_query import SearchQuery
            >>> labels_api = LabelsAPI(client)
            >>>
            >>> # Get all labels
            >>> all_labels = labels_api.find()
            >>> print("Database contains these record types:", all_labels)
            >>>
            >>> # Search for labels amongst records matching a pattern
            >>> query = SearchQuery(where={"name":{"$contains": "alice"}})
            >>> user_labels = labels_api.find(query)
            >>> print("User-related labels:", user_labels)
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/labels/search",
            data=typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers=headers,
        )
