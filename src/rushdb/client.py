"""RushDB Python Client

This module provides the main client interface for interacting with RushDB,
a modern graph database. The client handles authentication, request management,
and provides access to all RushDB API endpoints through specialized API classes.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .api.ai import AIAPI
from .api.labels import LabelsAPI
from .api.properties import PropertiesAPI
from .api.query import QueryAPI
from .api.records import RecordsAPI
from .api.relationships import RelationsAPI
from .api.text_indexes import TextIndexesAPI
from .api.transactions import TransactionsAPI
from .common import RushDBError
from .direct import DirectEngine
from .direct import router as direct_router
from .utils.token_prefix import extract_mixed_properties_from_token


class _SettingsNamespace:
    """Project settings sub-namespace. Accessed via ``db.settings``."""

    def __init__(self, client: "RushDB"):
        self._client = client

    def get(self) -> Dict[str, Any]:
        """Retrieve the current project settings.

        Returns:
            Dict[str, Any]: Current project settings object.
        """
        response = self._client._make_request("GET", "/sdk/settings")
        return response.get("data", response)


class RushDB:
    """Main client for interacting with RushDB graph database.

    The RushDB client is the primary interface for connecting to and interacting
    with a RushDB instance. It provides access to all database operations through
    specialized API endpoints for records, properties, labels, relationships, and
    transactions.

    The client handles:
    - Authentication via API keys
    - HTTP request management and error handling
    - Connection pooling and URL management
    - Access to all RushDB API endpoints
    - JSON serialization/deserialization
    - Error handling and custom exceptions

    Attributes:
        DEFAULT_BASE_URL (str): Default RushDB API endpoint URL
        base_url (str): The configured base URL for API requests
        api_key (str): The API key used for authentication
        records (RecordsAPI): API interface for record operations
        properties (PropertiesAPI): API interface for property operations
        labels (LabelsAPI): API interface for label operations
        tx (TransactionsAPI): API interface for transaction operations
        settings (_SettingsNamespace): API interface for project settings

    Example:
        >>> from rushdb import RushDB
        >>>
        >>> # Initialize client with API key
        >>> client = RushDB(api_key="your_api_key_here")
        >>>
        >>> # A self-hosted RushDB engine (direct mode)
        >>> client = RushDB(
        ...     "engine_token_here",
        ...     direct=True,
        ...     engine_url="http://127.0.0.1:3000",
        ... )
        >>>
        >>> # Check connection
        >>> if client.ping():
        ...     print("Connected to RushDB successfully!")
        >>>
        >>> # Create a record
        >>> user = client.records.create("User", {"name": "John", "email": "john@example.com"})
        >>>
        >>> # Start a transaction
        >>> transaction = client.tx.begin()
        >>> try:
        ...     client.records.create("User", {"name": "Alice"}, transaction=transaction)
        ...     client.records.create("User", {"name": "Bob"}, transaction=transaction)
        ...     transaction.commit()
        >>> except Exception:
        ...     transaction.rollback()
    """

    DEFAULT_BASE_URL = "https://api.rushdb.com/api/v1"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        url: Optional[str] = None,
        direct: bool = False,
        engine_url: Optional[str] = None,
        engine_token: Optional[str] = None,
        scope: Optional[str] = None,
    ):
        """Initialize the RushDB client with authentication and connection settings.

        Sets up the client with the necessary authentication credentials and server
        configuration. Initializes all API endpoint interfaces for database operations.

        Args:
            api_key (str): The API key for authenticating with the RushDB server.
                This key should have appropriate permissions for the operations you
                plan to perform.
            base_url (Optional[str], optional): Deprecated alias of ``url``, kept
                for backwards compatibility.
            url (Optional[str], optional): Base URL of the RushDB Cloud API, to use
                an endpoint other than the default. A self-hosted engine is reached
                with ``direct=True`` and ``engine_url`` instead.
                When provided without an ``/api/`` component the path ``/api/v1`` is
                appended automatically.  Defaults to None, which uses
                ``DEFAULT_BASE_URL``.
            direct (bool, optional): When ``True``, talks to a standalone
                ``rushdb`` engine instead of RushDB Cloud. Every method is
                answered from the engine; the methods in
                ``rushdb.CLOUD_ONLY_METHODS`` raise ``CloudOnlyError`` before
                sending anything, and no request ever goes to RushDB Cloud. The
                protocol transport is ``client.engine``.
            engine_url (Optional[str], optional): Standalone engine base URL (e.g.
                ``"http://127.0.0.1:3000"``). Required when ``direct=True``.
            engine_token (Optional[str], optional): The engine boot token. Defaults
                to ``api_key`` when not provided.
            scope (Optional[str], optional): Tenant scope sent to the engine in
                multitenant mode.

        Raises:
            ValueError: If api_key is empty or None, or ``direct=True`` without
                ``engine_url``.

        Example:
            >>> # Using default public API
            >>> client = RushDB(api_key="your_api_key")
            >>>
            >>> # Direct mode against a standalone engine
            >>> client = RushDB(
            ...     api_key="local-token",
            ...     direct=True,
            ...     engine_url="http://127.0.0.1:3000",
            ... )
        """
        settings, raw_key = extract_mixed_properties_from_token(api_key)

        self.server_settings = (
            {"selfHosted": settings["selfHosted"], "plan_type": settings["planType"]}
            if settings
            else None
        )
        effective_url = url or base_url or self.DEFAULT_BASE_URL
        # Both `url` and its deprecated alias `base_url` are documented to get
        # `/api/v1` appended when the path is absent.
        if (url or base_url) and "/api/" not in effective_url:
            effective_url = effective_url.rstrip("/") + "/api/v1"
        self.base_url = effective_url.rstrip("/")
        self.api_key = api_key
        self.direct = direct
        self.engine: Optional[DirectEngine] = None
        if direct:
            if not engine_url:
                raise ValueError("engine_url is required when direct=True")
            self.engine = DirectEngine(
                engine_url=engine_url,
                token=engine_token or api_key,
                scope=scope,
            )
        self.records = RecordsAPI(self)
        self.properties = PropertiesAPI(self)
        self.labels = LabelsAPI(self)
        self.tx = TransactionsAPI(self)
        self.query = QueryAPI(self)
        self.relationships = RelationsAPI(self)
        self.ai = AIAPI(self)
        self.text_indexes = TextIndexesAPI(self)
        self.settings = _SettingsNamespace(self)

    def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an authenticated HTTP request to the RushDB server.

        This is the core method that handles all HTTP communication with the RushDB
        server. It manages URL construction, authentication headers, request encoding,
        response parsing, and error handling.

        Args:
            method (str): HTTP method to use for the request (GET, POST, PUT, DELETE, PATCH).
            path (str): API endpoint path relative to the base URL. Can start with or
                without a leading slash.
            data (Optional[Dict], optional): Request body data to be JSON-encoded.
                Will be serialized to JSON and sent as the request body. Defaults to None.
            headers (Optional[Dict[str, str]], optional): Additional HTTP headers to include
                in the request. These will be merged with default headers (authentication,
                content-type). Defaults to None.
            params (Optional[Dict[str, Any]], optional): URL query parameters to append
                to the request URL. Will be properly URL-encoded. Defaults to None.

        Returns:
            Any: The parsed JSON response from the server. The exact structure depends
                on the specific API endpoint called.

        Raises:
            RushDBError: If the server returns an HTTP error status, connection fails,
                or the response cannot be parsed as JSON. The exception includes details
                about the specific error that occurred.

        Note:
            This is an internal method used by the API classes. You typically won't
            need to call this directly - use the methods on the API classes instead.

        Example:
            >>> # This is typically called internally by API methods
            >>> response = client._make_request("GET", "/records/search", data={"limit": 10})
            >>>
            >>> # With query parameters
            >>> response = client._make_request(
            ...     "GET",
            ...     "/properties",
            ...     params={"limit": 50, "skip": 0}
            ... )
        """
        if self.engine is not None:
            return direct_router.handle(
                self.engine, method, path, data, headers, params
            )

        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path

        # Clean and encode path components
        path = path.strip()
        path_parts = [
            urllib.parse.quote(part, safe="") for part in path.split("/") if part
        ]
        clean_path = "/" + "/".join(path_parts)

        # Build URL with query parameters
        url = f"{self.base_url}{clean_path}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        # Prepare headers
        request_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **(headers or {}),
        }

        try:
            # Prepare request body
            body = None
            if data is not None:
                body = json.dumps(data).encode("utf-8")

            # Create and send request
            request = urllib.request.Request(
                url, data=body, headers=request_headers, method=method
            )

            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Error bodies are usually JSON, but a gateway/proxy may return HTML or an
            # empty body — without this guard the JSONDecodeError raised here would
            # escape as-is instead of surfacing as a RushDBError.
            try:
                error_body = json.loads(e.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                error_body = {}
            message = error_body.get("message")
            if isinstance(message, list):
                message = "; ".join(str(item) for item in message)
            raise RushDBError(message or f"HTTP {e.code}", error_body, status=e.code)
        except urllib.error.URLError as e:
            raise RushDBError(f"Connection error: {str(e)}")
        except json.JSONDecodeError as e:
            raise RushDBError(f"Invalid JSON response: {str(e)}")

    def ping(self) -> bool:
        """Test connectivity to the RushDB server.

        Performs a simple health check request to verify that the RushDB server
        is reachable and responding. This is useful for testing connections,
        validating configuration, or implementing health monitoring.

        Returns:
            bool: True if the server is reachable and responds successfully,
                False if there are any connection issues, authentication problems,
                or server errors.

        Note:
            This method catches all RushDBError exceptions and returns False,
            making it safe for use in conditional checks without needing
            explicit exception handling.

        Example:
            >>> client = RushDB(api_key="your_api_key")
            >>>
            >>> # Check if server is available
            >>> if client.ping():
            ...     print("RushDB server is online and accessible")
            ...     # Proceed with database operations
            ... else:
            ...     print("Cannot connect to RushDB server")
            ...     # Handle connection failure
            >>>
            >>> # Use in application startup
            >>> def initialize_database():
            ...     client = RushDB(api_key=os.getenv("RUSHDB_API_KEY"))
            ...     if not client.ping():
            ...         raise RuntimeError("Database connection failed")
            ...     return client
        """
        try:
            if self.engine is not None:
                self.engine.execute(
                    {"kind": "describe", "describe": {"kind": "buildInfo"}}
                )
            else:
                self._make_request("GET", "/sdk/settings")
            return True
        except RushDBError:
            return False
