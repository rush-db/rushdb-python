import typing
from typing import Any, Dict, List, Optional, Union

from ..models.record import Record
from ..models.relationship import RelationshipDetachOptions, RelationshipOptions
from ..models.result import RecordSearchResult
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


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
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Replace all data in a record with new data.

        This method performs a complete replacement of the record's data,
        removing any existing fields that are not present in the new data.

        Args:
            record_id (str): The unique identifier of the record to update.
            data (Dict[str, Any]): The new data to replace the existing record data.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Dict[str, str]: Response from the server containing operation status.

        Raises:
            ValueError: If the record_id is invalid or empty.
            RequestError: If the server request fails.
        """
        headers = Transaction._build_transaction_header(transaction)
        return self.client._make_request("PUT", f"/records/{record_id}", data, headers)

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

        payload = {
            "label": label,
            "data": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        response = self.client._make_request("POST", "/records", payload, headers)
        return Record(self.client, response.get("data"))

    def create_many(
        self,
        label: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        options: Optional[Dict[str, bool]] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Record]:
        """Create multiple records in a single operation.

        Creates multiple records with the same label but different data.
        This is more efficient than creating records individually when
        you need to insert many records at once.

        Args:
            label (str): The label/type to assign to all new records.
            data (Union[Dict[str, Any], List[Dict[str, Any]]]): The data for the records.
                Can be a single dictionary or a list of dictionaries.
            options (Optional[Dict[str, bool]], optional): Configuration options for the operation.
                Available options:
                - returnResult (bool): Whether to return the created records data. Defaults to True.
                - suggestTypes (bool): Whether to automatically suggest data types. Defaults to True.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            List[Record]: A list of Record objects representing the newly created records.

        Raises:
            ValueError: If the label is empty or data is invalid.
            RequestError: If the server request fails.

        Example:
            >>> records_api = RecordsAPI(client)
            >>> users_data = [
            ...     {"name": "John Doe", "email": "john@example.com"},
            ...     {"name": "Jane Smith", "email": "jane@example.com"}
            ... ]
            >>> new_records = records_api.create_many("User", users_data)
            >>> print(len(new_records))
            2
        """
        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "data": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        response = self.client._make_request(
            "POST", "/records/import/json", payload, headers
        )
        return [Record(self.client, record) for record in response.get("data")]

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

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        record_id: Optional[str] = None,
        transaction: Optional[Transaction] = None,
    ) -> RecordSearchResult:
        """Search for and retrieve records matching the specified criteria.

        Searches the database for records that match the provided search query.
        Can perform both general searches across all records or searches within
        the context of a specific record's relationships.

        Args:
            search_query (Optional[SearchQuery], optional): The search criteria to filter records.
                If None, returns all records (subject to default limits). Defaults to None.
            record_id (Optional[str], optional): If provided, searches within the context
                of this specific record's relationships. Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            RecordSearchResult: A result object containing:
                - Iterable list of Record objects matching the search criteria
                - Total count of matching records (may be larger than returned list if pagination applies)
                - Additional metadata about the search operation
                - Convenient properties like .has_more, .count, etc.

        Example:
            >>> from rushdb.models.search_query import SearchQuery
            >>> records_api = RecordsAPI(client)
            >>>
            >>> # Find all records with a specific label
            >>> query = SearchQuery(labels=["User"])
            >>> result = records_api.find(query)
            >>> print(f"Found {result.count} records out of {result.total} total")
            >>>
            >>> # Iterate over results
            >>> for record in result:
            ...     print(f"User: {record.get('name', 'Unknown')}")
            >>>
            >>> # Access specific records
            >>> first_user = result[0] if result else None
            >>>
            >>> # Check if there are more results
            >>> if result.has_more:
            ...     print("There are more records available")
            >>>
            >>> # Find records related to a specific record
            >>> related_result = records_api.find(query, record_id="parent_123")
        """

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

    def import_csv(
        self,
        label: str,
        data: str,
        options: Optional[Dict[str, bool]] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Dict[str, Any]]:
        """Import records from CSV data.

        Parses CSV data and creates multiple records from the content. Each row
        in the CSV becomes a separate record with the specified label. The first
        row is typically treated as headers defining the field names.

        Args:
            label (str): The label/type to assign to all records created from the CSV.
            data (Union[str, bytes]): The CSV content to import. Can be provided
                as a string.
            options (Optional[Dict[str, bool]], optional): Configuration options for the import operation.
                Available options:
                - returnResult (bool): Whether to return the created records data. Defaults to True.
                - suggestTypes (bool): Whether to automatically suggest data types for CSV columns. Defaults to True.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            List[Dict[str, Any]]: List of dictionaries representing the imported records,
                or server response data depending on the options.

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
            >>> print(f"Imported {len(imported_records)} records")
        """
        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "data": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }

        return self.client._make_request(
            "POST", "/records/import/csv", payload, headers
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
        ]
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
            return [t.get("__id", "") if isinstance(t, dict) else "" for t in target]
        elif isinstance(target, Record) and "__id" in target.data:
            return [target.data["__id"]]
        elif isinstance(target, dict) and "__id" in target:
            return [target["__id"]]
        raise ValueError("Invalid target format")
