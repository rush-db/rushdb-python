from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .relationship import RelationshipDetachOptions, RelationshipOptions
from .transaction import Transaction

if TYPE_CHECKING:
    from ..client import RushDB


class Record:
    """Represents a record in RushDB with methods for manipulation."""

    def __init__(self, client: "RushDB", data: Union[Dict[str, Any], None] = None):
        self._client = client
        # Handle different data formats
        if isinstance(data, dict):
            self.data = data
        elif isinstance(data, str):
            # If just a string is passed, assume it's an ID
            self.data = {}
        else:
            raise ValueError(f"Invalid data format for Record: {type(data)}")

    @property
    def id(self) -> str:
        """Get record ID."""
        record_id = self.data.get("__id")
        if record_id is None:
            raise ValueError("Record ID is missing or None")

        return record_id

    @property
    def proptypes(self) -> str:
        """Get record ID."""
        return self.data["__proptypes"]

    @property
    def label(self) -> str:
        """Get record ID."""
        return self.data["__label"]

    @property
    def timestamp(self) -> int:
        """Get record timestamp from ID."""
        record_id = self.data.get("__id")
        if record_id is None:
            raise ValueError("Record ID is missing or None")

        parts = record_id.split("-")
        high_bits_hex = parts[0] + parts[1][:4]
        return int(high_bits_hex, 16)

    @property
    def date(self) -> datetime:
        """Get record creation date from ID."""
        return datetime.fromtimestamp(self.timestamp / 1000)

    def set(
        self, data: Dict[str, Any], transaction: Optional[Transaction] = None
    ) -> Dict[str, str]:
        """Set record data through API request."""
        return self._client.records.set(self.id, data, transaction)

    def update(
        self, data: Dict[str, Any], transaction: Optional[Transaction] = None
    ) -> Dict[str, str]:
        """Update record data through API request."""
        return self._client.records.update(self.id, data, transaction)

    def attach(
        self,
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
        """Attach other records to this record."""
        return self._client.records.attach(self.id, target, options, transaction)

    def detach(
        self,
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
        """Detach records from this record."""
        return self._client.records.detach(self.id, target, options, transaction)

    def delete(self, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete this record."""
        return self._client.records.delete_by_id(self.id, transaction)

    def __repr__(self) -> str:
        """String representation of record."""
        return f"Record(id='{self.id}')"
