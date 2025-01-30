from typing import List, Optional

from .base import BaseAPI
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction


class LabelsAPI(BaseAPI):
    """API for managing labels in RushDB."""
    def list(self, query: Optional[SearchQuery] = None, transaction: Optional[Transaction] = None) -> List[str]:
        """List all labels."""
        headers = Transaction._build_transaction_header(transaction.id if transaction else None)

        return self.client._make_request('POST', '/api/v1/labels', data=query or {}, headers=headers)