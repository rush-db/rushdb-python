"""RushDB Client"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .api.labels import LabelsAPI
from .api.properties import PropertiesAPI
from .api.records import RecordsAPI
from .api.transactions import TransactionsAPI
from .common import RushDBError


class RushDB:
    """Main client for interacting with RushDB."""

    DEFAULT_BASE_URL = "https://api.rushdb.com"

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize the RushDB client.

        Args:
            api_key: The API key for authentication
            base_url: Optional base URL for the RushDB server (default: https://api.rushdb.com)
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self.records = RecordsAPI(self)
        self.properties = PropertiesAPI(self)
        self.labels = LabelsAPI(self)
        self.transactions = TransactionsAPI(self)

    def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request to the RushDB server.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path
            data: Request body data
            headers: Optional request headers
            params: Optional URL query parameters

        Returns:
            The parsed JSON response
        """
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
            "token": self.api_key,
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
            error_body = json.loads(e.read().decode("utf-8"))
            raise RushDBError(error_body.get("message", str(e)), error_body)
        except urllib.error.URLError as e:
            raise RushDBError(f"Connection error: {str(e)}")
        except json.JSONDecodeError as e:
            raise RushDBError(f"Invalid JSON response: {str(e)}")

    def ping(self) -> bool:
        """Check if the server is reachable."""
        try:
            self._make_request("GET", "/")
            return True
        except RushDBError:
            return False
