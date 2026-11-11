"""db.connections against a mocked HTTP layer."""

import json
from unittest import mock

import pytest

from rushdb import RushDB

API = "https://api.test/api/v1"


class _Resp:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")
        self.status = 200
        self.headers = {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def calls():
    recorded = []

    def fake_urlopen(request, timeout=None):
        headers = {key.lower(): value for key, value in request.header_items()}
        recorded.append(
            {
                "method": request.get_method(),
                "path": request.full_url[len(API) :],
                "body": (
                    json.loads(request.data.decode("utf-8")) if request.data else None
                ),
                "auth": headers.get("authorization"),
            }
        )
        return _Resp({"success": True, "data": {"ok": True}})

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        yield recorded


def db():
    return RushDB("token", url="https://api.test")


def test_every_method_maps_to_its_route(calls):
    connections = db().connections

    connections.catalog()
    connections.list()
    connections.get("conn-1")
    connections.create(
        {
            "connectorId": "hubspot",
            "name": "HubSpot",
            "auth": {"type": "bearer", "token": "token"},
            "mode": "scheduled",
            "scheduleMinutes": 60,
            "streams": [
                {"stream": "contacts", "policy": {"mode": "auto", "exclude": ["phone"]}}
            ],
        }
    )
    connections.update("conn-1", {"scheduleMinutes": 30})
    connections.delete("conn-1")
    connections.delete("conn-1", delete_data=True)
    connections.test("conn-1")
    connections.preview("conn-1", "contacts", limit=5)
    connections.sync("conn-1", streams=["contacts"], full=True)
    connections.sync("conn-1")
    connections.runs("conn-1", limit=5, skip=10)
    connections.pause("conn-1")
    connections.resume("conn-1")
    connections.rotate_webhook_token("conn-1")
    connections.push_templates()
    connections.fields("conn-1", "contacts", limit=100)
    connections.fields("conn-1", "deals")

    assert [f"{call['method']} {call['path']}" for call in calls] == [
        "GET /connections/catalog",
        "GET /connections",
        "GET /connections/conn-1",
        "POST /connections",
        "PATCH /connections/conn-1",
        "DELETE /connections/conn-1",
        "DELETE /connections/conn-1?deleteData=true",
        "POST /connections/conn-1/test",
        "POST /connections/conn-1/preview",
        "POST /connections/conn-1/runs",
        "POST /connections/conn-1/runs",
        "GET /connections/conn-1/runs?limit=5&skip=10",
        "POST /connections/conn-1/pause",
        "POST /connections/conn-1/resume",
        "POST /connections/conn-1/webhook-token",
        "GET /connections/push-templates",
        "POST /connections/conn-1/fields",
        "POST /connections/conn-1/fields",
    ]
    assert all(call["auth"] == "Bearer token" for call in calls)
    assert calls[3]["body"] == {
        "connectorId": "hubspot",
        "name": "HubSpot",
        "auth": {"type": "bearer", "token": "token"},
        "mode": "scheduled",
        "scheduleMinutes": 60,
        "streams": [
            {"stream": "contacts", "policy": {"mode": "auto", "exclude": ["phone"]}}
        ],
    }
    assert calls[4]["body"] == {"scheduleMinutes": 30}
    assert calls[8]["body"] == {"stream": "contacts", "limit": 5}
    assert calls[9]["body"] == {"streams": ["contacts"], "full": True}
    # Writes without parameters still send a JSON body.
    assert calls[10]["body"] == {}
    assert calls[7]["body"] == {}
    assert calls[16]["body"] == {"stream": "contacts", "limit": 100}
    assert calls[17]["body"] == {"stream": "deals"}


def test_a_field_review_is_saved_as_an_allowlist_policy(calls):
    db().connections.review_fields(
        "conn-1",
        "contacts",
        [
            {"name": "company", "action": "include"},
            {"name": "email", "action": "hash"},
            {"name": "phone", "action": "exclude"},
            {"name": "title", "action": "include"},
        ],
    )
    assert len(calls) == 1
    assert f"{calls[0]['method']} {calls[0]['path']}" == "PATCH /connections/conn-1"
    assert calls[0]["body"] == {
        "streams": [
            {
                "stream": "contacts",
                "policy": {
                    "mode": "allowlist",
                    "include": ["company", "title"],
                    "exclude": ["phone"],
                    "hash": ["email"],
                },
            }
        ]
    }


def test_an_agent_connection_is_created_and_its_token_rotated(calls):
    connections = db().connections
    connections.create(
        {"connectorId": "agent", "name": "Warehouse", "agent": {"intervalMinutes": 15}}
    )
    connections.rotate_webhook_token("agent-1")
    assert [f"{call['method']} {call['path']}" for call in calls] == [
        "POST /connections",
        "POST /connections/agent-1/webhook-token",
    ]
    assert calls[0]["body"] == {
        "connectorId": "agent",
        "name": "Warehouse",
        "agent": {"intervalMinutes": 15},
    }


def test_responses_are_wrapped(calls):
    response = db().connections.test("conn-1")
    assert response.success is True
    assert response.data == {"ok": True}
