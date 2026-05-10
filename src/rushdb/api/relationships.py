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

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        pagination: Optional[PaginationParams] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> List[Relationship]:
        """Search for and retrieve relationships matching the specified criteria.

        Args:
            search_query: The search criteria to filter relationships.
                If None, returns all relationships (subject to pagination limits).
            pagination: Pagination options (``limit`` and ``skip``).
            transaction: Optional transaction context.

        Returns:
            List[Relationship]: Relationships matching the search criteria.

        Raises:
            RushDBError: If the server request fails.

        Example:
            >>> relations_api = RelationsAPI(client)
            >>> all_rels = relations_api.find()
            >>> page = relations_api.find(pagination={"limit": 50, "skip": 0})
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

        return response.get("data", [])

    def create_many(
        self,
        *,
        source: dict,
        target: dict,
        type: Optional[str] = None,
        direction: Optional[str] = None,
        many_to_many: Optional[bool] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> dict:
        """Bulk create relationships by matching keys or many-to-many cartesian.

        Modes:
            1. Key-match (default): requires source.key and target.key, creates relationships where source[key] = target[key].
            2. many_to_many=True: cartesian across filtered sets (requires where filters on both source & target and omits keys).

        Args:
            source (dict): { label: str, key?: str, where?: dict }
            target (dict): { label: str, key?: str, where?: dict }
            type (str, optional): Relationship type override.
            direction (str, optional): 'in' | 'out'. Defaults to 'out' server-side when omitted.
            many_to_many (bool, optional): Enable cartesian mode (requires filters, disallows keys).
            transaction (Transaction|str, optional): Transaction context.

        Returns:
            dict: API response payload.
        """
        headers = Transaction._build_transaction_header(transaction)
        payload: dict = {"source": source, "target": target}
        if type:
            payload["type"] = type
        if direction:
            payload["direction"] = direction
        if many_to_many is not None:
            payload["manyToMany"] = many_to_many
        return self.client._make_request(
            "POST", "/relationships/create-many", payload, headers
        )

    def delete_many(
        self,
        *,
        source: dict,
        target: dict,
        type: Optional[str] = None,
        direction: Optional[str] = None,
        many_to_many: Optional[bool] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> dict:
        """Bulk delete relationships using same contract as create_many.

        See create_many for argument semantics.
        """
        headers = Transaction._build_transaction_header(transaction)
        payload: dict = {"source": source, "target": target}
        if type:
            payload["type"] = type
        if direction:
            payload["direction"] = direction
        if many_to_many is not None:
            payload["manyToMany"] = many_to_many
        return self.client._make_request(
            "POST", "/relationships/delete-many", payload, headers
        )
