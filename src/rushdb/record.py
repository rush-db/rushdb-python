from datetime import datetime
from typing import Dict, Any, Optional, Union, List

from src.rushdb import RushDBClient
from src.rushdb.common import RelationOptions, RelationDetachOptions
from src.rushdb.transaction import Transaction


class Record:
    """Represents a record in RushDB with methods for manipulation."""
    def __init__(self, client: 'RushDBClient', data: Dict[str, Any] = None):
        self._client = client

        self.data = data.get('data')

    @property
    def id(self) -> str:
        """Get record ID."""
        return self.data['__id']

    @property
    def timestamp(self) -> int:
        """Get record timestamp from ID."""
        parts = self.data.get('__id').split('-')
        high_bits_hex = parts[0] + parts[1][:4]
        return int(high_bits_hex, 16)

    @property
    def date(self) -> datetime:
        """Get record creation date from ID."""
        return datetime.fromtimestamp(self.timestamp / 1000)

    def set(self, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Set record data through API request."""
        return self._client.records.set(self.id, data, transaction)

    def update(self, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Update record data through API request."""
        return self._client.records.update(self.id, data, transaction)

    def attach(self, target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], 'Record', List['Record']], options: Optional[RelationOptions] = None, transaction: Optional[
        Transaction] = None) -> Dict[str, str]:
        """Attach other records to this record."""
        return self._client.records.attach(self.id, target, options, transaction)

    def detach(self, target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], 'Record', List['Record']], options: Optional[RelationDetachOptions] = None, transaction: Optional[
        Transaction] = None) -> Dict[str, str]:
        """Detach records from this record."""
        return self._client.records.detach(self.id, target, options, transaction)

    def delete(self, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete this record."""
        return self._client.records.delete_by_id(self.id, transaction)

    def __repr__(self) -> str:
        """String representation of record."""
        return f"Record(id='{self.id}')"
