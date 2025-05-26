import typing
from typing import List, Optional

from ..models.property import Property, PropertyValuesData
from ..models.search_query import OrderDirection, SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class PropertyValuesQuery(SearchQuery, total=False):
    """Extended SearchQuery for property values endpoint with text search support."""

    query: Optional[str]  # For text search among values
    orderBy: Optional[OrderDirection]  # Simplified to only asc/desc for values


class PropertiesAPI(BaseAPI):
    """API for managing properties in RushDB."""

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Property]:
        """List all properties."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/properties/search",
            typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers,
        )

    def find_by_id(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> Property:
        """Get a property by ID."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "GET", f"/properties/{property_id}", headers=headers
        )

    def delete(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> None:
        """Delete a property."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "DELETE", f"/properties/{property_id}", headers=headers
        )

    def values(
        self,
        property_id: str,
        search_query: Optional[PropertyValuesQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> PropertyValuesData:
        """Get values data for a property."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            f"/properties/{property_id}/values",
            typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers,
        )
