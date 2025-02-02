import typing
from typing import List, Literal, Optional

from ..models.property import Property, PropertyValuesData
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class PropertiesAPI(BaseAPI):
    """API for managing properties in RushDB."""

    def find(
        self,
        query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Property]:
        """List all properties."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/api/v1/properties",
            typing.cast(typing.Dict[str, typing.Any], query or {}),
            headers,
        )

    def find_by_id(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> Property:
        """Get a property by ID."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "GET", f"/api/v1/properties/{property_id}", headers=headers
        )

    def delete(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> None:
        """Delete a property."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "DELETE", f"/api/v1/properties/{property_id}", headers=headers
        )

    def values(
        self,
        property_id: str,
        sort: Optional[Literal["asc", "desc"]],
        skip: Optional[int],
        limit: Optional[int],
        transaction: Optional[Transaction] = None,
    ) -> PropertyValuesData:
        """Get values data for a property."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "GET",
            f"/api/v1/properties/{property_id}/values",
            headers=headers,
            params={"sort": sort, "skip": skip, "limit": limit},
        )
