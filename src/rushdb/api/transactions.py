from typing import Optional

from ..models.transaction import Transaction
from .base import BaseAPI


class TransactionsAPI(BaseAPI):
    """API for managing transactions in RushDB."""

    def begin(self, ttl: Optional[int] = None) -> Transaction:
        """Begin a new transaction.

        Returns:
            Transaction object
        """
        response = self.client._make_request("POST", "/api/v1/tx", {"ttl": ttl or 5000})
        return Transaction(self.client, response.get("data")["id"])

    def _commit(self, transaction_id: str) -> None:
        """Internal method to commit a transaction."""
        return self.client._make_request(
            "POST", f"/api/v1/tx/{transaction_id}/commit", {}
        )

    def _rollback(self, transaction_id: str) -> None:
        """Internal method to rollback a transaction."""
        return self.client._make_request(
            "POST", f"/api/v1/tx/{transaction_id}/rollback", {}
        )
