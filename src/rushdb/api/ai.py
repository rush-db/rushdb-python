"""AI API for RushDB Python SDK.

Provides methods for AI-assisted graph exploration, smart search,
and embedding index management.
"""

import warnings
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from ..models.api_response import ApiResponse
from ..models.catalog import (
    JoinCandidate,
    NameSuggestion,
    SchemaSummaryLabel,
    ValueMatchesData,
)
from ..models.property import ValueMatchMode
from ..models.record import Record
from ..models.result import RecordSearchResult
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
        >>> found = db.ai.search_values("spiderman", match="similar")
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

    def _catalog_read(self, path: str, body: Dict[str, Any]) -> ApiResponse:
        response = self.client._make_request("POST", path, body)
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def search_values(
        self,
        text: str,
        match: Optional[ValueMatchMode] = None,
        labels: Optional[List[str]] = None,
        limit: Optional[int] = None,
        min_similarity: Optional[float] = None,
        case_sensitive: Optional[bool] = None,
    ) -> "ApiResponse[ValueMatchesData]":
        """Find stored values matching a text across every property.

        Each match names the label and property holding the value and its
        record count. It maps a word in a question to the value the data
        actually stores (``"positive"`` to ``KCT = "+"`` once combined with
        :meth:`get_schema_summary`).

        Args:
            text: The text to look for.
            match: ``"contains"`` (default), ``"prefix"``, ``"exact"`` or
                ``"similar"`` for near spellings (``spiderman`` finds
                ``Spider-Man``).
            labels: Labels to search (all when omitted).
            limit: Most matches (default 50, at most 1000).
            min_similarity: ``"similar"`` only: least similarity, 0 to 1
                (default 0.6).
            case_sensitive: Match case exactly (default ``False``).

        Returns:
            ApiResponse: ``data`` holds ``matches`` (each ``label``,
            ``property``, ``value``, ``count``), ``total`` (matches before
            ``limit``) and, when some properties could not be searched within
            the request limits, ``skipped`` as ``label.property``.
        """
        body: Dict[str, Any] = {"text": text}
        if match is not None:
            body["match"] = match
        if case_sensitive is not None:
            body["caseSensitive"] = case_sensitive
        if min_similarity is not None:
            body["minSimilarity"] = min_similarity
        if labels is not None:
            body["labels"] = labels
        if limit is not None:
            body["limit"] = limit
        return self._catalog_read("/ai/values/search", body)

    def get_schema_summary(
        self,
        labels: Optional[List[str]] = None,
        few_values: Optional[int] = None,
    ) -> "ApiResponse[List[SchemaSummaryLabel]]":
        """Every label with its properties in one read, from the live catalog.

        Types, record and exact distinct counts, numeric and date ranges, the
        values of properties that hold few, and relationship shapes.

        Args:
            labels: Labels to summarize (all when omitted).
            few_values: List a property's values when it holds at most this
                many (default 10).

        Returns:
            ApiResponse: ``data`` is a list of labels, each with ``name``,
            ``recordsCount``, ``properties`` and ``relationships``.
        """
        body: Dict[str, Any] = {}
        if labels is not None:
            body["labels"] = labels
        if few_values is not None:
            body["fewValues"] = few_values
        return self._catalog_read("/ai/schema/summary", body)

    def resolve_names(
        self, text: str, limit: Optional[int] = None
    ) -> "ApiResponse[List[NameSuggestion]]":
        """Labels and properties spelled like a name.

        Ignores case, separators and plural endings: the answer to "no such
        label or property" (``patients.birthdate`` to ``Patient.Birthday``).

        Args:
            text: The name, optionally as ``Label.property``.
            limit: Most suggestions.

        Returns:
            ApiResponse: ``data`` is a list of suggestions, each with
            ``label``, ``property`` (for a property) and ``score`` (spelling
            similarity, 0 to 1).
        """
        body: Dict[str, Any] = {"text": text}
        if limit is not None:
            body["limit"] = limit
        return self._catalog_read("/ai/schema/names", body)

    def get_join_candidates(
        self,
        labels: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
    ) -> "ApiResponse[List[JoinCandidate]]":
        """Properties that look like references to another label's key.

        Found from property names and exact value containment (no language
        model), each with its evidence. RushDB Cloud only: in direct mode it
        raises :class:`~rushdb.common.CloudOnlyError`.

        Args:
            labels: Labels the candidates must touch (all when omitted).
            min_confidence: Least confidence, 0 to 1 (default 0.5).

        Returns:
            ApiResponse: ``data`` is a list of candidates, each with
            ``source`` and ``target`` (``label``, ``property``), ``reasons``,
            ``relationshipType``, ``confidence``, ``evidence`` and
            ``rationale``.
        """
        body: Dict[str, Any] = {}
        if labels is not None:
            body["labels"] = labels
        if min_confidence is not None:
            body["minConfidence"] = min_confidence
        return self._catalog_read("/ai/schema/join-candidates", body)

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
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> RecordSearchResult:
        """Perform AI-assisted smart search from natural language.

        RushDB turns ``prompt`` into one read-only SQL statement over the
        project's schema, runs it, and returns the result with the statement
        as ``result.sql``, a short title as ``result.name`` and any generation
        warnings as ``result.warnings``. Rows that select a record's ``__id``
        come back as full records; aggregates come back as plain rows.
        ``result.next()`` pages through the statement.

        Use ``db.records.vector_search({...})`` for direct vector similarity
        over embedding indexes.

        Args:
            prompt: Natural-language search request. Passing a dict is
                deprecated and delegates to ``db.records.vector_search``.
            skip: Rows to skip (default 0).
            limit: Rows to return, at most 1000 (default 100).
            transaction: Only used by the deprecated dict form.

        Returns:
            RecordSearchResult: The statement's first page of rows.
        """
        if isinstance(prompt, dict):
            warnings.warn(
                "db.ai.search({...}) is deprecated for vector search; "
                "use db.records.vector_search({...}) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.client.records.vector_search(prompt, transaction=transaction)

        generated = self.client._make_request(
            "POST", "/ai/sql-search", {"prompt": prompt}
        )
        generated_data = generated.get("data") or {}
        result = self.run_sql(generated_data.get("sql", ""), skip=skip, limit=limit)
        result._name = generated_data.get("name")
        result._warnings = generated_data.get("warnings") or []
        return result

    def run_sql(
        self,
        sql: str,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RecordSearchResult:
        """Run one read-only SQL statement over the project's schema, as Smart
        search does: a statement from ``ai.search`` (its ``sql``), or one
        written by hand. Labels are tables; relationship types are
        ``rushdb_edges.<type>`` tables.

        Args:
            sql: One read-only SELECT statement.
            skip: Rows to skip (default 0).
            limit: Rows to return, at most 1000 (default 100).

        Returns:
            RecordSearchResult: Full records for rows that select a record's
            ``__id``, otherwise the rows themselves; ``result.sql`` holds the
            statement and ``result.next()`` fetches the following page.
        """
        page = {"skip": skip or 0, "limit": limit or 100}
        response = self.client._make_request(
            "POST", "/records/sql-search", {"sql": sql, **page}
        )
        records = [Record(self.client, item) for item in response.get("data", [])]
        return RecordSearchResult(
            data=records,
            total=response.get("total", len(records)),
            client=self.client,
            sql=sql,
            sql_page=page,
        )
