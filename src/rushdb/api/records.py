import typing
from typing import Any, Dict, List, Optional, Union

from ..models.record import Record
from ..models.relationship import RelationshipDetachOptions, RelationshipOptions
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class RecordsAPI(BaseAPI):
    """API for managing records in RushDB."""

    def set(
        self,
        record_id: str,
        data: Dict[str, Any],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Update a record by ID."""
        headers = Transaction._build_transaction_header(transaction)
        return self.client._make_request(
            "PUT", f"/api/v1/records/{record_id}", data, headers
        )

    def update(
        self,
        record_id: str,
        data: Dict[str, Any],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Update a record by ID."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "PATCH", f"/api/v1/records/{record_id}", data, headers
        )

    def create(
        self,
        label: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, bool]] = None,
        transaction: Optional[Transaction] = None,
    ) -> Record:
        """Create a new record.

        Args:
            label: Label for the record
            data: Record data
            options: Optional parsing and response options (returnResult, suggestTypes)
            transaction: Optional transaction object

        Returns:
            Record object
            :param
        """
        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "payload": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        response = self.client._make_request(
            "POST", "/api/v1/records", payload, headers
        )
        return Record(self.client, response.get("data"))

    def create_many(
        self,
        label: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        options: Optional[Dict[str, bool]] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Record]:
        """Create multiple records.

        Args:
            label: Label for all records
            data: List or Dict of record data
            options: Optional parsing and response options (returnResult, suggestTypes)
            transaction: Optional transaction object

        Returns:
            List of Record objects
        """
        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "payload": data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }
        response = self.client._make_request(
            "POST", "/api/v1/records/import/json", payload, headers
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
        """Attach records to a source record."""
        headers = Transaction._build_transaction_header(transaction)

        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {"targetIds": target_ids}
        if options:
            payload.update(typing.cast(typing.Dict[str, typing.Any], options))
        return self.client._make_request(
            "POST", f"/api/v1/records/{source_id}/relations", payload, headers
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
        """Detach records from a source record."""
        headers = Transaction._build_transaction_header(transaction)

        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {"targetIds": target_ids}
        if options:
            payload.update(typing.cast(typing.Dict[str, typing.Any], options))
        return self.client._make_request(
            "PUT", f"/api/v1/records/{source_id}/relations", payload, headers
        )

    def delete(
        self, query: SearchQuery, transaction: Optional[Transaction] = None
    ) -> Dict[str, str]:
        """Delete records matching the query."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "PUT",
            "/api/v1/records/delete",
            typing.cast(typing.Dict[str, typing.Any], query or {}),
            headers,
        )

    def delete_by_id(
        self,
        id_or_ids: Union[str, List[str]],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, str]:
        """Delete records by ID(s)."""
        headers = Transaction._build_transaction_header(transaction)

        if isinstance(id_or_ids, list):
            return self.client._make_request(
                "PUT",
                "/api/v1/records/delete",
                {"limit": 1000, "where": {"$id": {"$in": id_or_ids}}},
                headers,
            )
        return self.client._make_request(
            "DELETE", f"/api/v1/records/{id_or_ids}", None, headers
        )

    def find(
        self,
        query: Optional[SearchQuery] = None,
        record_id: Optional[str] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Record]:
        """Find records matching the query."""

        try:
            headers = Transaction._build_transaction_header(transaction)

            path = (
                f"/api/v1/records/{record_id}/search"
                if record_id
                else "/api/v1/records/search"
            )
            response = self.client._make_request(
                "POST",
                path,
                data=typing.cast(typing.Dict[str, typing.Any], query or {}),
                headers=headers,
            )
            return [Record(self.client, record) for record in response.get("data")]
        except Exception:
            return []

    def import_csv(
        self,
        label: str,
        csv_data: Union[str, bytes],
        options: Optional[Dict[str, bool]] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Dict[str, Any]]:
        """Import data from CSV."""
        headers = Transaction._build_transaction_header(transaction)

        payload = {
            "label": label,
            "payload": csv_data,
            "options": options or {"returnResult": True, "suggestTypes": True},
        }

        return self.client._make_request(
            "POST", "/api/v1/records/import/csv", payload, headers
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
        """Extract target IDs from various input types."""
        if isinstance(target, str):
            return [target]
        elif isinstance(target, list):
            return [t.get("__id", "") if isinstance(t, dict) else "" for t in target]
        elif isinstance(target, Record) and "__id" in target.data:
            return [target.data["__id"]]
        elif isinstance(target, dict) and "__id" in target:
            return [target["__id"]]
        raise ValueError("Invalid target format")
