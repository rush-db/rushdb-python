from typing import TYPE_CHECKING, Dict, Optional, Union

from ..common import RushDBError

if TYPE_CHECKING:
    from ..client import RushDB


class Transaction:
    """Represents a RushDB transaction."""

    def __init__(self, client: "RushDB", transaction_id: str):
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

    @staticmethod
    def _build_transaction_header(
        transaction: Optional[Union[str, "Transaction"]] = None,
    ) -> Optional[Dict[str, str]]:
        """Build transaction header if transaction_id is provided."""
        transaction_id = None

        if isinstance(transaction, Transaction):
            transaction_id = transaction.id
        else:
            transaction_id = transaction

        return {"X-Transaction-Id": transaction_id} if transaction_id else None

    def __enter__(self) -> "Transaction":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if not self._rolled_back:
                self.rollback()
        elif not self._committed and not self._rolled_back:
            self.commit()
