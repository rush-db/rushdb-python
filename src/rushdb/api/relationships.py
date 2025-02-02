import typing
from typing import List, Optional, TypedDict, Union
from urllib.parse import urlencode

from ..models.relationship import Relationship
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class PaginationParams(TypedDict, total=False):
    """TypedDict for pagination parameters."""

    limit: int
    skip: int


class RelationsAPI(BaseAPI):
    """API for managing relationships in RushDB."""

    async def find(
        self,
        query: Optional[SearchQuery] = None,
        pagination: Optional[PaginationParams] = None,
        transaction: Optional[Union[Transaction, str]] = None,
    ) -> List[Relationship]:
        """Find relations matching the search parameters.

        Args:
            query: Search query parameters
            pagination: Optional pagination parameters (limit and skip)
            transaction: Optional transaction context or transaction ID

        Returns:
            List of matching relations
        """
        # Build query string for pagination
        query_params = {}
        if pagination:
            if pagination.get("limit") is not None:
                query_params["limit"] = str(pagination["limit"])
            if pagination.get("skip") is not None:
                query_params["skip"] = str(pagination["skip"])

        # Construct path with query string
        query_string = f"?{urlencode(query_params)}" if query_params else ""
        path = f"/records/relations/search{query_string}"

        # Build headers with transaction if present
        headers = Transaction._build_transaction_header(transaction)

        # Make request
        response = self.client._make_request(
            method="POST",
            path=path,
            data=typing.cast(typing.Dict[str, typing.Any], query or {}),
            headers=headers,
        )

        return response.data
