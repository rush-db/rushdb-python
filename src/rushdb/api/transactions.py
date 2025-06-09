from typing import Optional

from ..models.transaction import Transaction
from .base import BaseAPI


class TransactionsAPI(BaseAPI):
    """API client for managing database transactions in RushDB.

    The TransactionsAPI provides functionality for creating and managing database
    transactions, which allow multiple operations to be grouped together and
    executed atomically. Transactions ensure data consistency and provide
    rollback capabilities if operations fail.

    This class handles:
    - Transaction creation and initialization
    - Transaction commitment (making changes permanent)
    - Transaction rollback (undoing changes)
    - Transaction lifecycle management

    Transactions are essential for maintaining data integrity when performing
    multiple related operations that should succeed or fail together.

    Attributes:
        client: The underlying RushDB client instance for making HTTP requests.

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> tx_api = client.transactions
        >>>
        >>> # Begin a new transaction
        >>> transaction = tx_api.begin(ttl=10000)  # 10 second TTL
        >>>
        >>> # Use transaction with other API calls
        >>> try:
        ...     client.records.create("User", {"name": "John"}, transaction=transaction)
        ...     client.records.create("User", {"name": "Jane"}, transaction=transaction)
        ...     transaction.commit()  # Makes changes permanent
        >>> except Exception:
        ...     transaction.rollback()  # Undoes all changes
    """

    def begin(self, ttl: Optional[int] = None) -> Transaction:
        """Begin a new database transaction.

        Creates a new transaction that can be used to group multiple database
        operations together. The transaction will have a time-to-live (TTL)
        after which it will automatically expire if not committed or rolled back.

        Args:
            ttl (Optional[int], optional): Time-to-live in milliseconds for the transaction.
                After this time, the transaction will automatically expire and be rolled back.
                If None, defaults to 5000ms (5 seconds). Defaults to None.

        Returns:
            Transaction: A Transaction object that can be used with other API operations.
                The transaction provides commit() and rollback() methods for controlling
                the transaction lifecycle.

        Raises:
            RequestError: If the server request fails or transaction creation is denied.

        Example:
            >>> tx_api = TransactionsAPI(client)
            >>>
            >>> # Begin transaction with default TTL (5 seconds)
            >>> transaction = tx_api.begin()
            >>>
            >>> # Begin transaction with custom TTL (30 seconds)
            >>> long_transaction = tx_api.begin(ttl=30000)
            >>>
            >>> # Use the transaction with other operations
            >>> try:
            ...     client.records.create("User", {"name": "Alice"}, transaction=transaction)
            ...     transaction.commit()
            >>> except Exception:
            ...     transaction.rollback()
        """
        response = self.client._make_request("POST", "/tx", {"ttl": ttl or 5000})
        return Transaction(self.client, response.get("data")["id"])

    def _commit(self, transaction_id: str) -> None:
        """Internal method to commit a transaction.

        Commits the specified transaction, making all operations performed within
        the transaction permanent. This is an internal method that should not be
        called directly - use the commit() method on the Transaction object instead.

        Args:
            transaction_id (str): The unique identifier of the transaction to commit.

        Returns:
            None: This method does not return a value.

        Raises:
            ValueError: If the transaction_id is invalid or empty.
            NotFoundError: If no transaction exists with the specified ID.
            RequestError: If the server request fails or the transaction cannot be committed.

        Note:
            This is an internal method. Use transaction.commit() instead of calling this directly.
        """
        return self.client._make_request("POST", f"/tx/{transaction_id}/commit", {})

    def _rollback(self, transaction_id: str) -> None:
        """Internal method to rollback a transaction.

        Rolls back the specified transaction, undoing all operations performed within
        the transaction and restoring the database to its state before the transaction
        began. This is an internal method that should not be called directly - use the
        rollback() method on the Transaction object instead.

        Args:
            transaction_id (str): The unique identifier of the transaction to rollback.

        Returns:
            None: This method does not return a value.

        Raises:
            ValueError: If the transaction_id is invalid or empty.
            NotFoundError: If no transaction exists with the specified ID.
            RequestError: If the server request fails or the transaction cannot be rolled back.

        Note:
            This is an internal method. Use transaction.rollback() instead of calling this directly.
        """
        return self.client._make_request("POST", f"/tx/{transaction_id}/rollback", {})
