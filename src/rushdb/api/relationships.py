import typing
from typing import TYPE_CHECKING, Optional, TypedDict, Union

from ..models.relationship import Relationship
from ..models.result import SearchResult
from ..models.search_query import RelationshipSearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI
from .relationship_patterns import RelationshipPatternsAPI

if TYPE_CHECKING:
    from ..client import RushDB


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

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> relations_api = client.relationships
        >>>
        >>> # Find all relationships
        >>> relationships = relations_api.find()
        >>>
        >>> # Filter by edge type and properties
        >>> leads = relations_api.find({"where": {"type": "STARS_IN", "role": "lead"}})
        >>>
        >>> # Find relationships with pagination
        >>> page_1 = relations_api.find(pagination={"limit": 50, "skip": 0})
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)
        self.patterns = RelationshipPatternsAPI(client)

    def find(
        self,
        search_query: Optional[RelationshipSearchQuery] = None,
        pagination: Optional[PaginationParams] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> SearchResult[Relationship]:
        """Search for and retrieve relationships matching the specified criteria.

        Args:
            search_query: Relationship-edge criteria. ``where`` filters the edge —
                ``type`` maps to the relationship type, ``direction`` constrains
                direction, and every other key matches a user-defined edge property
                (full operator set: ``$gte``, ``$contains``, ``$in``, ``$exists``,
                logical grouping, ...). Use top-level ``source`` and ``target``
                (``{"labels": [...], "where": {...}}``) to filter endpoint records.
                ``limit``/``skip`` inside the query control pagination.
                If None, returns all relationships (subject to pagination limits).
            pagination: Pagination options (``limit`` and ``skip``). Merged into the
                search query body, overriding any ``limit``/``skip`` already inside
                ``search_query`` — useful for paginating a stored query object
                without mutating it.
            transaction: Optional transaction context.

        Returns:
            SearchResult[Relationship]: Matching relationships with ``total`` count.
                Iterable and indexable like a list; each item includes ``sourceId``,
                ``sourceLabel``, ``targetId``, ``targetLabel``, ``type``,
                ``direction``, and user-defined edge ``properties``.

        Raises:
            RushDBError: If the server request fails.

        Example:
            >>> relations_api = RelationsAPI(client)
            >>> result = relations_api.find({
            ...     "source": {"labels": ["MOVIE"], "where": {"title": "Inception"}},
            ...     "target": {"labels": ["ACTOR"]},
            ...     "where": {"type": "STARS_IN", "role": "lead"},
            ...     "limit": 50,
            ... })
            >>> result.total
            1
            >>> result[0]["properties"]["role"]
            'lead'
        """
        # Pagination lives in the body, same as records search. The `pagination`
        # argument overrides limit/skip inside `search_query` without mutating it.
        payload: typing.Dict[str, typing.Any] = dict(search_query or {})
        if pagination:
            if pagination.get("limit") is not None:
                payload["limit"] = pagination["limit"]
            if pagination.get("skip") is not None:
                payload["skip"] = pagination["skip"]

        # Build headers with transaction if present
        headers = Transaction._build_transaction_header(transaction)

        # Make request
        response = self.client._make_request(
            method="POST",
            path="/relationships/search",
            data=payload,
            headers=headers,
        )

        data = response.get("data", [])
        return SearchResult(
            data=data,
            total=response.get("total"),
            search_query=typing.cast(typing.Any, payload),
        )

    def create_many(
        self,
        *,
        source: dict,
        target: dict,
        type: Optional[str] = None,
        direction: Optional[str] = None,
        properties: Optional[dict] = None,
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
            properties (dict, optional): Shared user-defined properties to store on created edges.
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
        if properties is not None:
            payload["properties"] = properties
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
