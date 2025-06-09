import typing
from typing import List, Optional, TypedDict, Union
from urllib.parse import urlencode

from ..models.relationship import Relationship
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class PaginationParams(TypedDict, total=False):
    """TypedDict for pagination parameters in relationship queries.

    Defines the structure for pagination options when querying relationships,
    allowing for efficient retrieval of large result sets.

    Attributes:
        limit (int): Maximum number of relationships to return in a single request.
        skip (int): Number of relationships to skip from the beginning of the result set.
            Used for implementing pagination by skipping already retrieved items.
    """

    limit: int
    skip: int


class RelationsAPI(BaseAPI):
    """API client for managing relationships in RushDB.

    The RelationsAPI provides functionality for querying and analyzing relationships
    between records in the database. Relationships represent connections or associations
    between different records, enabling graph-like data structures and complex queries.

    This class handles:
    - Relationship discovery and searching
    - Pagination support for large result sets
    - Transaction support for operations
    - Flexible querying with various search criteria

    Relationships are the connections between records that enable building complex
    data models and performing graph traversals within the database.

    Attributes:
        client: The underlying RushDB client instance for making HTTP requests.

    Note:
        This API currently contains async methods. Ensure you're using it in an
        async context or consider updating to sync methods if needed.

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> relations_api = client.relationships
        >>>
        >>> # Find all relationships
        >>> relationships = await relations_api.find()
        >>>
        >>> # Find relationships with pagination
        >>> pagination = {"limit": 50, "skip": 0}
        >>> page_1 = await relations_api.find(pagination=pagination)
    """

    async def find(
        self,
        search_query: Optional[SearchQuery] = None,
        pagination: Optional[PaginationParams] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> List[Relationship]:
        """Search for and retrieve relationships matching the specified criteria.

        Asynchronously searches the database for relationships that match the provided
        search query. Supports pagination for efficient handling of large result sets
        and can operate within transaction contexts.

        Args:
            search_query (Optional[SearchQuery], optional): The search criteria to filter relationships.
                If None, returns all relationships (subject to pagination limits). Can include
                filters for relationship types, source/target records, or other metadata.
                Defaults to None.
            pagination (Optional[PaginationParams], optional): Pagination options to control
                result set size and offset. Contains:
                - limit (int): Maximum number of relationships to return
                - skip (int): Number of relationships to skip from the beginning
                Defaults to None.
            transaction (Optional[Union[Transaction, str]], optional): Transaction context
                for the operation. Can be either a Transaction object or a transaction ID string.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            List[Relationship]: List of Relationship objects matching the search criteria.
                The list will be limited by pagination parameters if provided.

        Raises:
            RequestError: If the server request fails.

        Note:
            This is an async method and must be awaited when called.

        Example:
            >>> from rushdb.models.search_query import SearchQuery
            >>> relations_api = RelationsAPI(client)
            >>>
            >>> # Find all relationships
            >>> all_relationships = await relations_api.find()
            >>>
            >>> # Find relationships with pagination
            >>> pagination = PaginationParams(limit=50, skip=0)
            >>> first_page = await relations_api.find(pagination=pagination)
            >>>
            >>> # Find relationships with search criteria
            >>> query = SearchQuery(where={"flight_type": "domestic"})
            >>> follow_relationships = await relations_api.find(search_query=query)
            >>>
            >>> # Combine search and pagination
            >>> filtered_page = await relations_api.find(
            ...     search_query=query,
            ...     pagination=PaginationParams(limit=25, skip=25)
            ... )
        """
        # Build query string for pagination
        query_params = {}
        if pagination:
            if pagination.get("limit") is not None:
                query_params["limit"] = str(pagination["limit"])
            if pagination.get("skip") is not None:
                query_params["skip"] = str(pagination["skip"])

        # Construct path with query string
        query_string = f"?{urlencode(query_params)}" if query_params else ""
        path = f"/relationships/search{query_string}"

        # Build headers with transaction if present
        headers = Transaction._build_transaction_header(transaction)

        # Make request
        response = self.client._make_request(
            method="POST",
            path=path,
            data=typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers=headers,
        )

        return response.data
