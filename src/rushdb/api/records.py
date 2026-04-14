import typing
from typing import Any, Dict, List, Optional, Union

from ..models.record import Record
from ..models.relationship import RelationshipDetachOptions, RelationshipOptions
from ..models.result import RecordSearchResult
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


def _is_flat(obj: Any) -> bool:
    """Return True if obj is a dict with no nested dict/list values."""
    return isinstance(obj, dict) and not any(
        isinstance(v, (dict, list)) for v in obj.values()
    )


class RecordsAPI(BaseAPI):
    """API client for managing records in RushDB.

    The RecordsAPI provides a comprehensive interface for performing CRUD operations
    on records within a RushDB database. It supports creating, reading, updating,
    and deleting records, as well as managing relationships between records and
    importing data from various formats.

    This class handles:
    - Individual and batch record creation
    - Record updates (full replacement and partial updates)
    - Record deletion by ID or search criteria
    - Record searching and querying
    - Relationship management (attach/detach operations)
    - Data import from CSV format
    - Transaction support for all operations

    The API supports flexible input formats for record identification, accepting
    record IDs, record dictionaries, or Record objects interchangeably in most methods.

    Attributes:
        client: The underlying RushDB client instance for making HTTP requests.

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> records_api = client.records
        >>>
        >>> # Create a new record
        >>> user = records_api.create("User", {"name": "John", "email": "john@example.com"})
        >>>
        >>> # Search for records
        >>> from rushdb.models.search_query import SearchQuery
        >>> query = SearchQuery(where={"name": "John"})
        >>> results, total = records_api.find(query)
    """

    def set(
        self,
        record_id: str,
        data: Dict[str, Any],
        label: Optional[str] = None,
        vectors: Optional[List[Dict[str, Any]]] = None,
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Replace all data in a record with new data.

        This method performs a complete replacement of the record's data,
        removing any existing fields that are not present in the new data.

        Args:
            record_id (str): The unique identifier of the record to update.
            data (Dict[str, Any]): The new data to replace the existing record data.
            label (Optional[str]): Optional label to re-assign to the record.
            vectors (Optional[List[Dict[str, Any]]]): Optional pre-computed embedding vectors
                to write alongside the record update. Each entry must contain at least
                ``propertyName`` and ``vector``; ``similarityFunction`` is required when
                multiple external indexes match the same (label, propertyName).
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status.

        Raises:
            ValueError: If the record_id is invalid or empty.
            RequestError: If the server request fails.
        """
        headers = Transaction._build_transaction_header(transaction)
        payload: Dict[str, Any] = {"data": data}
        if label is not None:
            payload["label"] = label
        if vectors is not None:
            payload["vectors"] = vectors
        return self.client._make_request(
            "PUT", f"/records/{record_id}", payload, headers
        )

    def update(
        self,
        record_id: str,
        data: Dict[str, Any],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Partially update a record with new or modified fields.

        This method performs a partial update, merging the provided data
        with existing record data without removing existing fields.

        Args:
            record_id (str): The unique identifier of the record to update.
            data (Dict[str, Any]): The data to merge with the existing record data.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status.

        Raises:
            ValueError: If the record_id is invalid or empty.
            RequestError: If the server request fails.
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "PATCH", f"/records/{record_id}", data, headers
        )

    def create(
        self,
        label: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, bool]] = None,
        vectors: Optional[List[Dict[str, Any]]] = None,
        transaction: Optional[Transaction] = None,
    ) -> Record:
        """Create a new record in the database.

        Creates a single record with the specified label and data. The record
        will be assigned a unique identifier and can be optionally configured
        with parsing and response options.

        Args:
            label (str): The label/type to assign to the new record.
            data (Dict[str, Any]): The data to store in the record.
            options (Optional[Dict[str, bool]], optional): Configuration options for the operation.
                Available options:
                - returnResult (bool): Whether to return the created record data. Defaults to True.
                - suggestTypes (bool): Whether to automatically suggest data types. Defaults to True.
            vectors (Optional[List[Dict[str, Any]]]): Optional pre-computed embedding vectors
                to write alongside the record. Each entry must contain at least
                ``propertyName`` and ``vector``; ``similarityFunction`` is required when
                multiple external indexes match the same (label, propertyName).
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Record: A Record object representing the newly created record.

        Raises:
            ValueError: If the label is empty or data is invalid.
            RequestError: If the server request fails.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> new_record = records_api.create(
            ...     label="User",
            ...     data={"name": "John Doe", "email": "john@example.com"}
            ... )
            >>> print(new_record.data["name"])
            John Doe
        """
        headers = Transaction._build_transaction_header(transaction)

        payload: Dict[str, Any] = {
            "label": label,
            "data": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        if vectors is not None:
            payload["vectors"] = vectors
        response = self.client._make_request("POST", "/records", payload, headers)
        return Record(self.client, response.get("data"))

    def create_many(
        self,
        label: str,
        data: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        vectors: Optional[List[Optional[List[Dict[str, Any]]]]] = None,
        transaction: Optional[Transaction] = None,
    ) -> RecordSearchResult:
        """Create multiple flat records in a single operation.

        This helper maps directly to the ``/records/import/json`` endpoint and is
        intended for CSV-like flat rows (no nested objects or arrays). For nested
        or complex JSON payloads, use :meth:`import_json` instead.

        The behaviour mirrors the TypeScript SDK ``records.createMany`` method,
        including support for upsert semantics via ``options.mergeBy`` and
        ``options.mergeStrategy``.

        Args:
            label: The label/type to assign to all new records.
            data: A list of flat dictionaries. Each dictionary represents a single
                record. Nested objects/arrays are not supported here — raises
                ``ValueError`` if any item contains a nested object or list.
            options: Optional write options forwarded as-is to the server
                (e.g. ``suggestTypes``, ``mergeBy``, ``mergeStrategy``, etc.).
            vectors: Optional per-row inline vectors for external embedding indexes.
                ``vectors[i]`` is applied to ``data[i]``. Each element is a list of
                vector entry dicts: ``[{"propertyName": str, "vector": List[float],
                "similarityFunction"?: str}]``. Its length must not exceed
                ``len(data)``. Pass ``None`` in a slot to skip a row.
            transaction: Optional transaction context for the operation.

        Returns:
            RecordSearchResult: Search-result wrapper containing created records
                and total count.

        Raises:
            ValueError: If any item in ``data`` contains nested objects or arrays.
                Use :meth:`import_json` for nested JSON.
            ValueError: If ``vectors`` length exceeds the number of data rows.
        """
        items = data if isinstance(data, list) else [data]
        if not all(_is_flat(item) for item in items):
            raise ValueError(
                "records.create_many supports only flat records (no nested objects/arrays). "
                "Use records.import_json for nested JSON."
            )

        if vectors is not None and len(vectors) > len(items):
            raise ValueError(
                f"records.create_many: vectors length ({len(vectors)}) exceeds the "
                f"number of data rows ({len(items)})."
            )

        # Inject per-row vectors as $vectors so the backend BFS handles them
        if vectors:
            items = [
                (
                    {**item, "$vectors": vectors[i]}
                    if i < len(vectors) and vectors[i]
                    else item
                )
                for i, item in enumerate(items)
            ]

        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "data": items,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        response = self.client._make_request(
            "POST", "/records/import/json", payload, headers
        )
        records = [Record(self.client, r) for r in (response.get("data") or [])]
        return RecordSearchResult(
            data=records, total=response.get("total", len(records))
        )

    def import_json(
        self,
        data: Any,
        label: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        transaction: Optional[Transaction] = None,
    ) -> RecordSearchResult:
        """Import nested or complex JSON payloads.

        Works in two modes:

        - With ``label`` provided: imports ``data`` under the given label.
        - Without ``label``: expects ``data`` to be a mapping with a single
          top-level key that determines the label, e.g. ``{"ITEM": [...]}``.

        This mirrors the behaviour of the TypeScript SDK ``records.importJson``
        method and is suitable for nested, mixed, or hash-map-like JSON
        structures.

        Args:
            data: Arbitrary JSON-serialisable structure to import.
            label: Optional label; if omitted, inferred from a single top-level
                key of ``data``.
            options: Optional import/write options (see server docs).
            transaction: Optional transaction context for the operation.

        Returns:
            RecordSearchResult: Imported records and total count when
            ``options.returnResult`` is true.

        Raises:
            ValueError: If ``label`` is omitted and ``data`` is not an object
                with a single top-level key.
        """

        inferred_label = label
        payload_data: Any = data

        if inferred_label is None:
            if isinstance(data, dict):
                keys = list(data.keys())
                if len(keys) == 1:
                    inferred_label = keys[0]
                    payload_data = data[inferred_label]
                else:
                    raise ValueError(
                        "records.import_json: Missing `label`. Provide `label` or "
                        "pass an object with a single top-level key that determines "
                        "the label, e.g. { ITEM: [...] }."
                    )
            else:
                raise ValueError(
                    "records.import_json: Missing `label`. Provide `label` or pass "
                    "an object with a single top-level key that determines the "
                    "label, e.g. { ITEM: [...] }."
                )

        headers = Transaction._build_transaction_header(transaction)
        payload = {
            "label": inferred_label,
            "data": payload_data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }

        response = self.client._make_request(
            "POST", "/records/import/json", payload, headers
        )
        records = [Record(self.client, r) for r in (response.get("data") or [])]
        return RecordSearchResult(
            data=records, total=response.get("total", len(records))
        )

    def upsert(
        self,
        data: Dict[str, Any],
        label: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        vectors: Optional[List[Dict[str, Any]]] = None,
        transaction: Optional[Transaction] = None,
    ) -> Record:
        """Upsert a single record.

        Attempts to find an existing record matching the provided criteria and
        either updates it or creates a new one. This mirrors the behaviour of the
        TypeScript SDK ``records.upsert`` method.

        Args:
            data: A flat dictionary containing the record data.
            label: Optional label/type of the record.
            options: Optional upsert options, including ``mergeBy`` and
                ``mergeStrategy`` as well as standard write options.
            transaction: Optional transaction context for the operation.

        Returns:
            Record: The upserted record instance.
        """

        headers = Transaction._build_transaction_header(transaction)

        # Ensure upsert semantics always receive a mergeBy array by default.
        # This mirrors the JavaScript SDK behaviour where mergeBy defaults to []
        # and the server interprets an empty array as "use all incoming keys".
        normalized_options: Dict[str, Any] = {
            "returnResult": True,
            "suggestTypes": True,
            "mergeBy": [],
        }
        if options:
            normalized_options.update(options)

        payload: Dict[str, Any] = {
            "label": label,
            "data": data,
            "options": normalized_options,
        }
        if vectors is not None:
            payload["vectors"] = vectors

        response = self.client._make_request("POST", "/records", payload, headers)
        return Record(self.client, response.get("data"))

    def attach(
        self,
        source: Union[str, Dict[str, Any]],
        target: Union[
            str,
            List[str],
            Dict[str, Any],
            List[Dict[str, Any]],
            "Record",
            List["Record"],
        ],
        options: Optional[RelationshipOptions] = None,
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Create relationships by attaching target records to a source record.

        Establishes relationships between a source record and one or more target records.
        The source and target can be specified using various formats including IDs,
        record dictionaries, or Record objects.

        Args:
            source (Union[str, Dict[str, Any]]): The source record to attach targets to.
                Can be a record ID string or a record dictionary containing '__id'.
            target (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]):
                The target record(s) to attach to the source. Accepts multiple formats:
                - Single record ID (str)
                - List of record IDs (List[str])
                - Record dictionary with '__id' field
                - List of record dictionaries
                - Record object
                - List of Record objects
            options (Optional[RelationshipOptions], optional): Additional options for the relationship.
                Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status.

        Raises:
            ValueError: If source or target format is invalid or missing required '__id' fields.
            RequestError: If the server request fails.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> # Attach using record IDs
            >>> response = records_api.attach("source_id", ["target1_id", "target2_id"])
            >>>
            >>> # Attach using Record objects
            >>> response = records_api.attach(source_record, target_records)
        """
        headers = Transaction._build_transaction_header(transaction)

        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {"targetIds": target_ids}
        if options:
            payload.update(typing.cast(typing.Dict[str, typing.Any], options))
        return self.client._make_request(
            "POST", f"/relationships/{source_id}", payload, headers
        )

    def detach(
        self,
        source: Union[str, Dict[str, Any]],
        target: Union[
            str,
            List[str],
            Dict[str, Any],
            List[Dict[str, Any]],
            "Record",
            List["Record"],
        ],
        options: Optional[RelationshipDetachOptions] = None,
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Remove relationships by detaching target records from a source record.

        Removes existing relationships between a source record and one or more target records.
        The source and target can be specified using various formats including IDs,
        record dictionaries, or Record objects.

        Args:
            source (Union[str, Dict[str, Any]]): The source record to detach targets from.
                Can be a record ID string or a record dictionary containing '__id'.
            target (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]):
                The target record(s) to detach from the source. Accepts multiple formats:
                - Single record ID (str)
                - List of record IDs (List[str])
                - Record dictionary with '__id' field
                - List of record dictionaries
                - Record object
                - List of Record objects
            options (Optional[RelationshipDetachOptions], optional): Additional options for the detach operation.
                Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status.

        Raises:
            ValueError: If source or target format is invalid or missing required '__id' fields.
            RequestError: If the server request fails.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> # Detach using record IDs
            >>> response = records_api.detach("source_id", ["target1_id", "target2_id"])
            >>>
            >>> # Detach using Record objects
            >>> response = records_api.detach(source_record, target_records)
        """
        headers = Transaction._build_transaction_header(transaction)

        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {"targetIds": target_ids}
        if options:
            payload.update(typing.cast(typing.Dict[str, typing.Any], options))
        return self.client._make_request(
            "PUT", f"/relationships/{source_id}", payload, headers
        )

    def delete(
        self, search_query: SearchQuery, transaction: Optional[Transaction] = None
    ) -> Dict[str, str]:
        """Delete multiple records matching the specified search criteria.

        Deletes all records that match the provided search query. This operation
        can delete multiple records in a single request based on the query conditions.

        Args:
            search_query (SearchQuery): The search criteria to identify records for deletion.
                This defines which records should be deleted based on their properties,
                labels, relationships, or other query conditions.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status and
                information about the number of records deleted.

        Raises:
            ValueError: If the search_query is invalid or malformed.
            RequestError: If the server request fails.

        Warning:
            This operation can delete multiple records at once. Use with caution
            and ensure your search query is properly constructed to avoid
            unintended deletions.

        Example:
            >>> from rushdb.models.search_query import SearchQuery
            >>> records_api = RecordsAPI(client)
            >>> query = SearchQuery(where={"status": "inactive"})
            >>> response = records_api.delete(query)
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/records/delete",
            typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers,
        )

    def delete_by_id(
        self,
        id_or_ids: Union[str, List[str]],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Delete one or more records by their unique identifiers.

        Deletes records by their specific IDs. Can handle both single record
        deletion and bulk deletion of multiple records.

        Args:
            id_or_ids (Union[str, List[str]]): The record identifier(s) to delete.
                Can be a single record ID string or a list of record ID strings.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status and
                information about the deletion operation.

        Raises:
            ValueError: If any of the provided IDs are invalid or empty.
            RequestError: If the server request fails.

        Note:
            When deleting multiple records (list of IDs), the operation uses a
            batch delete with a limit of 1000 records. For single record deletion,
            it uses a direct DELETE request.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> # Delete a single record
            >>> response = records_api.delete_by_id("record_123")
            >>>
            >>> # Delete multiple records
            >>> record_ids = ["record_123", "record_456", "record_789"]
            >>> response = records_api.delete_by_id(record_ids)
        """
        headers = Transaction._build_transaction_header(transaction)

        if isinstance(id_or_ids, list):
            return self.client._make_request(
                "POST",
                "/records/delete",
                {"limit": 1000, "where": {"$id": {"$in": id_or_ids}}},
                headers,
            )
        return self.client._make_request(
            "DELETE", f"/records/{id_or_ids}", None, headers
        )

    def find_by_id(
        self,
        id_or_ids: Union[str, List[str]],
        transaction: Optional[Transaction] = None,
    ) -> Union["Record", RecordSearchResult]:
        """Retrieve one or more records by their unique identifiers.

        Mirrors the TypeScript SDK ``records.findById`` method.

        Args:
            id_or_ids: A single record ID string or a list of ID strings.
            transaction: Optional transaction context for the operation.

        Returns:
            A single :class:`Record` when ``id_or_ids`` is a string, or a
            :class:`RecordSearchResult` when ``id_or_ids`` is a list.
        """
        headers = Transaction._build_transaction_header(transaction)
        if isinstance(id_or_ids, list):
            response = self.client._make_request(
                "POST", "/records", {"ids": id_or_ids}, headers
            )
            records = [Record(self.client, r) for r in (response.get("data") or [])]
            return RecordSearchResult(
                data=records, total=response.get("total", len(records))
            )
        response = self.client._make_request(
            "GET", f"/records/{id_or_ids}", None, headers
        )
        return Record(self.client, response.get("data", response))

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        record_id: Optional[str] = None,
        transaction: Optional[Transaction] = None,
    ) -> RecordSearchResult:
        try:
            headers = Transaction._build_transaction_header(transaction)

            path = f"/records/{record_id}/search" if record_id else "/records/search"
            response = self.client._make_request(
                "POST",
                path,
                data=typing.cast(typing.Dict[str, typing.Any], search_query or {}),
                headers=headers,
            )

            records = [
                Record(self.client, record) for record in response.get("data", [])
            ]
            total = response.get("total", 0)

            return RecordSearchResult(
                data=records, total=total, search_query=search_query
            )
        except Exception:
            return RecordSearchResult(data=[], total=0)

    def find_one(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> Optional[Record]:
        """Return the first record matching the query, or ``None`` if no records match.

        Equivalent to calling :meth:`find` with ``limit=1`` and returning the first
        element (or ``None``). Mirrors the TypeScript SDK ``records.findOne`` method.

        Args:
            search_query: Optional search query to filter records.
            transaction: Optional transaction context for the operation.

        Returns:
            The first matching :class:`Record`, or ``None``.
        """
        query: Dict[str, Any] = dict(search_query or {})
        query["limit"] = 1
        result = self.find(typing.cast(SearchQuery, query), transaction=transaction)
        return result.data[0] if result.data else None

    def find_uniq(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> Optional[Record]:
        """Return exactly one record matching the query, raising if more than one match.

        Fetches up to 2 records. Raises :class:`~rushdb.common.NonUniqueResultError`
        when the total result count exceeds 1. Returns ``None`` when no records match.
        Mirrors the TypeScript SDK ``records.findUniq`` method.

        Args:
            search_query: Optional search query to filter records.
            transaction: Optional transaction context for the operation.

        Returns:
            The single matching :class:`Record`, or ``None``.

        Raises:
            NonUniqueResultError: When more than one record matches the query.
        """
        from ..common import NonUniqueResultError

        query: Dict[str, Any] = dict(search_query or {})
        query["limit"] = 2
        result = self.find(typing.cast(SearchQuery, query), transaction=transaction)
        if result.total > 1:
            raise NonUniqueResultError(result.total)
        return result.data[0] if result.data else None

    def export(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> str:
        """Export records as CSV text.

        Mirrors the TypeScript SDK ``records.export`` method.

        Args:
            search_query: Optional search query to filter which records to export.
            transaction: Optional transaction context for the operation.

        Returns:
            A CSV string containing the exported records.
        """
        headers = Transaction._build_transaction_header(transaction)
        response = self.client._make_request(
            "POST", "/records/export", typing.cast(Dict[str, Any], search_query or {}), headers
        )
        return response

    def import_csv(
        self,
        label: str,
        data: str,
        options: Optional[Dict[str, bool]] = None,
        parse_config: Optional[Dict[str, Any]] = None,
        vectors: Optional[List[Optional[List[Dict[str, Any]]]]] = None,
        transaction: Optional[Transaction] = None,
    ) -> RecordSearchResult:
        """Import records from CSV data.

        Parses CSV data and creates multiple records from the content. Each row
        in the CSV becomes a separate record with the specified label. The first
        row is typically treated as headers defining the field names.

        Args:
            label (str): The label/type to assign to all records created from the CSV.
            data (str): The CSV content to import as a string.
            options (Optional[Dict[str, bool]]): Import write options (see create_many for list).
            parse_config (Optional[Dict[str, Any]]): CSV parsing configuration keys (subset of PapaParse):
                - delimiter (str)
                - header (bool)
                - skipEmptyLines (bool | 'greedy')
                - dynamicTyping (bool)
                - quoteChar (str)
                - escapeChar (str)
                - newline (str)
            vectors: Optional per-row inline vectors for external embedding indexes.
                ``vectors[i]`` is applied to CSV row ``i`` (0-based, after header row).
                Each element is a list of vector entry dicts:
                ``[{"propertyName": str, "vector": List[float], "similarityFunction"?: str}]``.
                Its length must not exceed the number of data rows — validated server-side.
                Pass ``None`` in a slot to skip a row.
            transaction (Optional[Transaction]): Transaction context for the operation.

        Returns:
            RecordSearchResult: Imported records and total count.

        Raises:
            ValueError: If the label is empty or CSV data is invalid/malformed.
            RequestError: If the server request fails.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> csv_content = '''name,email,age
            ... John Doe,john@example.com,30
            ... Jane Smith,jane@example.com,25'''
            >>>
            >>> imported_records = records_api.import_csv("User", csv_content)
            >>> print(f"Imported {len(imported_records.data)} records")
        """
        headers = Transaction._build_transaction_header(transaction)

        payload: Dict[str, Any] = {
            "label": label,
            "data": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        if parse_config:
            # pass through only known parse config keys, ignore others silently
            allowed_keys = {
                "delimiter",
                "header",
                "skipEmptyLines",
                "dynamicTyping",
                "quoteChar",
                "escapeChar",
                "newline",
            }
            payload["parseConfig"] = {
                k: v
                for k, v in parse_config.items()
                if k in allowed_keys and v is not None
            }

        if vectors is not None:
            payload["vectors"] = vectors

        response = self.client._make_request(
            "POST", "/records/import/csv", payload, headers
        )
        records = [Record(self.client, r) for r in (response.get("data") or [])]
        return RecordSearchResult(
            data=records, total=response.get("total", len(records))
        )

    @staticmethod
    def _extract_target_ids(
        target: Union[
            str,
            List[str],
            Dict[str, Any],
            List[Dict[str, Any]],
            "Record",
            List["Record"],
        ],
    ) -> List[str]:
        """Extract record IDs from various input types and formats.

        This utility method handles the conversion of different target input formats
        into a standardized list of record ID strings. It supports multiple input
        types commonly used throughout the API for specifying target records.

        Args:
            target (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]):
                The target input to extract IDs from. Supported formats:
                - str: Single record ID
                - List[str]: List of record IDs
                - Dict[str, Any]: Record dictionary containing '__id' field
                - List[Dict[str, Any]]: List of record dictionaries with '__id' fields
                - Record: Record object with data containing '__id'
                - List[Record]: List of Record objects

        Returns:
            List[str]: List of extracted record ID strings.

        Raises:
            ValueError: If the target format is not supported or if required '__id'
                fields are missing from dictionary or Record objects.

        Note:
            This is an internal utility method used by attach() and detach() methods
            to normalize their input parameters.

        Example:
            >>> # Extract from string
            >>> ids = RecordsAPI._extract_target_ids("record_123")
            >>> # Returns: ["record_123"]
            >>>
            >>> # Extract from Record objects
            >>> record_obj = Record(client, {"__id": "record_456", "name": "Test"})
            >>> ids = RecordsAPI._extract_target_ids(record_obj)
            >>> # Returns: ["record_456"]
        """
        if isinstance(target, str):
            return [target]
        elif isinstance(target, list):
            ids = []
            for t in target:
                if isinstance(t, str):
                    ids.append(t)
                elif isinstance(t, Record) and "__id" in t.data:
                    ids.append(t.data["__id"])
                elif isinstance(t, dict) and "__id" in t:
                    ids.append(t["__id"])
                else:
                    raise ValueError(f"Cannot extract id from list item: {t!r}")
            return ids
        elif isinstance(target, Record) and "__id" in target.data:
            return [target.data["__id"]]
        elif isinstance(target, dict) and "__id" in target:
            return [target["__id"]]
        raise ValueError("Invalid target format")
