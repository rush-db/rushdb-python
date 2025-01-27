from typing import Dict, Any, Optional, Union, List

from src.rushdb import RushDBClient, RushDBError
from src.rushdb.transaction import Transaction
from src.rushdb.common import RelationOptions, RelationDetachOptions
from src.rushdb.record import Record


class RecordsAPI:
    """API for managing records in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def set(self, record_id: str, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Update a record by ID."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        return self.client._make_request('PUT', f'/api/v1/records/{record_id}', data, headers)

    def update(self, record_id: str, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Update a record by ID."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        return self.client._make_request('PATCH', f'/api/v1/records/{record_id}', data, headers)

    def create(self, label: str, data: Dict[str, Any], options: Optional[Dict[str, bool]] = None, transaction: Optional[Transaction] = None) -> Record:
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
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        payload = {
            "label": label,
            "payload": data,
            "options": options or {
                "returnResult": True,
                "suggestTypes": True
            }
        }
        response = self.client._make_request('POST', '/api/v1/records', payload, headers)
        return Record(self.client, response)

    def create_many(self, label: str, data: Union[Dict[str, Any], List[Dict[str, Any]]], options: Optional[Dict[str, bool]] = None, transaction: Optional[Transaction] = None) -> List[Record]:
        """Create multiple records.

        Args:
            label: Label for all records
            data: List or Dict of record data
            options: Optional parsing and response options (returnResult, suggestTypes)
            transaction: Optional transaction object

        Returns:
            List of Record objects
        """
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        payload = {
            "label": label,
            "payload": data,
            "options": options or {
                "returnResult": True,
                "suggestTypes": True
            }
        }
        response = self.client._make_request('POST', '/api/v1/records/import/json', payload, headers)

        print('r:', response)

        return [Record(self.client, {"data": record}) for record in response.get('data')]

    def attach(self, source: Union[str, Dict[str, Any]], target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]], options: Optional[RelationOptions] = None, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Attach records to a source record."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {'targetIds': target_ids}
        if options:
            payload.update(options)
            print(payload)
        return self.client._make_request('POST', f'/api/v1/records/{source_id}/relations', payload, headers)

    def detach(self, source: Union[str, Dict[str, Any]], target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]], options: Optional[RelationDetachOptions] = None, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Detach records from a source record."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {'targetIds': target_ids}
        if options:
            payload.update(options)
        return self.client._make_request('PUT', f'/api/v1/records/{source_id}/relations', payload, headers)

    def delete(self, query: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete records matching the query."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        return self.client._make_request('PUT', '/api/v1/records/delete', query, headers)

    def delete_by_id(self, id_or_ids: Union[str, List[str]], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete records by ID(s)."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        if isinstance(id_or_ids, list):
            return self.client._make_request('PUT', '/api/v1/records/delete', {
                'limit': 1000,
                'where': {'$id': {'$in': id_or_ids}}
            }, headers)
        return self.client._make_request('DELETE', f'/api/v1/records/{id_or_ids}', None, headers)

    def find(self, query: Optional[Dict[str, Any]] = None, record_id: Optional[str] = None, transaction: Optional[Transaction] = None) -> List[Record]:
        """Find records matching the query."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        path = f'/api/v1/records/{record_id}/search' if record_id else '/api/v1/records/search'
        response = self.client._make_request('POST', path, data=query, headers=headers)
        return [Record(self.client, record) for record in response]

    def find_by_id(self, id_or_ids: Union[str, List[str]], transaction: Optional[Transaction] = None) -> Union[Record, List[Record]]:
        """Find records by ID(s)."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        if isinstance(id_or_ids, list):
            response = self.client._make_request('POST', '/api/v1/records', {'ids': id_or_ids}, headers)
            return [Record(self.client, record) for record in response]
        response = self.client._make_request('GET', f'/api/v1/records/{id_or_ids}', None, headers)
        return Record(self.client, response)

    def find_one(self, query: Dict[str, Any], transaction: Optional[Transaction] = None) -> Optional[Record]:
        """Find a single record matching the query."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)
        query = {**query, 'limit': 1, 'skip': 0}
        result = self.client._make_request('POST', '/api/v1/records/search', query, headers)
        return Record(self.client, result[0]) if result else None

    def find_unique(self, query: Dict[str, Any], transaction: Optional[Transaction] = None) -> Record:
        """Find a unique record matching the query."""
        result = self.find_one(query, transaction)
        if not result:
            raise RushDBError("No records found matching the unique query")
        return result

    def import_csv(self, label: str, csv_data: Union[str, bytes], options: Optional[Dict[str, bool]] = None, transaction: Optional[Transaction] = None) -> List[Dict[str, Any]]:
        """Import data from CSV."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        payload = {
            "label": label,
            "payload": csv_data,
            "options": options or {
                "returnResult": True,
                "suggestTypes": True
            }
        }

        return self.client._make_request('POST','/api/v1/records/import/csv', payload, headers)

    @staticmethod
    def _extract_target_ids(target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]]) -> List[str]:
        """Extract target IDs from various input types."""
        if isinstance(target, str):
            return [target]
        elif isinstance(target, list):
            return [t['__id'] if isinstance(t, dict) and '__id' in t else t for t in target]
        elif isinstance(target, Record) and '__id' in target.data:
            return [target.data['__id']]
        elif isinstance(target, dict) and '__id' in target:
            return [target['__id']]
        raise ValueError("Invalid target format")
