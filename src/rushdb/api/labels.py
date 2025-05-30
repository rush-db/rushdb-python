import typing
from typing import List, Optional

from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class LabelsAPI(BaseAPI):
    """API for managing labels in RushDB."""

    def list(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[str]:
        """List all labels."""
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/labels/search",
            data=typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers=headers,
        )
