"""AI API for RushDB Python SDK.

Provides methods for AI-assisted graph exploration, smart search,
and embedding index management.
"""

import warnings
from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

from ..models.api_response import ApiResponse
from ..models.record import Record
from ..models.result import RecordSearchResult
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI

if TYPE_CHECKING:
    from ..client import RushDB


class _AIIndexesNamespace:
    """Embedding index management sub-namespace.

    Accessed via ``db.ai.indexes``.
    """

    def __init__(self, client: "RushDB"):
        self._client = client

    def find(self) -> ApiResponse:
        """List all embedding index policies for the current project.

        Returns:
            ApiResponse: Response whose ``data`` is a list of embedding index objects.
        """
        response = self._client._make_request("GET", "/ai/indexes")
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def create(self, params: Dict[str, Any]) -> ApiResponse:
        """Create a new embedding index policy for a string property.

        Args:
            params: Index configuration. Required keys:

                - ``propertyName`` (str): Name of the property to embed.
                - ``label`` (str): Neo4j label to scope this index to
                  (e.g. ``"Book"``, ``"Task"``).

        Returns:
            ApiResponse: Response whose ``data`` is the created embedding index object.
        """
        response = self._client._make_request("POST", "/ai/indexes", params)
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def delete(self, index_id: str) -> ApiResponse:
        """Delete an embedding index policy by ID.

        Args:
            index_id: The ID of the embedding index to delete.

        Returns:
            ApiResponse: Response whose ``data`` contains a ``deleted`` boolean.
        """
        response = self._client._make_request("DELETE", f"/ai/indexes/{index_id}")
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def stats(self, index_id: str) -> ApiResponse:
        """Retrieve Neo4j-level statistics for an embedding index.

        Args:
            index_id: The ID of the embedding index.

        Returns:
            ApiResponse: Response whose ``data`` is an index-stats object.
        """
        response = self._client._make_request("GET", f"/ai/indexes/{index_id}/stats")
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def upsert_vectors(self, index_id: str, params: Dict[str, Any]) -> ApiResponse:
        """Bulk-seed an external index with pre-computed vectors.

        Idempotent — calling with the same ``recordId`` replaces the stored vector.

        Args:
            index_id: The ID of the external embedding index.
            params: Dict with key ``items``: a list of
                ``{"recordId": str, "vector": list[float]}`` objects.

        Returns:
            ApiResponse: Response confirming the upsert operation.
        """
        response = self._client._make_request(
            "POST", f"/ai/indexes/{index_id}/vectors/upsert", params
        )
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )


class AIAPI(BaseAPI):
    """AI-assisted graph exploration API.

    Accessed via ``db.ai``.

    Attributes:
        indexes (_AIIndexesNamespace): Embedding index management sub-namespace.

    Example::

        >>> db = RushDB(api_key="...")
        >>> schema = db.ai.get_schema()
        >>> results = db.ai.search("books about fast cars")
        >>> vectors = db.records.vector_search({
        ...     "query": "fast cars",
        ...     "propertyName": "description",
        ...     "labels": ["Book"],
        ... })
        >>> db.ai.indexes.create({"propertyName": "description", "label": "Book"})
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)
        self.indexes = _AIIndexesNamespace(client)

    def get_schema(
        self,
        params: Optional[Dict[str, Any]] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> ApiResponse:
        """Return the full graph schema as structured JSON.

        Each item contains the label name, record count, properties with value
        ranges/samples, and cross-label relationships with direction.
        Properties may include a ``vectorIndexes`` list when one or more embedding
        indexes exist for that property — each entry exposes ``id``,
        ``sourceType``, ``similarityFunction``, ``dimensions``, ``status``, and
        ``modelKey``.  A non-empty ``vectorIndexes`` list means the property is
        queryable with ``db.records.vector_search()``.

        Args:
            params: Optional filter. Pass ``{"labels": ["Label1"]}`` to scope
                the schema to specific labels only. Pass ``{"force": True}``
                to bypass the 1-hour schema cache and trigger a full
                recalculation.
            transaction: Optional transaction context.

        Returns:
            ApiResponse: Response whose ``data`` is a list of schema items.
        """
        headers: Dict[str, str] = {}
        if transaction is not None:
            tx_id = (
                transaction.id if isinstance(transaction, Transaction) else transaction
            )
            headers["x-transaction-id"] = tx_id

        response = self.client._make_request(
            "POST", "/ai/schema", params or {}, headers=headers or None
        )
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def get_schema_markdown(
        self,
        params: Optional[Dict[str, Any]] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> ApiResponse:
        """Return the full graph schema as compact Markdown tables.

        Token-efficient representation intended for direct LLM consumption.
        Includes labels with counts, properties with types and value
        ranges/samples, cross-label relationship map, and a **Semantic Search**
        column per property that shows
        ``sourceType similarityFunction dimensionsd [status]``
        (e.g. ``managed cosine 1536d [ready]``) for indexed properties, or
        ``—`` when no embedding index exists.

        Args:
            params: Optional filter. Pass ``{"labels": ["Label1"]}`` to scope
                the output to specific labels only. Pass ``{"force": True}``
                to bypass the 1-hour schema cache and trigger a full
                recalculation.
            transaction: Optional transaction context.

        Returns:
            ApiResponse: Response whose ``data`` is a Markdown string.
        """
        headers: Dict[str, str] = {}
        if transaction is not None:
            tx_id = (
                transaction.id if isinstance(transaction, Transaction) else transaction
            )
            headers["x-transaction-id"] = tx_id

        response = self.client._make_request(
            "POST", "/ai/schema/md", params or {}, headers=headers or None
        )
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def search(
        self,
        prompt: Union[str, Dict[str, Any]],
        current_query: Optional[SearchQuery] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> RecordSearchResult:
        """Perform AI-assisted smart search from natural language.

        RushDB converts ``prompt`` into a SearchQuery using the project schema,
        executes it, and returns matching records with the generated query
        attached to ``result.search_query``.

        Use ``db.records.vector_search({...})`` for direct vector similarity
        over embedding indexes.

        Args:
            prompt: Natural-language search request. Passing a dict is
                deprecated and delegates to ``db.records.vector_search``.
            current_query: Optional current SearchQuery context from a
                dashboard/query-builder session.
            transaction: Optional transaction context.

        Returns:
            RecordSearchResult: Matching records. The generated SearchQuery is
            available as ``result.search_query`` and server warnings as
            ``result.warnings``.
        """
        if isinstance(prompt, dict):
            warnings.warn(
                "db.ai.search({...}) is deprecated for vector search; "
                "use db.records.vector_search({...}) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.client.records.vector_search(prompt, transaction=transaction)

        headers = Transaction._build_transaction_header(transaction)
        generated = self.client._make_request(
            "POST",
            "/ai/search-query",
            {"prompt": prompt, "currentQuery": current_query},
            headers,
        )
        generated_data = generated.get("data") or {}
        search_query = generated_data.get("searchQuery") or {}

        response = self.client._make_request(
            "POST", "/records/search", search_query, headers
        )
        records = [Record(self.client, item) for item in response.get("data", [])]
        return RecordSearchResult(
            data=records,
            total=response.get("total", len(records)),
            search_query=cast(SearchQuery, search_query),
            client=self.client,
            warnings=generated_data.get("warnings") or [],
        )
