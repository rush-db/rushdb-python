"""Relationship pattern suggestions API for the RushDB Python SDK."""

from typing import TYPE_CHECKING, Any, Dict

from ..models.api_response import ApiResponse
from .base import BaseAPI

if TYPE_CHECKING:
    from ..client import RushDB


class RelationshipPatternsAPI(BaseAPI):
    """Review and manage relationship patterns inferred from project ontology.

    Accessed via ``db.relationships.patterns``.
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)

    @staticmethod
    def _wrap(response: Dict[str, Any]) -> ApiResponse:
        return ApiResponse(
            data=response.get("data"),
            success=response.get("success", True),
            total=response.get("total"),
        )

    def list(self) -> ApiResponse:
        """List inferred patterns, ontology relationships, and analysis status."""
        response = self.client._make_request("GET", "/relationships/patterns")
        return self._wrap(response)

    def analyze(self) -> ApiResponse:
        """Queue ontology analysis to generate relationship pattern suggestions."""
        response = self.client._make_request(
            "POST", "/relationships/patterns/analyze", {}
        )
        return self._wrap(response)

    def approve(self, pattern_id: str) -> ApiResponse:
        """Approve and apply a suggested relationship pattern."""
        response = self.client._make_request(
            "POST", f"/relationships/patterns/{pattern_id}/approve", {}
        )
        return self._wrap(response)

    def ignore(self, pattern_id: str) -> ApiResponse:
        """Ignore a suggested relationship pattern without applying it."""
        response = self.client._make_request(
            "POST", f"/relationships/patterns/{pattern_id}/ignore", {}
        )
        return self._wrap(response)

    def delete(self, pattern_id: str, *, delete_existing: bool = False) -> ApiResponse:
        """Delete a saved pattern and optionally its materialized relationships."""
        params = {"deleteExisting": "true"} if delete_existing else None
        response = self.client._make_request(
            "DELETE", f"/relationships/patterns/{pattern_id}", params=params
        )
        return self._wrap(response)
