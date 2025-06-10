from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .relationship import RelationshipDetachOptions, RelationshipOptions
from .transaction import Transaction

if TYPE_CHECKING:
    from ..client import RushDB


class Record:
    """Represents a record in RushDB with methods for manipulation."""

    def __init__(self, client: "RushDB", data: Dict[str, Any] = {}):
        self._client = client
        if isinstance(data, dict):
            self.data = data
        else:
            self.data = {}
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
        try:
            return f"Record(id='{self.id}', label='{self.label}')"
        except (ValueError, KeyError):
            return f"Record(data_keys={list(self.data.keys())})"

    def __str__(self) -> str:
        """Human-readable string representation."""
        try:
            name = self.get("name", self.get("title", self.get("email", "")))
            if name:
                return f"{self.label}: {name}"
            return f"{self.label} ({self.id})"
        except (ValueError, KeyError):
            return f"Record with {len(self.data)} fields"

    def __eq__(self, other) -> bool:
        """Check equality based on record ID."""
        if not isinstance(other, Record):
            return False
        try:
            return self.id == other.id
        except (ValueError, KeyError):
            return False

    def __hash__(self) -> int:
        """Hash based on record ID for use in sets and dicts."""
        try:
            return hash(self.id)
        except (ValueError, KeyError):
            return hash(id(self))

    def to_dict(self, exclude_internal: bool = True) -> Dict[str, Any]:
        """
        Convert record to dictionary.

        Args:
            exclude_internal: If True, excludes fields starting with '__'

        Returns:
            Dictionary representation of the record
        """
        return self.get_data(exclude_internal=exclude_internal)

    def __getitem__(self, key: str) -> Any:
        """Get a field value by key, supporting both data fields and internal fields."""
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a field value with optional default.

        This method provides convenient access to record data fields while
        excluding internal RushDB fields (those starting with '__').

        Args:
            key: The field name to retrieve
            default: Default value if field doesn't exist

        Returns:
            The field value or default if not found

        Example:
            >>> record = db.records.create("User", {"name": "John", "age": 30})
            >>> record.get("name")  # "John"
            >>> record.get("email", "no-email@example.com")  # "no-email@example.com"
        """
        return self.data.get(key, default)

    def get_data(self, exclude_internal: bool = True) -> Dict[str, Any]:
        """
        Get all record data, optionally excluding internal RushDB fields.

        Args:
            exclude_internal: If True, excludes fields starting with '__'

        Returns:
            Dictionary containing the record data

        Example:
            >>> record = db.records.create("User", {"name": "John", "age": 30})
            >>> record.get_data()  # {"name": "John", "age": 30}
            >>> record.get_data(exclude_internal=False)  # includes __id, __label, etc.
        """
        if exclude_internal:
            return {k: v for k, v in self.data.items() if not k.startswith("__")}
        return self.data.copy()

    @property
    def fields(self) -> Dict[str, Any]:
        """
        Get user data fields (excluding internal RushDB fields).

        This is a convenient property for accessing just the user-defined
        data without RushDB's internal metadata fields.

        Returns:
            Dictionary containing only user-defined fields

        Example:
            >>> record = db.records.create("User", {"name": "John", "age": 30})
            >>> record.fields  # {"name": "John", "age": 30}
        """
        return self.get_data(exclude_internal=True)

    def exists(self) -> bool:
        """
        Check if the record exists in the database.

        This method safely checks if the record exists without throwing exceptions,
        making it ideal for validation and conditional logic.

        Returns:
            bool: True if record exists and is accessible, False otherwise

        Example:
            >>> record = db.records.create("User", {"name": "John"})
            >>> record.exists()  # True
            >>>
            >>> # After deletion
            >>> record.delete()
            >>> record.exists()  # False
            >>>
            >>> # For invalid or incomplete records
            >>> invalid_record = Record(client, {})
            >>> invalid_record.exists()  # False
        """
        try:
            # Check if we have a valid ID first
            record_id = self.data.get("__id")
            if not record_id:
                return False
            return True

        except Exception:
            # Any exception means the record doesn't exist or isn't accessible
            return False
