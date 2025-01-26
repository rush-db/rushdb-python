"""RushDB Client"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional, Union, TypedDict, Literal
from datetime import datetime

# Relation types
RelationDirection = Literal['in', 'out']

class RelationOptions(TypedDict, total=False):
    """Options for creating relations."""
    direction: Optional[RelationDirection]
    type: Optional[str]

class RelationDetachOptions(TypedDict, total=False):
    """Options for detaching relations."""
    direction: Optional[RelationDirection]
    typeOrTypes: Optional[Union[str, List[str]]]

# Value types
class DatetimeObject(TypedDict, total=False):
    """Datetime object structure"""
    year: int
    month: Optional[int]
    day: Optional[int]
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]
    millisecond: Optional[int]
    microsecond: Optional[int]
    nanosecond: Optional[int]

DatetimeValue = Union[DatetimeObject, str]
BooleanValue = bool
NullValue = None
NumberValue = float
StringValue = str

# Property types
PROPERTY_TYPE_BOOLEAN = 'boolean'
PROPERTY_TYPE_DATETIME = 'datetime'
PROPERTY_TYPE_NULL = 'null'
PROPERTY_TYPE_NUMBER = 'number'
PROPERTY_TYPE_STRING = 'string'

PropertyType = Literal[
    PROPERTY_TYPE_BOOLEAN,
    PROPERTY_TYPE_DATETIME,
    PROPERTY_TYPE_NULL,
    PROPERTY_TYPE_NUMBER,
    PROPERTY_TYPE_STRING
]

class Property(TypedDict):
    """Base property structure"""
    id: str
    name: str
    type: PropertyType
    metadata: Optional[str]

class PropertyWithValue(Property):
    """Property with a value"""
    value: Union[DatetimeValue, BooleanValue, NullValue, NumberValue, StringValue]

class PropertyValuesData(TypedDict, total=False):
    """Property values data structure"""
    max: Optional[float]
    min: Optional[float]
    values: List[Any]

class RushDBError(Exception):
    """Custom exception for RushDB client errors."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}

class Transaction:
    """Represents a RushDB transaction."""
    def __init__(self, client: 'RushDBClient', transaction_id: str):
        self.client = client
        self.id = transaction_id
        self._committed = False
        self._rolled_back = False

    def commit(self) -> None:
        """Commit the transaction."""
        if self._committed or self._rolled_back:
            raise RushDBError("Transaction already completed")
        self.client.transactions._commit(self.id)
        self._committed = True

    def rollback(self) -> None:
        """Rollback the transaction."""
        if self._committed or self._rolled_back:
            raise RushDBError("Transaction already completed")
        self.client.transactions._rollback(self.id)
        self._rolled_back = True

    def __enter__(self) -> 'Transaction':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if not self._rolled_back:
                self.rollback()
        elif not self._committed and not self._rolled_back:
            self.commit()

class TransactionsAPI:
    """API for managing transactions in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def begin(self, ttl: Optional[int] = None) -> Transaction:
        """Begin a new transaction.

        Returns:
            Transaction object
        """
        response = self.client._make_request('POST', '/api/v1/tx', { "ttl": ttl or 5000 })
        return Transaction(self.client, response.get('data')['id'])

    def _commit(self, transaction_id: str) -> None:
        """Internal method to commit a transaction."""
        return self.client._make_request('POST', f'/api/v1/tx/{transaction_id}/commit', {})

    def _rollback(self, transaction_id: str) -> None:
        """Internal method to rollback a transaction."""
        return self.client._make_request('POST', f'/api/v1/tx/{transaction_id}/rollback', {})

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

    def attach(self, target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]], options: Optional[RelationOptions] = None, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Attach other records to this record."""
        return self._client.records.attach(self.id, target, options, transaction)

    def detach(self, target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]], options: Optional[RelationDetachOptions] = None, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Detach records from this record."""
        return self._client.records.detach(self.id, target, options, transaction)

    def delete(self, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete this record."""
        return self._client.records.delete_by_id(self.id, transaction)

    def __repr__(self) -> str:
        """String representation of record."""
        return f"Record(id='{self.id}')"

class RecordsAPI:
    """API for managing records in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def set(self, record_id: str, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Update a record by ID."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        return self.client._make_request('PUT', f'/api/v1/records/{record_id}', data, headers)

    def update(self, record_id: str, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Update a record by ID."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
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
        headers = self._build_transaction_header(transaction.id if transaction else None)

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
        headers = self._build_transaction_header(transaction.id if transaction else None)

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
        headers = self._build_transaction_header(transaction.id if transaction else None)
        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {'targetIds': target_ids}
        if options:
            payload.update(options)
            print(payload)
        return self.client._make_request('POST', f'/api/v1/records/{source_id}/relations', payload, headers)

    def detach(self, source: Union[str, Dict[str, Any]], target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]]], options: Optional[RelationDetachOptions] = None, transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Detach records from a source record."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        source_id = self._extract_target_ids(source)[0]
        target_ids = self._extract_target_ids(target)
        payload = {'targetIds': target_ids}
        if options:
            payload.update(options)
        return self.client._make_request('PUT', f'/api/v1/records/{source_id}/relations', payload, headers)

    def delete(self, query: Dict[str, Any], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete records matching the query."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        return self.client._make_request('PUT', '/api/v1/records/delete', query, headers)

    def delete_by_id(self, id_or_ids: Union[str, List[str]], transaction: Optional[Transaction] = None) -> Dict[str, str]:
        """Delete records by ID(s)."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        if isinstance(id_or_ids, list):
            return self.client._make_request('PUT', '/api/v1/records/delete', {
                'limit': 1000,
                'where': {'$id': {'$in': id_or_ids}}
            }, headers)
        return self.client._make_request('DELETE', f'/api/v1/records/{id_or_ids}', None, headers)

    def find(self, query: Optional[Dict[str, Any]] = None, record_id: Optional[str] = None, transaction: Optional[Transaction] = None) -> List[Record]:
        """Find records matching the query."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        path = f'/api/v1/records/{record_id}/search' if record_id else '/api/v1/records/search'
        response = self.client._make_request('POST', path, data=query, headers=headers)
        return [Record(self.client, record) for record in response]

    def find_by_id(self, id_or_ids: Union[str, List[str]], transaction: Optional[Transaction] = None) -> Union[Record, List[Record]]:
        """Find records by ID(s)."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
        if isinstance(id_or_ids, list):
            response = self.client._make_request('POST', '/api/v1/records', {'ids': id_or_ids}, headers)
            return [Record(self.client, record) for record in response]
        response = self.client._make_request('GET', f'/api/v1/records/{id_or_ids}', None, headers)
        return Record(self.client, response)

    def find_one(self, query: Dict[str, Any], transaction: Optional[Transaction] = None) -> Optional[Record]:
        """Find a single record matching the query."""
        headers = self._build_transaction_header(transaction.id if transaction else None)
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
        headers = self._build_transaction_header(transaction.id if transaction else None)

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
    def _build_transaction_header(transaction_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Build transaction header if transaction_id is provided."""
        return {'X-Transaction-Id': transaction_id} if transaction_id else None

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

class PropertyAPI:
    """API for managing properties in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def list(self) -> List[Property]:
        """List all properties."""
        return self.client._make_request('GET', '/api/v1/properties')

    def create(self, data: Dict[str, Any]) -> Property:
        """Create a new property."""
        return self.client._make_request('POST', '/api/v1/properties', data)

    def get(self, property_id: str) -> Property:
        """Get a property by ID."""
        return self.client._make_request('GET', f'/api/v1/properties/{property_id}')

    def update(self, property_id: str, data: Dict[str, Any]) -> Property:
        """Update a property."""
        return self.client._make_request('PUT', f'/api/v1/properties/{property_id}', data)

    def delete(self, property_id: str) -> None:
        """Delete a property."""
        return self.client._make_request('DELETE', f'/api/v1/properties/{property_id}')

    def get_values(self, property_id: str) -> PropertyValuesData:
        """Get values data for a property."""
        return self.client._make_request('GET', f'/api/v1/properties/{property_id}/values')

class LabelsAPI:
    """API for managing labels in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def list(self) -> List[str]:
        """List all labels."""
        return self.client._make_request('GET', '/api/v1/labels')

    def create(self, label: str) -> None:
        """Create a new label."""
        return self.client._make_request('POST', '/api/v1/labels', {'name': label})

    def delete(self, label: str) -> None:
        """Delete a label."""
        return self.client._make_request('DELETE', f'/api/v1/labels/{label}')

class RushDBClient:
    """Main client for interacting with RushDB."""
    DEFAULT_BASE_URL = "https://api.rushdb.com"

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize the RushDB client.

        Args:
            api_key: The API key for authentication
            base_url: Optional base URL for the RushDB server (default: https://api.rushdb.com)
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.api_key = api_key
        self.records = RecordsAPI(self)
        self.properties = PropertyAPI(self)
        self.labels = LabelsAPI(self)
        self.transactions = TransactionsAPI(self)

    def _make_request(self, method: str, path: str, data: Optional[Dict] = None, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make an HTTP request to the RushDB server.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            data: Request body data
            headers: Optional request headers
            params: Optional URL query parameters

        Returns:
            The parsed JSON response
        """
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path

        # Clean and encode path components
        path = path.strip()
        path_parts = [urllib.parse.quote(part, safe='') for part in path.split('/') if part]
        clean_path = '/' + '/'.join(path_parts)

        # Build URL with query parameters
        url = f"{self.base_url}{clean_path}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        # Prepare headers
        request_headers = {
            'token': self.api_key,
            'Content-Type': 'application/json',
            **(headers or {})
        }

        try:
            # Prepare request body
            body = None
            if data is not None:
                body = json.dumps(data).encode('utf-8')

            # Create and send request
            request = urllib.request.Request(
                url,
                data=body,
                headers=request_headers,
                method=method
            )

            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = json.loads(e.read().decode('utf-8'))
            raise RushDBError(error_body.get('message', str(e)), error_body)
        except urllib.error.URLError as e:
            raise RushDBError(f"Connection error: {str(e)}")
        except json.JSONDecodeError as e:
            raise RushDBError(f"Invalid JSON response: {str(e)}")

    def ping(self) -> bool:
        """Check if the server is reachable."""
        try:
            self._make_request('GET', '/')
            return True
        except RushDBError:
            return False