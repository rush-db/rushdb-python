"""Ordered and unique indexes over one property of a label.

Accessed via ``db.indexes``. Text indexes are ``db.text_indexes``; vector
indexes are ``db.ai.indexes``.
"""

from typing import Any, Dict

from ..models.api_response import ApiResponse
from .base import BaseAPI


def _with_unique(index: Any) -> Any:
    """An index as the SDK returns it: the server's ``kind`` and ``unique``."""
    if isinstance(index, dict) and "kind" in index:
        return {**index, "unique": index["kind"] == "unique"}
    return index


class IndexesAPI(BaseAPI):
    """Declare, list and drop ordered and unique indexes."""

    def _request(self, method: str, path: str, data: Any = None) -> ApiResponse:
        response = self.client._make_request(method, path, data)
        data_out = response.get("data")
        data_out = (
            [_with_unique(index) for index in data_out]
            if isinstance(data_out, list)
            else _with_unique(data_out)
        )
        return ApiResponse(
            data=data_out,
            success=response.get("success", True),
            total=response.get("total"),
        )

    def find(self) -> ApiResponse:
        """List the project's ordered and unique indexes.

        Returns:
            ApiResponse: ``data`` is a list of ``{name, label, property,
            kind, unique, status}``; ``kind`` is ``ordered`` or ``unique``. ``property`` is stored normalized (``unitPrice``
            is listed as ``unitprice``); ``status`` is ``building``, ``ready``
            or ``dropping``.
        """
        return self._request("GET", "/indexes")

    def create(self, params: Dict[str, Any]) -> ApiResponse:
        """Declare an index over one property of a label. It is built online;
        its ``status`` turns ``ready``.

        A ``unique`` index (RushDB 3.0.14) also refuses a write that would
        give a second record of the label a value another record of it holds:
        the write raises :class:`~rushdb.UniqueConstraintError`. Declaring one
        on data that already repeats a value raises it too.

        Args:
            params: ``label`` and ``property`` (required); optional
                ``unique`` (default ``False``) and ``name`` (defaults to
                ``<label>.<property>.ordered`` or ``.unique``, made unique in
                the project).

        Returns:
            ApiResponse: ``data`` is the created index, ``status`` ``building``
            at first.

        Raises:
            UniqueConstraintError: ``unique`` over data that already repeats
                a value (when the server names the label and property; a plain
                409 ``RushDBError`` otherwise).
        """
        body = {key: value for key, value in params.items() if key != "unique"}
        body["kind"] = "unique" if params.get("unique") else "ordered"
        return self._request("POST", "/indexes", body)

    def delete(self, name: str) -> ApiResponse:
        """Drop an ordered or unique index by name.

        Returns:
            ApiResponse: ``data`` is ``{"deleted": bool}``.
        """
        return self._request("DELETE", f"/indexes/{name}")
