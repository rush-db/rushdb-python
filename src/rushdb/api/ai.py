"""AI API for RushDB Python SDK.

Provides methods for graph ontology exploration, semantic vector search,
and embedding index management.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from ..models.api_response import ApiResponse
from ..models.record import Record
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
        >>> ontology = db.ai.get_ontology()
        >>> results = db.ai.search({"query": "fast cars", "propertyName": "description"})
        >>> db.ai.indexes.create({"propertyName": "description", "label": "Book"})
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)
        self.indexes = _AIIndexesNamespace(client)

    def get_ontology(
        self,
        params: Optional[Dict[str, Any]] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> ApiResponse:
        """Return the full graph ontology as structured JSON.

        Each item contains the label name, record count, properties with value
        ranges/samples, and cross-label relationships with direction.
        Properties may include a ``vectorIndexes`` list when one or more embedding
        indexes exist for that property — each entry exposes ``id``,
        ``sourceType``, ``similarityFunction``, ``dimensions``, ``status``, and
        ``modelKey``.  A non-empty ``vectorIndexes`` list means the property is
        queryable with ``db.ai.search()``.

        Args:
            params: Optional filter. Pass ``{"labels": ["Label1"]}`` to scope
                the ontology to specific labels only. Pass ``{"force": True}``
                to bypass the 1-hour ontology cache and trigger a full
                recalculation.
            transaction: Optional transaction context.

        Returns:
            ApiResponse: Response whose ``data`` is a list of ontology items.
        """
        headers: Dict[str, str] = {}
        if transaction is not None:
            tx_id = (
                transaction.id if isinstance(transaction, Transaction) else transaction
            )
            headers["x-transaction-id"] = tx_id

        response = self.client._make_request(
            "POST", "/ai/ontology", params or {}, headers=headers or None
        )
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def get_ontology_markdown(
        self,
        params: Optional[Dict[str, Any]] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> ApiResponse:
        """Return the full graph ontology as compact Markdown tables.

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
                to bypass the 1-hour ontology cache and trigger a full
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
            "POST", "/ai/ontology/md", params or {}, headers=headers or None
        )
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def search(self, params: Dict[str, Any]) -> ApiResponse:
        """Perform semantic (vector) search over indexed record properties.

        **Direct vector-index mode** (default, fast): used when no ``where``
        filter and at most one ``labels`` entry. Queries the shared global
        vector index directly.

        **Prefilter mode** (exact, slower): activated when a ``where``
        filter is supplied or ``labels`` contains more than one value.
        Candidates are first narrowed by MATCH/WHERE, then ranked by exact
        cosine similarity.

        Args:
            params: Search parameters. Expected keys:

                - ``query`` (str): The natural-language query text.
                - ``propertyName`` (str): Property that has been embedded.
                - ``labels`` (list[str], optional): Scope to specific labels.
                - ``where`` (dict, optional): Additional property filters.
                - ``limit`` (int, optional): Maximum number of results.

        Returns:
            ApiResponse: Response whose ``data`` is a list of semantic search
            result objects (each includes the matched record and a score).
        """
        response = self.client._make_request("POST", "/ai/search", params)
        records = [Record(self.client, item) for item in response.get("data", [])]
        return ApiResponse(
            data=records,
            success=response.get("success", True),
            total=response.get("total"),
        )
