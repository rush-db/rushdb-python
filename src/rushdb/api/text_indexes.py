"""BM25 text indexes, searched with ``db.records.text_search()`` or as the
keyword leg of a hybrid ``db.records.vector_search({..., "text": {...}})``.

Accessed via ``db.text_indexes``. Mirrors the TypeScript SDK ``db.textIndexes``.
"""

from typing import Any, Dict

from ..models.api_response import ApiResponse
from .base import BaseAPI


class TextIndexesAPI(BaseAPI):
    """Declare, list and drop BM25 text indexes."""

    def _request(self, method: str, path: str, data: Any = None) -> ApiResponse:
        response = self.client._make_request(method, path, data)
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def find(self) -> ApiResponse:
        """List the project's text indexes.

        Returns:
            ApiResponse: ``data`` is a list of ``{name, label, property,
            consistency, status, pending}``.
        """
        return self._request("GET", "/text-indexes")

    def create(self, params: Dict[str, Any]) -> ApiResponse:
        """Declare a text index over one property of a label, or every string
        of it (``property: "*"``). It is built online; its ``status`` turns
        ``ready``.

        Args:
            params: ``label`` and ``property`` (required); optional ``name``
                (defaults to a unique ``<label>.<property>.text``) and
                ``consistency`` (``eventual``, the default, or ``immediate``).

        Returns:
            ApiResponse: ``data`` is the created text index.
        """
        return self._request("POST", "/text-indexes", params)

    def suggest_name(self, params: Dict[str, Any]) -> ApiResponse:
        """The name a new text index over ``label`` and ``property`` would get
        by default, unique in the project.

        Returns:
            ApiResponse: ``data`` is ``{"name": ...}``.
        """
        return self._request("POST", "/text-indexes/name-suggestion", params)

    def delete(self, name: str) -> ApiResponse:
        """Drop a text index by name.

        Returns:
            ApiResponse: ``data`` is ``{"deleted": True}``.
        """
        return self._request("DELETE", f"/text-indexes/{name}")
