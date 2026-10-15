"""Direct mode (a standalone engine): every SDK method talks to the engine
only, or is refused as Cloud-only before anything is sent."""

import inspect
import io
import json
import urllib.error
from unittest import mock

import pytest

from rushdb import (
    CLOUD_ONLY_METHODS,
    CloudOnlyError,
    DirectModeError,
    RushDB,
    RushDBError,
)

RECORD = {
    "id": "0190a7e2-0000-7000-8000-000000000001",
    "label": "Book",
    "properties": {"title": "Dune"},
}
TEXT_INDEX = {
    "kind": "text",
    "name": "Book.title.text",
    "label": "Book",
    "property": "title",
    "state": "ready",
}
VECTOR_INDEX = {
    "name": "book-vec",
    "label": "Book",
    "property": "title",
    "similarity": "cosine",
    "dimensions": 3,
}


def engine_answer(operation):
    """What a standalone engine answers, by operation."""
    inner = (
        operation["mutation"]
        if operation["kind"] == "mutate"
        else operation.get(operation["kind"], {}) or {}
    )
    key = f"{operation['kind']}.{inner.get('kind', '')}"
    if key == "transaction.stage" and inner["mutation"]["kind"] == "getRecord":
        return {
            "kind": "transactionGet",
            "transactionId": "tx-1",
            "record": {
                "_id": inner["mutation"]["record"]["id"],
                "__label": "Book",
                "properties": {"title": "Dune"},
            },
        }
    answers = {
        "query.record": {"kind": "record", "record": RECORD},
        "query.records": {"kind": "records", "records": [RECORD], "total": 1},
        "query.vector": {"kind": "records", "records": [RECORD], "total": 1},
        "query.hybrid": {"kind": "records", "records": [RECORD], "total": 1},
        "query.relationships": {
            "kind": "relationships",
            "relationships": [],
            "total": 0,
        },
        "query.propertyValues": {
            "kind": "propertyValues",
            "property": "title",
            "values": ["Dune"],
        },
        "query.statement": {"kind": "rows", "rows": [{"n": 1}], "total": 1},
        "query.exportCsv": {
            "kind": "csv",
            "content": "__id,__label,title\r\nr1,Book,Dune",
            "count": 1,
        },
        "describe.schema": {
            "kind": "schema",
            "schema": {
                "labels": [{"name": "Book", "recordsCount": 1}],
                "properties": [
                    {
                        "id": "p1",
                        "name": "title",
                        "type": "string",
                        "recordsCount": 1,
                        "label": "Book",
                    }
                ],
                "relationships": [],
            },
        },
        "describe.labels": {"kind": "labels", "labels": ["Book"]},
        "describe.properties": {
            "kind": "properties",
            "properties": [
                {"id": "p1", "name": "title", "type": "string", "recordsCount": 1}
            ],
        },
        "describe.indexes": {"kind": "indexes", "indexes": [TEXT_INDEX]},
        "describe.vectorIndexes": {"kind": "vectorIndexes", "indexes": [VECTOR_INDEX]},
        "describe.vectorIndex": {
            "kind": "vectorIndexStats",
            "stats": {"totalRecords": 1, "indexedRecords": 1, "index": VECTOR_INDEX},
        },
        "describe.buildInfo": {"kind": "buildInfo", "build": {}},
        "mutate.putRecord": {"kind": "record", "record": RECORD},
        "index.createVector": {"kind": "vectorIndex", "index": VECTOR_INDEX},
        "index.upsertVectors": {
            "kind": "vectorsUpserted",
            "updated": 1,
            "requested": 1,
        },
        "ingest.documents": {
            "kind": "ingested",
            "count": 1,
            "relationships": 0,
            "records": [RECORD],
        },
        "ingest.csv": {
            "kind": "ingested",
            "count": 1,
            "relationships": 0,
            "records": [RECORD],
        },
        "transaction.begin": {"kind": "transactionBegun", "transactionId": "tx-1"},
        "transaction.commit": {
            "kind": "transactionOutcome",
            "transactionId": "tx-1",
            "status": "committed",
            "retryable": False,
        },
        "transaction.stage": {"kind": "transactionStaged", "transactionId": "tx-1"},
    }
    return answers.get(key, {"kind": "mutation", "affected": 1})


class _Resp:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def engine_calls():
    calls = []

    def fake_urlopen(request, timeout=None):
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        calls.append(
            {
                "url": request.full_url,
                "headers": dict(request.header_items()),
                "body": body,
            }
        )
        return _Resp(
            {"protocolVersion": 1, "response": engine_answer(body["operation"])}
        )

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        yield calls


def direct_db(**extra):
    return RushDB(
        "ENGINE-SECRET", direct=True, engine_url="http://engine:3000", **extra
    )


def operations(calls):
    return [call["body"]["operation"] for call in calls]


# One representative call per SDK method.
EVERY_METHOD = {
    "records.attach": lambda db: db.records.attach(
        RECORD["id"], RECORD["id"], options={"type": "LIKES"}
    ),
    "records.detach": lambda db: db.records.detach(
        RECORD["id"], RECORD["id"], options={"typeOrTypes": "LIKES"}
    ),
    "records.create": lambda db: db.records.create("Book", {"title": "Dune"}),
    "records.create_many": lambda db: db.records.create_many(
        "Book", [{"title": "Dune"}]
    ),
    "records.import_json": lambda db: db.records.import_json(
        [{"title": "Dune"}], label="Book"
    ),
    "records.import_csv": lambda db: db.records.import_csv("Book", "title\nDune\n"),
    "records.delete": lambda db: db.records.delete(
        {"labels": ["Book"], "where": {"title": "Dune"}}
    ),
    "records.delete_by_id": lambda db: db.records.delete_by_id(RECORD["id"]),
    "records.export": lambda db: db.records.export({"labels": ["Book"]}),
    "records.find": lambda db: db.records.find({"labels": ["Book"]}),
    "records.find_by_id": lambda db: db.records.find_by_id(RECORD["id"]),
    "records.find_one": lambda db: db.records.find_one({"labels": ["Book"]}),
    "records.find_uniq": lambda db: db.records.find_uniq({"labels": ["Book"]}),
    "records.set": lambda db: db.records.set(
        RECORD["id"], {"title": "Dune"}, label="Book"
    ),
    "records.update": lambda db: db.records.update(RECORD["id"], {"title": "Dune"}),
    "records.upsert": lambda db: db.records.upsert(
        {"title": "Dune"}, label="Book", options={"mergeBy": ["title"]}
    ),
    "records.text_search": lambda db: db.records.text_search(
        {"query": "dune", "labels": ["Book"]}
    ),
    "text_indexes.create": lambda db: db.text_indexes.create(
        {"label": "Book", "property": "summary"}
    ),
    "text_indexes.delete": lambda db: db.text_indexes.delete("Book.title.text"),
    "text_indexes.find": lambda db: db.text_indexes.find(),
    "text_indexes.suggest_name": lambda db: db.text_indexes.suggest_name(
        {"label": "Book", "property": "title"}
    ),
    "records.vector_search": lambda db: db.records.vector_search(
        {"index": "book-vec", "queryVector": [1, 0, 0], "labels": ["Book"]}
    ),
    "properties.delete": lambda db: db.properties.delete("p1"),
    "properties.find": lambda db: db.properties.find({}),
    "properties.find_by_id": lambda db: db.properties.find_by_id("p1"),
    "properties.values": lambda db: db.properties.values("p1"),
    "labels.find": lambda db: db.labels.find({}),
    "tx.begin": lambda db: db.tx.begin(),
    "tx.commit": lambda db: db.tx.commit("tx-1"),
    "tx.get": lambda db: db.tx.get("tx-1"),
    "tx.rollback": lambda db: db.tx.rollback("tx-1"),
    "query.raw": lambda db: db.query.raw({"query": "MATCH (n) RETURN count(n) AS n"}),
    "relationships.create_many": lambda db: db.relationships.create_many(
        source={"label": "Book", "key": "id"},
        target={"label": "Author", "key": "bookId"},
    ),
    "relationships.delete_many": lambda db: db.relationships.delete_many(
        source={"label": "Book", "key": "id"},
        target={"label": "Author", "key": "bookId"},
    ),
    "relationships.find": lambda db: db.relationships.find({}),
    "relationships.patterns.analyze": lambda db: db.relationships.patterns.analyze(),
    "relationships.patterns.approve": lambda db: db.relationships.patterns.approve(
        "pattern-1"
    ),
    "relationships.patterns.delete": lambda db: db.relationships.patterns.delete(
        "pattern-1"
    ),
    "relationships.patterns.ignore": lambda db: db.relationships.patterns.ignore(
        "pattern-1"
    ),
    "relationships.patterns.list": lambda db: db.relationships.patterns.list(),
    "ai.get_schema": lambda db: db.ai.get_schema(),
    "ai.get_schema_markdown": lambda db: db.ai.get_schema_markdown(),
    "ai.indexes.create": lambda db: db.ai.indexes.create(
        {"label": "Book", "propertyName": "summary", "external": True, "dimensions": 3}
    ),
    "ai.indexes.delete": lambda db: db.ai.indexes.delete("book-vec"),
    "ai.indexes.find": lambda db: db.ai.indexes.find(),
    "ai.indexes.stats": lambda db: db.ai.indexes.stats("book-vec"),
    "ai.indexes.upsert_vectors": lambda db: db.ai.indexes.upsert_vectors(
        "book-vec", {"items": [{"recordId": RECORD["id"], "vector": [1, 0, 0]}]}
    ),
    "ai.search": lambda db: db.ai.search("books about deserts"),
    "settings.get": lambda db: db.settings.get(),
}

# Answered without the engine (it has no operation for them).
ANSWERED_LOCALLY = {"tx.get"}


def sdk_methods(db):
    found = set()

    def walk(obj, path, depth):
        for name in dir(obj):
            if name.startswith("_") or name == "client":
                continue
            attr = getattr(obj, name)
            if inspect.ismethod(attr):
                found.add(".".join(path + [name]))
            elif depth < 1 and type(attr).__module__.startswith("rushdb.api"):
                walk(attr, path + [name], depth + 1)

    for namespace in (
        "records",
        "properties",
        "labels",
        "tx",
        "query",
        "relationships",
        "ai",
        "text_indexes",
        "settings",
    ):
        walk(getattr(db, namespace), [namespace], 0)
    return found


def test_every_sdk_method_is_classified():
    assert set(EVERY_METHOD) == sdk_methods(direct_db())


@pytest.mark.parametrize("method", sorted(EVERY_METHOD))
def test_method_talks_to_the_engine_only_or_is_refused_as_cloud_only(
    method, engine_calls
):
    try:
        EVERY_METHOD[method](direct_db())
        outcome = None
    except Exception as error:  # noqa: BLE001 - the outcome is what is asserted
        outcome = error
    for call in engine_calls:
        assert call["url"] == "http://engine:3000/protocol/v1/execute"
    if method in CLOUD_ONLY_METHODS:
        assert isinstance(outcome, CloudOnlyError), outcome
        assert engine_calls == []
    else:
        assert outcome is None, outcome
        if method not in ANSWERED_LOCALLY:
            assert engine_calls


def test_direct_mode_needs_an_engine_url():
    with pytest.raises(ValueError):
        RushDB("ENGINE-SECRET", direct=True)


def test_engine_token_and_tenant_scope_are_sent(engine_calls):
    direct_db(scope="tenant-1").records.find({"labels": ["Book"]})
    assert engine_calls[0]["headers"]["Authorization"] == "Bearer ENGINE-SECRET"
    assert engine_calls[0]["headers"]["X-rushdb-tenant"] == "tenant-1"
    assert engine_calls[0]["body"]["context"] == {"scope": "tenant-1"}


def test_create_returns_the_created_record(engine_calls):
    created = direct_db().records.create("Book", {"title": "Dune"})
    assert created.id == RECORD["id"]
    assert operations(engine_calls)[0]["mutation"]["properties"] == {"title": "Dune"}


def test_find_sends_the_whole_query_document(engine_calls):
    direct_db().records.find(
        {
            "labels": ["Book"],
            "where": {"title": "Dune"},
            "orderBy": {"__id": "asc"},
            "select": {"n": {"$count": "*"}},
            "groupBy": ["$record.genre"],
            "skip": 5,
            "limit": 10,
        }
    )
    assert operations(engine_calls)[0]["query"]["query"] == {
        "labels": ["Book"],
        "predicate": {"title": "Dune"},
        "select": {"n": {"$count": "*"}},
        "groupBy": ["$record.genre"],
        "order": {"id": "asc"},
        "offset": 5,
        "limit": 10,
    }


def test_find_by_id_of_several_ids_searches_by_id(engine_calls):
    other = "0190a7e2-0000-7000-8000-000000000002"
    found = direct_db().records.find_by_id([RECORD["id"], other])
    assert operations(engine_calls)[0]["query"]["query"]["predicate"] == {
        "$id": {"$in": [RECORD["id"], other]}
    }
    assert found.data[0].id == RECORD["id"]


def test_export_returns_the_csv_text(engine_calls):
    assert (
        direct_db().records.export({"labels": ["Book"]})
        == "__id,__label,title\r\nr1,Book,Dune"
    )


def test_a_text_vector_search_needs_cloud(engine_calls):
    with pytest.raises(CloudOnlyError):
        direct_db().records.vector_search(
            {"propertyName": "title", "labels": ["Book"], "query": "deserts"}
        )
    assert engine_calls == []


def test_only_external_indexes_can_be_created(engine_calls):
    with pytest.raises(CloudOnlyError):
        direct_db().ai.indexes.create(
            {"label": "Book", "propertyName": "summary", "dimensions": 3}
        )
    assert engine_calls == []
    direct_db().ai.indexes.create(
        {"label": "Book", "propertyName": "summary", "external": True, "dimensions": 3}
    )
    created = [
        op
        for op in operations(engine_calls)
        if op.get("index", {}).get("kind") == "createVector"
    ][0]
    assert created["index"]["definition"]["name"] == "Book.summary.external.3.cosine"


def staged_mutations(calls):
    return [
        op["transaction"]["mutation"]
        for op in operations(calls)
        if op.get("transaction", {}).get("kind") == "stage"
    ]


def test_a_record_created_in_a_transaction_is_staged(engine_calls):
    db = direct_db()
    tx = db.tx.begin()
    created = db.records.create(
        "Book", {"title": "Dune"}, options={"suggestTypes": True}, transaction=tx
    )
    assert staged_mutations(engine_calls)[0] == {
        "kind": "createRecord",
        "label": "Book",
        "id": created.id,
        "properties": {"title": "Dune"},
        "options": {"suggestTypes": True},
    }
    assert created["title"] == "Dune"


def test_updates_replaces_deletes_and_links_are_staged_by_id(engine_calls):
    db = direct_db()
    db.records.update(RECORD["id"], {"title": "Emma"}, transaction="tx-1")
    db.records.set(RECORD["id"], {"title": "Emma"}, label="Novel", transaction="tx-1")
    db.records.delete_by_id(RECORD["id"], transaction="tx-1")
    db.records.attach(
        RECORD["id"], ["t1", "t2"], options={"direction": "in"}, transaction="tx-1"
    )
    record = {"id": RECORD["id"]}
    link = {
        "kind": "createRelationship",
        "relationType": "__RUSHDB__RELATION__DEFAULT__",
        "target": record,
        "properties": {},
    }
    assert staged_mutations(engine_calls) == [
        {
            "kind": "updateRecord",
            "record": record,
            "properties": {"title": "Emma"},
            "replace": False,
        },
        {"kind": "getRecord", "record": record},
        {"kind": "getRecord", "record": record},
        {
            "kind": "retypeRecord",
            "record": record,
            "fromLabel": "Book",
            "toLabel": "Novel",
        },
        {
            "kind": "updateRecord",
            "record": record,
            "properties": {"title": "Emma"},
            "replace": True,
        },
        {"kind": "getRecord", "record": record},
        {"kind": "deleteRecord", "record": record},
        {**link, "source": {"id": "t1"}},
        {**link, "source": {"id": "t2"}},
    ]


def test_imports_are_staged_into_a_transaction(engine_calls):
    db = direct_db()
    db.records.import_json([{"title": "Dune"}], label="Book", transaction="tx-1")
    db.records.import_csv("Book", "title\nDune\n", transaction="tx-1")
    json_import, csv_import = staged_mutations(engine_calls)
    assert json_import["kind"] == csv_import["kind"] == "ingest"
    assert json_import["ingest"]["kind"] == "documents"
    assert json_import["ingest"]["documents"] == [{"title": "Dune"}]
    assert csv_import["ingest"]["kind"] == "csv"
    assert csv_import["ingest"]["data"] == "title\nDune\n"
    assert not [op for op in operations(engine_calls) if op["kind"] == "ingest"]


def test_a_write_it_cannot_stage_is_refused_before_sending(engine_calls):
    db = direct_db()
    with pytest.raises(DirectModeError):
        db.records.delete({"labels": ["Book"]}, transaction="tx-1")
    with pytest.raises(DirectModeError):
        db.records.detach(RECORD["id"], "t1", transaction="tx-1")
    with pytest.raises(DirectModeError):
        db.records.upsert(
            {"title": "Dune"},
            label="Book",
            options={"mergeBy": ["title"]},
            transaction="tx-1",
        )
    assert engine_calls == []


def test_detach_without_type_or_direction_removes_every_link(engine_calls):
    db = direct_db()
    db.records.detach(RECORD["id"], ["t1"])
    db.records.detach(
        RECORD["id"], ["t1"], options={"typeOrTypes": ["A", "B"], "direction": "out"}
    )
    commands = [
        op["mutation"]["command"]
        for op in operations(engine_calls)
        if op.get("mutation", {}).get("kind") == "unlinkRecordsById"
    ]
    assert commands == [
        {"relationTypes": [], "sourceIds": [RECORD["id"]], "targetIds": ["t1"]},
        {
            "relationTypes": ["A", "B"],
            "direction": "out",
            "sourceIds": [RECORD["id"]],
            "targetIds": ["t1"],
        },
    ]


def test_keyword_search_uses_the_labels_text_index(engine_calls):
    result = direct_db().records.text_search({"query": "dune", "labels": ["Book"]})
    hybrid = [op for op in operations(engine_calls) if op.get("kind") == "query"][0]
    assert hybrid["query"] == {
        "kind": "hybrid",
        "query": {
            "labels": ["Book"],
            "predicate": {},
            "text": {
                "index": "Book.title.text",
                "query": "dune",
                "allTerms": False,
                "phrase": False,
            },
            "offset": 0,
            "limit": 10,
        },
    }
    assert result.data[0]["title"] == "Dune"


def test_text_index_names_default_and_stay_unique(engine_calls):
    db = direct_db()
    suggested = db.text_indexes.suggest_name({"label": "Book", "property": "title"})
    assert suggested.data == {"name": "Book.title.text-2"}
    with pytest.raises(RushDBError) as missing:
        db.text_indexes.delete("nope")
    assert missing.value.status == 404


def test_find_raises_instead_of_returning_nothing():
    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"message":"bad token"}'),
        )

    with mock.patch("urllib.request.urlopen", side_effect=refuse):
        with pytest.raises(RushDBError) as failure:
            RushDB("BAD", base_url="http://cloud:3000").records.find(
                {"labels": ["Book"]}
            )
    assert failure.value.status == 401


def test_ping_checks_the_engine(engine_calls):
    assert direct_db().ping() is True
    assert operations(engine_calls) == [
        {"kind": "describe", "describe": {"kind": "buildInfo"}}
    ]
