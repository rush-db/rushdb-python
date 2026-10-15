from typing import Any, Dict, Optional

from ..models.transaction import Transaction
from .base import BaseAPI


class QueryAPI(BaseAPI):
    """API client for executing raw openCypher queries.

    Works on RushDB Cloud and on a self-hosted RushDB engine in direct mode
    (the engine must be started with ``--languages cypher``).

    Example:
        >>> from rushdb import RushDB
        >>> db = RushDB("RUSHDB_API_KEY")
        >>> result = db.query.raw({
        ...     "query": "MATCH (n:Person) RETURN n LIMIT $limit",
        ...     "params": {"limit": 10}
        ... })
        >>> print(result)
    """

    def raw(
        self,
        body: Dict[str, Any],
        transaction: Optional[Transaction] = None,
    ) -> Dict[str, Any]:
        """Execute a raw Cypher query.

        Args:
            body (Dict[str, Any]): Payload containing:
                - query (str): Cypher query string
                - params (Optional[Dict[str, Any]]): Parameter dict
            transaction (Optional[Transaction]): Optional transaction context.

        Returns:
            Dict[str, Any]: API response including raw driver result in 'data'.
        """
        headers = Transaction._build_transaction_header(transaction)
        return self.client._make_request("POST", "/query/raw", body, headers)
