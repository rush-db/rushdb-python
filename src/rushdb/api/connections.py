"""SaaS connections for the RushDB Python SDK (RushDB Cloud only)."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..models.api_response import ApiResponse
from ..models.ingest import (
    CatalogConnector,
    Connection,
    ConnectionFieldsReview,
    ConnectionPreview,
    ConnectionTestResult,
    ConnectionWebhookToken,
    CreateConnectionParams,
    CreatedConnection,
    DeletedConnection,
    FieldChoice,
    ImportRun,
    PushTemplate,
    UpdateConnectionParams,
)
from .base import BaseAPI
from .imports import _guard, _wrap

if TYPE_CHECKING:
    from ..client import RushDB


class ConnectionsAPI(BaseAPI):
    """The project's connections to SaaS tools (CRM, billing, support, issue
    trackers, docs, spreadsheets), custom APIs, webhooks and on-prem agents.
    Every sync is an import run: follow it with ``db.imports.get(run_id)`` or
    ``db.imports.wait(run_id)``.

    Accessed via ``db.connections``. **RushDB Cloud only**: in direct mode
    every method raises ``CloudOnlyError`` before sending anything.
    """

    def __init__(self, client: "RushDB"):
        super().__init__(client)

    def _guard(self, method: str) -> None:
        _guard(self.client, "connections", method)

    def catalog(self) -> "ApiResponse[List[CatalogConnector]]":
        """Built-in connectors and the workspace's own, with their streams,
        auth types and config fields."""
        self._guard("catalog")
        return _wrap(self.client._make_request("GET", "/connections/catalog"))

    def push_templates(self) -> "ApiResponse[List[PushTemplate]]":
        """Zapier, Make and n8n recipes for pushing records into a webhook
        (push) connection."""
        self._guard("push_templates")
        return _wrap(self.client._make_request("GET", "/connections/push-templates"))

    def list(self) -> "ApiResponse[List[Connection]]":
        """The project's connections with their streams, status and last sync."""
        self._guard("list")
        return _wrap(self.client._make_request("GET", "/connections"))

    def get(self, connection_id: str) -> "ApiResponse[Connection]":
        """One connection."""
        self._guard("get")
        return _wrap(self.client._make_request("GET", f"/connections/{connection_id}"))

    def create(
        self, params: CreateConnectionParams
    ) -> "ApiResponse[CreatedConnection]":
        """Create a connection.

        Credentials are sealed on the server and never returned. A push or
        trigger connection's ``webhookToken`` and an agent connection's
        (``connectorId: "agent"``) ``agentToken`` are returned once.

        Args:
            params: ``{"connectorId", "name"?, "config"?, "auth"?, "oauthApp"?,
                "webhookSecret"?, "mode"?, "scheduleMinutes"?, "streams"?,
                "push"?, "agent"?, "specId"?}``.

        Returns:
            ApiResponse: ``data`` is ``{"connection", "webhookToken"?, "agentToken"?}``.
        """
        self._guard("create")
        return _wrap(self.client._make_request("POST", "/connections", dict(params)))

    def update(
        self, connection_id: str, params: UpdateConnectionParams
    ) -> "ApiResponse[Connection]":
        """Change name, credentials, mode, schedule or stream settings
        (labels, delete mode, field policy)."""
        self._guard("update")
        return _wrap(
            self.client._make_request(
                "PATCH", f"/connections/{connection_id}", dict(params)
            )
        )

    def delete(
        self, connection_id: str, delete_data: bool = False
    ) -> "ApiResponse[DeletedConnection]":
        """Delete a connection; ``delete_data=True`` also deletes the records
        it wrote."""
        self._guard("delete")
        params = {"deleteData": "true"} if delete_data else None
        return _wrap(
            self.client._make_request(
                "DELETE", f"/connections/{connection_id}", params=params
            )
        )

    def test(self, connection_id: str) -> "ApiResponse[ConnectionTestResult]":
        """Check the credentials against the provider."""
        self._guard("test")
        return _wrap(
            self.client._make_request("POST", f"/connections/{connection_id}/test", {})
        )

    def preview(
        self, connection_id: str, stream: str, limit: Optional[int] = None
    ) -> "ApiResponse[ConnectionPreview]":
        """The first records of a stream as they would be written (up to 50).
        Writes nothing."""
        self._guard("preview")
        body: Dict[str, Any] = {"stream": stream}
        if limit is not None:
            body["limit"] = limit
        return _wrap(
            self.client._make_request(
                "POST", f"/connections/{connection_id}/preview", body
            )
        )

    def fields(
        self, connection_id: str, stream: str, limit: Optional[int] = None
    ) -> "ApiResponse[ConnectionFieldsReview]":
        """The field review of one stream: sampled field profiles with
        personal-data findings (values of fields that look personal are
        masked), the stream's current policy and the fields held back since
        the last review. Writes nothing.

        Args:
            stream: The stream name.
            limit: Records to sample, 1–200.
        """
        self._guard("fields")
        body: Dict[str, Any] = {"stream": stream}
        if limit is not None:
            body["limit"] = limit
        return _wrap(
            self.client._make_request(
                "POST", f"/connections/{connection_id}/fields", body
            )
        )

    def review_fields(
        self, connection_id: str, stream: str, choices: List[FieldChoice]
    ) -> "ApiResponse[Connection]":
        """Save a field review: the stream switches to an allowlist of the
        fields marked ``include`` or ``hash`` (hashed ones are kept as a keyed
        hash); ``exclude``d fields are left out, and new fields wait for the
        next review.

        Args:
            choices: ``[{"name": "email", "action": "include" | "exclude" | "hash"}]``.
        """
        self._guard("review_fields")

        def pick(action: str) -> List[str]:
            return [choice["name"] for choice in choices if choice["action"] == action]

        body = {
            "streams": [
                {
                    "stream": stream,
                    "policy": {
                        "mode": "allowlist",
                        "include": pick("include"),
                        "exclude": pick("exclude"),
                        "hash": pick("hash"),
                    },
                }
            ]
        }
        return _wrap(
            self.client._make_request("PATCH", f"/connections/{connection_id}", body)
        )

    def sync(
        self,
        connection_id: str,
        streams: Optional[List[str]] = None,
        full: Optional[bool] = None,
    ) -> "ApiResponse[ImportRun]":
        """Sync now and return the queued run.

        Args:
            streams: Stream names; every enabled stream when omitted.
            full: Ignore stored cursors and read everything again.
        """
        self._guard("sync")
        body: Dict[str, Any] = {}
        if streams is not None:
            body["streams"] = streams
        if full is not None:
            body["full"] = full
        return _wrap(
            self.client._make_request(
                "POST", f"/connections/{connection_id}/runs", body
            )
        )

    def runs(
        self,
        connection_id: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> "ApiResponse[List[ImportRun]]":
        """The connection's sync runs, newest first; ``total`` is the count."""
        self._guard("runs")
        params = {
            key: value
            for key, value in (("limit", limit), ("skip", skip))
            if value is not None
        }
        return _wrap(
            self.client._make_request(
                "GET", f"/connections/{connection_id}/runs", params=params or None
            )
        )

    def pause(self, connection_id: str) -> "ApiResponse[Connection]":
        """Stop scheduled and webhook-triggered syncs until resumed."""
        self._guard("pause")
        return _wrap(
            self.client._make_request("POST", f"/connections/{connection_id}/pause", {})
        )

    def resume(self, connection_id: str) -> "ApiResponse[Connection]":
        """Resume scheduled and webhook-triggered syncs."""
        self._guard("resume")
        return _wrap(
            self.client._make_request(
                "POST", f"/connections/{connection_id}/resume", {}
            )
        )

    def rotate_webhook_token(
        self, connection_id: str
    ) -> "ApiResponse[ConnectionWebhookToken]":
        """A new token, shown once; the previous one stops working. Trigger and
        push connections get a new webhook URL, agent connections a new agent
        token."""
        self._guard("rotate_webhook_token")
        return _wrap(
            self.client._make_request(
                "POST", f"/connections/{connection_id}/webhook-token", {}
            )
        )
