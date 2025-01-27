from typing import List, Dict, Any, Optional

from src.rushdb import RushDBClient
from src.rushdb.property import Property, PropertyValuesData
from src.rushdb.transaction import Transaction


class PropertiesAPI:
    """API for managing properties in RushDB."""
    def __init__(self, client: 'RushDBClient'):
        self.client = client

    def list(self, transaction: Optional[Transaction] = None) -> List[Property]:
        """List all properties."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('GET', '/api/v1/properties', headers=headers)

    def create(self, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Property:
        """Create a new property."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('POST', '/api/v1/properties', data, headers)

    def get(self, property_id: str, transaction: Optional[Transaction] = None) -> Property:
        """Get a property by ID."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('GET', f'/api/v1/properties/{property_id}', headers=headers)

    def update(self, property_id: str, data: Dict[str, Any], transaction: Optional[Transaction] = None) -> Property:
        """Update a property."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('PUT', f'/api/v1/properties/{property_id}', data, headers)

    def delete(self, property_id: str, transaction: Optional[Transaction] = None) -> None:
        """Delete a property."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('DELETE', f'/api/v1/properties/{property_id}', headers=headers)

    def get_values(self, property_id: str, transaction: Optional[Transaction] = None) -> PropertyValuesData:
        """Get values data for a property."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('GET', f'/api/v1/properties/{property_id}/values', headers=headers)
