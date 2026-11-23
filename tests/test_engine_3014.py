"""RushDB 3.0.14: typed values, spatial queries, catalog-check warnings,
unique indexes, batched ingest and reading your own text writes. Every test
runs without a server, against RushDB Cloud's REST shape and a direct-mode
engine, and against engines that do not advertise the new features."""

import io
import json
import urllib.error
from unittest import mock

import pytest

from rushdb import (
    CatalogCheckError,
    DirectModeError,
    RushDB,
    RushDBError,
    UniqueConstraintError,
    distance_from,
    point,
    within_box,
    within_radius,
)
from rushdb.direct import DirectEngine
from rushdb.direct.schema import build_schema, build_schema_markdown

RECORD = {"id": "r1", "label": "Cafe", "properties": {"name": "Kaffeehaus"}}
WARNING = {
    "kind": "unknownValue",
    "labels": ["Person"],
    "property": "city",
    "value": "berlin",
    "suggestions": [{"value": "Berlin", "reason": "spelling"}],
}
CONFLICT = {
    "protocolVersion": 1,
    "error": {
        "code": "conflict",
        "retryable": False,
        "message": "unique constraint conflict on `User`.`email`: record r9 holds the value",
        "details": {"label": "User", "property": "email", "recordId": "r9"},
    },
}
STRICT_REFUSAL = {
    "protocolVersion": 1,
    "error": {
        "code": "invalid_request",
        "retryable": False,
        "message": "the query names values no record holds",
        "details": {"warnings": [WARNING]},
    },
}
CAPABILITIES_3014 = {
    "typedTemporalValues": True,
    "pointValues": True,
    "spatialFilters": True,
    "uniqueIndexes": True,
    "catalogCheck": True,
}


class FakeEngine:
    """Answers protocol envelopes; ``answers`` maps ``kind.inner`` to a
    response, an envelope (``{"warnings": ...}`` beside the response), an
    ``(status, error body)`` pair, or a list of those answered in turn."""

    def __init__(self, capabilities=None, answers=None):
        self.capabilities = CAPABILITIES_3014 if capabilities is None else capabilities
        self.answers = answers or {}
        self.envelopes = []

    def __call__(self, engine, data, headers, is_read):
        envelope = json.loads(data)
        self.envelopes.append(envelope)
        operation = envelope["operation"]
        inner = operation.get(operation["kind"]) or operation.get("mutation") or {}
        key = f"{operation['kind']}.{inner.get('kind', '')}"
        if key == "describe.capabilities":
            body = {
                "response": {"kind": "capabilities", "capabilities": self.capabilities}
            }
        else:
            answer = self.answers.get(key, {"kind": "mutation", "affected": 1})
            if isinstance(answer, list):
                answer = answer.pop(0)
            if isinstance(answer, tuple):
                status, error = answer
                return status, json.dumps(error).encode("utf-8")
            body = answer if "response" in answer else {"response": answer}
        return 200, json.dumps({"protocolVersion": 1, **body}).encode("utf-8")

    def operations(self, key=None):
        found = []
        for envelope in self.envelopes:
            operation = envelope["operation"]
            inner = operation.get(operation["kind"]) or operation.get("mutation") or {}
            if key is None or f"{operation['kind']}.{inner.get('kind', '')}" == key:
                found.append(envelope)
        return found


@pytest.fixture
def engine():
    fake = FakeEngine()
    with mock.patch.object(DirectEngine, "_send", autospec=True, side_effect=fake):
        yield fake


def direct_db():
    return RushDB("TOKEN", direct=True, engine_url="http://engine:3000")


class CloudFake:
    """Answers RushDB Cloud REST calls through ``urlopen``."""

    def __init__(self, answers):
        self.answers = answers
        self.requests = []

    def __call__(self, request, timeout=None):
        body = json.loads(request.data) if request.data else None
        self.requests.append((request.get_method(), request.full_url, body))
        answer = self.answers[len(self.requests) - 1]
        if isinstance(answer, tuple):
            status, error = answer
            raise urllib.error.HTTPError(
                request.full_url,
                status,
                "error",
                {},
                io.BytesIO(json.dumps(error).encode("utf-8")),
            )
        response = mock.MagicMock()
        response.read.return_value = json.dumps(answer).encode("utf-8")
        response.__enter__.return_value = response
        return response


def cloud(answers):
    fake = CloudFake(answers)
    patcher = mock.patch("urllib.request.urlopen", side_effect=fake)
    patcher.start()
    return fake, patcher


# ── spatial query helpers ───────────────────────────────────────────────────


def test_spatial_helpers_build_the_engine_operands():
    berlin = point(13.405, 52.52)
    assert berlin == {"type": "Point", "coordinates": [13.405, 52.52]}
    assert point(1, 2, 3, crs="cartesian-3d") == {
        "type": "Point",
        "coordinates": [1, 2, 3],
        "crs": "cartesian-3d",
    }
    assert within_radius(berlin, 2000) == {
        "$within": {"center": berlin, "meters": 2000}
    }
    assert within_box(point(13.3, 52.45), point(13.5, 52.55)) == {
        "$within": {"box": [point(13.3, 52.45), point(13.5, 52.55)]}
    }
    assert distance_from(berlin) == {"$distance": berlin}


def test_within_and_distance_reach_the_engine_unchanged(engine):
    engine.answers["query.records"] = {
        "kind": "records",
        "records": [RECORD],
        "total": 1,
    }
    berlin = point(13.405, 52.52)
    direct_db().records.find(
        {
            "labels": ["Cafe"],
            "where": {"location": within_radius(berlin, 2000)},
            "orderBy": {"location": distance_from(berlin)},
            "limit": 5,
        }
    )
    (envelope,) = engine.operations("query.records")
    document = envelope["operation"]["query"]["query"]
    assert document["predicate"] == {
        "location": {"$within": {"center": berlin, "meters": 2000}}
    }
    assert document["order"] == {"location": {"$distance": berlin}}
    assert "context" not in envelope


def test_a_point_is_a_flat_value_for_create_many(engine):
    engine.answers["ingest.documents"] = {
        "kind": "ingested",
        "count": 1,
        "records": [RECORD],
    }
    direct_db().records.create_many(
        "Cafe", [{"name": "Kaffeehaus", "location": point(13.405, 52.52)}]
    )
    with pytest.raises(ValueError):
        direct_db().records.create_many("Cafe", [{"address": {"city": "Berlin"}}])


# ── catalog check ───────────────────────────────────────────────────────────


def test_direct_mode_returns_catalog_warnings_and_sends_check(engine):
    engine.answers["query.records"] = {
        "response": {"kind": "records", "records": [], "total": 0},
        "warnings": [WARNING],
    }
    result = direct_db().records.find(
        {
            "labels": ["Person"],
            "where": {"city": "berlin"},
            "context": {"check": "warn"},
        }
    )
    assert result.catalog_warnings == [WARNING]
    assert result.warnings == []
    (envelope,) = engine.operations("query.records")
    assert envelope["context"] == {"check": "warn"}
    # The query document itself refuses unknown keys.
    assert "context" not in envelope["operation"]["query"]["query"]


def test_no_check_is_sent_unless_asked(engine):
    engine.answers["query.records"] = {
        "kind": "records",
        "records": [RECORD],
        "total": 1,
    }
    result = direct_db().records.find({"labels": ["Cafe"]})
    assert result.catalog_warnings == []
    assert all("context" not in envelope for envelope in engine.envelopes)
    assert engine.operations("describe.capabilities") == []


def test_strict_refusal_raises_catalog_check_error(engine):
    engine.answers["query.records"] = (400, STRICT_REFUSAL)
    with pytest.raises(CatalogCheckError) as caught:
        direct_db().records.find(
            {
                "labels": ["Person"],
                "where": {"city": "berlin"},
                "context": {"check": "strict"},
            }
        )
    assert caught.value.warnings == [WARNING]
    assert caught.value.code == "invalid_request"
    assert caught.value.status == 400


def test_an_engine_without_the_check_runs_queries_unchecked():
    fake = FakeEngine(
        capabilities={},
        answers={"query.records": {"kind": "records", "records": [RECORD], "total": 1}},
    )
    with mock.patch.object(DirectEngine, "_send", autospec=True, side_effect=fake):
        db = direct_db()
        db.records.find({"labels": ["Cafe"], "context": {"check": "warn"}})
        db.records.find({"labels": ["Cafe"], "context": {"check": "off"}})
        with pytest.raises(DirectModeError):
            db.records.find({"labels": ["Cafe"], "context": {"check": "strict"}})
    assert all("context" not in envelope for envelope in fake.envelopes)
    # Capabilities are read once per engine.
    assert len(fake.operations("describe.capabilities")) == 1


def test_property_values_carry_warnings(engine):
    engine.answers["query.propertyValues"] = {
        "response": {"kind": "propertyValues", "property": "city", "values": []},
        "warnings": [WARNING],
    }
    response = direct_db().properties.values(
        "city", {"labels": ["Person"], "context": {"check": "warn"}}
    )
    assert response["warnings"] == [WARNING]
    (envelope,) = engine.operations("query.propertyValues")
    assert envelope["context"] == {"check": "warn"}


def test_cloud_sends_context_in_the_body_and_reads_top_level_warnings():
    fake, patcher = cloud(
        [{"success": True, "data": [], "total": 0, "warnings": [WARNING]}]
    )
    try:
        result = RushDB("KEY").records.find(
            {
                "labels": ["Person"],
                "where": {"city": "berlin"},
                "context": {"check": "warn"},
            }
        )
    finally:
        patcher.stop()
    method, url, body = fake.requests[0]
    assert url.endswith("/records/search")
    assert body["context"] == {"check": "warn"}
    assert result.catalog_warnings == [WARNING]


def test_cloud_strict_refusal_keeps_code_and_details():
    fake, patcher = cloud([(400, STRICT_REFUSAL)])
    try:
        with pytest.raises(CatalogCheckError) as caught:
            RushDB("KEY").records.find(
                {"labels": ["Person"], "context": {"check": "strict"}}
            )
    finally:
        patcher.stop()
    assert caught.value.warnings == [WARNING]
    assert caught.value.code == "invalid_request"


def test_smart_search_warnings_stay_apart_from_catalog_warnings():
    fake, patcher = cloud([{"success": True, "data": [], "total": 0}])
    try:
        result = RushDB("KEY").records.find({"labels": ["Person"]})
    finally:
        patcher.stop()
    assert result.catalog_warnings == []
    assert result.to_dict()["catalog_warnings"] == []


# ── unique indexes ──────────────────────────────────────────────────────────


def test_a_unique_conflict_raises_unique_constraint_error(engine):
    engine.answers["mutate.putRecord"] = (409, CONFLICT)
    with pytest.raises(UniqueConstraintError) as caught:
        direct_db().records.create("User", {"email": "a@example.com"})
    error = caught.value
    assert isinstance(error, RushDBError)
    assert (error.label, error.property, error.record_id) == ("User", "email", "r9")
    assert error.status == 409
    assert error.code == "conflict"


def test_cloud_unique_conflict_raises_unique_constraint_error():
    fake, patcher = cloud([(409, CONFLICT)])
    try:
        with pytest.raises(UniqueConstraintError) as caught:
            RushDB("KEY").records.create("User", {"email": "a@example.com"})
    finally:
        patcher.stop()
    assert caught.value.record_id == "r9"


def test_a_plain_conflict_stays_a_rushdb_error():
    fake, patcher = cloud([(409, {"statusCode": 409, "message": "Index exists"})])
    try:
        with pytest.raises(RushDBError) as caught:
            RushDB("KEY").indexes.create({"label": "User", "property": "email"})
    finally:
        patcher.stop()
    assert not isinstance(caught.value, UniqueConstraintError)
    assert caught.value.status == 409


def test_cloud_index_routes_send_kind_and_return_unique():
    index = {
        "name": "User.email.unique",
        "label": "User",
        "property": "email",
        "kind": "unique",
        "status": "building",
    }
    fake, patcher = cloud(
        [
            {"success": True, "data": index},
            {"success": True, "data": [index]},
            {"success": True, "data": {"deleted": True}},
        ]
    )
    try:
        db = RushDB("KEY")
        created = db.indexes.create(
            {"label": "User", "property": "email", "unique": True}
        )
        listed = db.indexes.find()
        dropped = db.indexes.delete("User.email.unique")
    finally:
        patcher.stop()
    assert fake.requests[0][0] == "POST"
    assert fake.requests[0][1].endswith("/indexes")
    assert fake.requests[0][2] == {
        "label": "User",
        "property": "email",
        "kind": "unique",
    }
    assert created.data["unique"] is True and created.data["kind"] == "unique"
    assert listed.data[0]["unique"] is True
    assert fake.requests[2][0] == "DELETE"
    assert fake.requests[2][1].endswith("/indexes/User.email.unique")
    assert dropped.data == {"deleted": True}


def test_direct_mode_indexes(engine):
    unique = {
        "kind": "unique",
        "name": "User.email.unique",
        "label": "User",
        "property": "email",
        "state": "building",
    }
    engine.answers["describe.indexes"] = {
        "kind": "indexes",
        "indexes": [
            {
                "kind": "text",
                "name": "t",
                "label": "User",
                "property": "bio",
                "state": "ready",
            },
            {
                "kind": "ordered",
                "name": "User.age.ordered",
                "label": "User",
                "property": "age",
                "state": "ready",
            },
        ],
    }
    engine.answers["index.create"] = {"kind": "index", "index": unique}
    db = direct_db()

    created = db.indexes.create({"label": "User", "property": "email", "unique": True})
    (envelope,) = engine.operations("index.create")
    assert envelope["operation"]["index"]["definition"] == {
        "name": "User.email.unique",
        "label": "User",
        "property": "email",
        "kind": "unique",
    }
    assert created.data == {
        "name": "User.email.unique",
        "label": "User",
        "property": "email",
        "kind": "unique",
        "unique": True,
        "status": "building",
    }

    listed = db.indexes.find()
    assert [index["name"] for index in listed.data] == ["User.age.ordered"]
    assert listed.data[0]["unique"] is False

    db.indexes.create({"label": "User", "property": "age"})
    definition = engine.operations("index.create")[1]["operation"]["index"][
        "definition"
    ]
    assert definition["kind"] == "ordered"
    assert definition["name"] == "User.age.ordered-2"

    assert db.indexes.delete("User.age.ordered").data == {"deleted": True}
    with pytest.raises(RushDBError) as caught:
        db.indexes.delete("t")  # a text index is dropped with db.text_indexes
    assert caught.value.status == 404


def test_unique_index_needs_an_engine_that_has_them():
    fake = FakeEngine(
        capabilities={},
        answers={"describe.indexes": {"kind": "indexes", "indexes": []}},
    )
    with mock.patch.object(DirectEngine, "_send", autospec=True, side_effect=fake):
        with pytest.raises(DirectModeError):
            direct_db().indexes.create(
                {"label": "User", "property": "email", "unique": True}
            )
        direct_db().indexes.create({"label": "User", "property": "age"})
    assert len(fake.operations("index.create")) == 1


# ── batched ingest ──────────────────────────────────────────────────────────


def test_create_many_is_one_request_unless_batched(engine):
    engine.answers["ingest.documents"] = {"kind": "ingested", "count": 0, "records": []}
    rows = [{"n": i} for i in range(12_001)]
    direct_db().records.create_many("Row", rows, options={"returnResult": False})
    direct_db().records.create_many(
        "Row", rows, options={"returnResult": False}, batch_size=5000
    )
    sizes = [
        len(envelope["operation"]["ingest"]["documents"])
        for envelope in engine.operations("ingest.documents")
    ]
    assert sizes == [12_001, 5000, 5000, 2001]


def test_batches_are_configurable_and_merge_their_results():
    fake, patcher = cloud(
        [
            {"success": True, "data": [{"__id": "a"}, {"__id": "b"}]},
            {"success": True, "data": [{"__id": "c"}]},
        ]
    )
    try:
        result = RushDB("KEY").records.create_many(
            "Row", [{"n": 1}, {"n": 2}, {"n": 3}], batch_size=2
        )
    finally:
        patcher.stop()
    assert [len(body["data"]) for _, _, body in fake.requests] == [2, 1]
    assert [record.id for record in result] == ["a", "b", "c"]
    assert result.total == 3


def test_by_default_one_request_however_large():
    fake, patcher = cloud([{"success": True, "data": {"message": "ok", "count": 6000}}])
    try:
        result = RushDB("KEY").records.create_many(
            "Row", [{"n": i} for i in range(6000)], options={"returnResult": False}
        )
    finally:
        patcher.stop()
    assert len(fake.requests) == 1
    assert result.total == 6000


def test_import_json_batches_a_top_level_list(engine):
    engine.answers["ingest.documents"] = {"kind": "ingested", "count": 0, "records": []}
    db = direct_db()
    items = [{"n": i, "tags": [{"t": "x"}]} for i in range(10_001)]
    db.records.import_json(items, label="Doc")
    db.records.import_json(items, label="Doc", batch_size=10_000)
    db.records.import_json({"n": 1, "child": {"m": 2}}, label="Doc", batch_size=10)
    sizes = [
        (
            len(envelope["operation"]["ingest"]["documents"])
            if isinstance(envelope["operation"]["ingest"]["documents"], list)
            else "object"
        )
        for envelope in engine.operations("ingest.documents")
    ]
    assert sizes == [10_001, 10_000, 1, "object"]


def test_batches_share_the_transaction():
    fake, patcher = cloud(
        [{"success": True, "data": []}, {"success": True, "data": []}]
    )
    try:
        db = RushDB("KEY")
        with mock.patch.object(db, "_make_request", wraps=db._make_request) as sent:
            db.records.create_many(
                "Row", [{"n": 1}, {"n": 2}], batch_size=1, transaction="tx-9"
            )
    finally:
        patcher.stop()
    assert [call.args[3] for call in sent.call_args_list] == [
        {"X-Transaction-Id": "tx-9"},
        {"X-Transaction-Id": "tx-9"},
    ]


# ── text search right after a write ─────────────────────────────────────────


def text_answer(pending, records):
    return {
        "kind": "records",
        "records": records,
        "total": len(records),
        "textSearch": {"matches": len(records), "pending": pending},
    }


def test_text_search_repeats_while_pending(engine):
    engine.answers["query.hybrid"] = [
        text_answer(2, []),
        text_answer(1, []),
        text_answer(0, [RECORD]),
    ]
    engine.answers["describe.indexes"] = {
        "kind": "indexes",
        "indexes": [
            {
                "kind": "text",
                "name": "Cafe.name.text",
                "label": "Cafe",
                "property": "name",
                "state": "ready",
            }
        ],
    }
    with mock.patch("time.sleep") as slept:
        result = direct_db().records.text_search(
            {"query": "kaffee", "labels": ["Cafe"]}, wait_for_pending=5
        )
    assert [record.id for record in result] == ["r1"]
    assert result.meta["textSearch"]["pending"] == 0
    assert len(engine.operations("query.hybrid")) == 3
    assert slept.call_count == 2


def test_text_search_searches_once_by_default():
    fake, patcher = cloud(
        [
            {
                "success": True,
                "data": [],
                "total": 0,
                "meta": {"textSearch": {"matches": 0, "pending": 3}},
            }
        ]
    )
    try:
        result = RushDB("KEY").records.text_search({"query": "kaffee"})
    finally:
        patcher.stop()
    assert len(fake.requests) == 1
    assert result.meta["textSearch"]["pending"] == 3


# ── typed values in the schema ──────────────────────────────────────────────


def test_schema_keeps_typed_ranges_and_gives_points_none(engine):
    engine.answers["describe.schema"] = {
        "kind": "schema",
        "schema": {
            "labels": [{"name": "Event", "recordsCount": 2}],
            "properties": [
                {
                    "id": "1",
                    "label": "Event",
                    "name": "day",
                    "type": "date",
                    "recordsCount": 2,
                    "min": "2024-05-01",
                    "max": "2024-05-03",
                },
                {
                    "id": "2",
                    "label": "Event",
                    "name": "at",
                    "type": "datetime",
                    "recordsCount": 2,
                    "min": "2024-05-01T10:30:00+02:00",
                    "max": "2024-05-01T12:00:00Z",
                },
                {
                    "id": "3",
                    "label": "Event",
                    "name": "lasts",
                    "type": "duration",
                    "recordsCount": 2,
                    "min": "PT1H",
                    "max": "P1DT2H",
                },
                {
                    "id": "4",
                    "label": "Event",
                    "name": "where",
                    "type": "point",
                    "recordsCount": 2,
                },
                {
                    "id": "5",
                    "label": "Event",
                    "name": "opens",
                    "type": "localtime",
                    "recordsCount": 2,
                    "min": "08:00:00",
                    "max": "10:30:00.5",
                },
            ],
            "relationships": [],
        },
    }
    engine.answers["describe.vectorIndexes"] = {"kind": "vectorIndexes", "indexes": []}
    schema = build_schema(
        DirectEngine("http://engine:3000", "T"), None, lambda raw: raw
    )
    props = {prop["name"]: prop for prop in schema[0]["properties"]}
    assert (props["day"]["min"], props["day"]["max"]) == ("2024-05-01", "2024-05-03")
    assert props["at"]["min"] == "2024-05-01T10:30:00+02:00"
    assert "min" not in props["where"] and "values" not in props["where"]
    markdown = build_schema_markdown(schema)
    assert "| `day` | date | `2024-05-01`..`2024-05-03` |" in markdown
    assert "| `lasts` | duration | `PT1H`..`P1DT2H` |" in markdown
    assert "| `opens` | localtime | `08:00:00`..`10:30:00.5` |" in markdown
    assert "| `where` | point | — |" in markdown


def test_a_failed_batch_says_which_batches_went_in():
    fake, patcher = cloud(
        [
            {"success": True, "data": [{"__id": "a"}, {"__id": "b"}]},
            (409, CONFLICT),
        ]
    )
    try:
        with pytest.raises(UniqueConstraintError) as caught:
            RushDB("KEY").records.create_many(
                "User", [{"n": 1}, {"n": 2}, {"n": 3}, {"n": 4}, {"n": 5}], batch_size=2
            )
    finally:
        patcher.stop()
    assert len(fake.requests) == 2
    assert caught.value.status == 409 and caught.value.record_id == "r9"
    assert caught.value.ingest == {
        "chunks": 3,
        "failed_chunk": 1,
        "completed_chunks": 1,
        "completed_records": 2,
        "in_transaction": False,
    }


def test_an_unbatched_failure_has_no_ingest_report(engine):
    engine.answers["ingest.documents"] = (409, CONFLICT)
    with pytest.raises(UniqueConstraintError) as caught:
        direct_db().records.create_many("User", [{"n": 1}], transaction=None)
    assert caught.value.ingest is None


def test_a_failed_batch_in_a_transaction_was_only_staged(engine):
    engine.answers["transaction.stage"] = [
        {"kind": "transactionStaged", "transactionId": "tx-1", "count": 1},
        (409, CONFLICT),
    ]
    with pytest.raises(RushDBError) as caught:
        direct_db().records.import_json(
            [{"n": 1}, {"n": 2}], label="User", batch_size=1, transaction="tx-1"
        )
    assert caught.value.ingest["in_transaction"] is True
    assert caught.value.ingest["failed_chunk"] == 1
