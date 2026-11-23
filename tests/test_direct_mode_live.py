"""Direct mode against a real standalone engine. Runs only when
``RUSHDB_TEST_ENGINE_URL`` (and ``RUSHDB_TEST_ENGINE_TOKEN``, default
``local-token``) point at a single-tenant ``rushdb`` started with
``--languages cypher``::

    rushdb serve --data-dir /tmp/rushdb-test --port 3877 --languages cypher
    RUSHDB_TEST_ENGINE_URL=http://127.0.0.1:3877 pytest tests/test_direct_mode_live.py

The read-only capability test also needs the engine's
``--capability-secret`` in ``RUSHDB_TEST_ENGINE_CAPABILITY_SECRET``.

``RUSHDB_TEST_ENGINE_FEATURES`` (comma-separated, e.g.
``typedTemporalValues,uniqueIndexes,catalogCheck,spatialFilters``) adds
capability flags a pre-release build has the features of but does not
advertise yet.
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import uuid

import pytest

from rushdb import (
    CatalogCheckError,
    CloudOnlyError,
    DirectModeError,
    RushDB,
    RushDBError,
    UniqueConstraintError,
)

ENGINE_URL = os.environ.get("RUSHDB_TEST_ENGINE_URL")
pytestmark = pytest.mark.skipif(
    not ENGINE_URL, reason="RUSHDB_TEST_ENGINE_URL is not set"
)

RUN = uuid.uuid4().hex[:8]
BOOK = f"Book{RUN}"
AUTHOR = f"Author{RUN}"


@pytest.fixture(scope="module")
def db():
    client = RushDB(
        os.environ.get("RUSHDB_TEST_ENGINE_TOKEN", "local-token"),
        direct=True,
        engine_url=ENGINE_URL,
    )
    extra = os.environ.get("RUSHDB_TEST_ENGINE_FEATURES")
    if extra:
        client.engine.supports("")
        client.engine._capabilities |= set(extra.split(","))
    client.records.create_many(
        BOOK,
        [
            {"title": "Dune", "pages": 412, "genre": "sf"},
            {"title": "Emma", "pages": 474, "genre": "novel"},
            {"title": "Foundation", "pages": 255, "genre": "sf"},
        ],
    )
    client.records.create_many(AUTHOR, [{"name": "Herbert", "wrote": "Dune"}])
    return client


def test_records_round_trip(db):
    assert db.ping() is True
    created = db.records.create(BOOK, {"title": "Ubik", "pages": 202})
    assert db.records.find_by_id(created.id)["title"] == "Ubik"
    db.records.update(created.id, {"pages": 210})
    assert db.records.find_by_id(created.id)["pages"] == 210
    db.records.update(created.id, {"pages": 211, "label": "worn"}, label=BOOK)
    updated = db.records.find_by_id(created.id)
    assert updated["pages"] == 211 and updated["label"] == "worn"
    assert updated["title"] == "Ubik" and updated.label == BOOK
    db.records.set(created.id, {"title": "Ubik!"}, label=BOOK)
    replaced = db.records.find_by_id(created.id)
    assert replaced["title"] == "Ubik!" and replaced.get("pages") is None
    both = db.records.find_by_id([created.id])
    assert [record.id for record in both.data] == [created.id]
    db.records.delete_by_id(created.id)


def test_search_and_grouping(db):
    sf = db.records.find(
        {"labels": [BOOK], "where": {"genre": "sf"}, "orderBy": {"pages": "asc"}}
    )
    assert [record["title"] for record in sf.data] == ["Foundation", "Dune"]
    grouped = db.records.find(
        {
            "labels": [BOOK],
            "select": {"count": {"$count": "*"}},
            "groupBy": ["$record.genre"],
        }
    )
    rows = [record.to_dict() for record in grouped.data]
    assert {"genre": "sf", "count": 2} in rows


def test_relationships(db):
    db.relationships.create_many(
        source={"label": AUTHOR, "key": "wrote"},
        target={"label": BOOK, "key": "title"},
        type="AUTHORED",
    )
    found = db.relationships.find(
        {"where": {"type": "AUTHORED"}, "source": {"labels": [AUTHOR]}}
    )
    assert found.total == 1

    edge = found.data[0]
    result = db.relationships.update(
        edge["sourceId"],
        edge["targetId"],
        type="AUTHORED",
        set={"year": 1965, "role": "author", "since": "1965-08-01T10:30:00.000Z"},
        types={"since": "datetime"},
    )
    assert result["data"]["updated"] == 1
    db.relationships.update(
        edge["sourceId"], edge["targetId"], type="AUTHORED", unset=["role"]
    )
    updated = db.relationships.find(
        {"where": {"type": "AUTHORED"}, "source": {"labels": [AUTHOR]}}
    )
    properties = updated.data[0].get("properties")
    # RushDB 3.0.14 prints the shortest fraction; 3.0.13 printed milliseconds.
    assert properties["since"] in ("1965-08-01T10:30:00Z", "1965-08-01T10:30:00.000Z")
    assert properties == {"year": 1965, "since": properties["since"]}
    assert updated.data[0].get("propertyTypes", {}).get("since") == "datetime"


def test_labels_properties_schema(db):
    assert db.labels.find({})["data"][BOOK] >= 3
    pages = [
        prop
        for prop in db.properties.find({"labels": [BOOK]})["data"]
        if prop["name"] == "pages"
    ][0]
    assert pages["type"] == "number"
    schema = db.ai.get_schema({"labels": [BOOK]})
    assert schema.data[0]["label"] == BOOK
    assert f"## `{BOOK}`" in db.ai.get_schema_markdown({"labels": [BOOK]}).data


def test_csv_import_and_export(db):
    db.records.import_csv(
        BOOK, "title,pages,in print\nSolaris,204,true\n", options={"suggestTypes": True}
    )
    solaris = db.records.find_one({"labels": [BOOK], "where": {"title": "Solaris"}})
    assert solaris["pages"] == 204 and solaris["in_print"] is True
    csv = db.records.export({"labels": [BOOK], "where": {"title": "Solaris"}})
    assert csv.startswith("__id,__label,in_print,pages,title\r\n")


def test_external_vectors(db):
    created = db.ai.indexes.create(
        {"label": BOOK, "propertyName": "title", "external": True, "dimensions": 3}
    )
    name = created.data["name"]
    dune = db.records.find_one({"labels": [BOOK], "where": {"title": "Dune"}})
    db.ai.indexes.upsert_vectors(
        name, {"items": [{"recordId": dune.id, "vector": [1, 0, 0]}]}
    )
    db.records.create(
        BOOK,
        {"title": "Hyperion"},
        vectors=[{"propertyName": "title", "vector": [0, 0, 1]}],
    )
    nearest = db.records.vector_search(
        {
            "propertyName": "title",
            "labels": [BOOK],
            "queryVector": [0, 0.1, 1],
            "limit": 1,
        }
    )
    assert nearest.data[0]["title"] == "Hyperion"
    db.ai.indexes.delete(name)


def test_raw_cypher(db):
    result = db.query.raw(
        {"query": f"MATCH (b:{BOOK}) WHERE b.title = 'Dune' RETURN b.pages AS pages"}
    )
    assert result["data"]["records"] == [{"pages": 412}]


def test_transactions(db):
    # A label with no text index: a transaction deleting a record an eventual
    # text index has not applied yet loses to the index's background commit.
    shelf = f"Shelf{RUN}"
    dune = db.records.create(shelf, {"title": "Dune"})
    doomed = db.records.create(shelf, {"title": "Doomed"})
    tx = db.tx.begin()
    staged = db.records.create(shelf, {"title": "Staged"}, transaction=tx)
    updated = db.records.update(staged.id, {"pages": 1}, transaction=tx)["data"]
    assert updated["title"] == "Staged" and updated["pages"] == 1
    db.records.attach(dune, staged, options={"type": "SEQUEL"}, transaction=tx)
    db.records.delete_by_id(doomed.id, transaction=tx)
    with pytest.raises(DirectModeError):
        db.records.detach(dune, staged, transaction=tx)
    assert db.records.find({"labels": [shelf], "where": {"title": "Staged"}}).total == 0
    tx.commit()
    time.sleep(0.05)
    assert db.records.find_by_id(staged.id)["pages"] == 1
    assert db.records.find({"labels": [shelf], "where": {"title": "Doomed"}}).total == 0
    sequels = {"where": {"type": "SEQUEL"}, "source": {"labels": [shelf]}}
    assert db.relationships.find(sequels).total == 1
    db.records.detach(dune, staged)
    assert db.relationships.find(sequels).total == 0


def test_keyword_search(db):
    created = db.text_indexes.create({"label": BOOK, "property": "title"})
    name = created.data["name"]
    for _ in range(100):
        indexes = {index["name"]: index for index in db.text_indexes.find().data}
        if indexes[name]["status"] == "ready" and indexes[name]["pending"] == 0:
            break
        time.sleep(0.05)
    found = db.records.text_search({"query": "foundation", "labels": [BOOK]})
    assert [record["title"] for record in found.data] == ["Foundation"]
    assert found.meta["textSearch"]["matches"] == 1
    db.text_indexes.delete(name)


def test_cloud_features_are_refused(db):
    with pytest.raises(CloudOnlyError):
        db.ai.search("books about deserts")
    with pytest.raises(CloudOnlyError):
        db.relationships.patterns.list()
    with pytest.raises(CloudOnlyError):
        db.settings.get()


def test_calls_share_one_connection(db):
    db.engine.close()
    db.records.find({"labels": [BOOK]})
    conn = db.engine._connections[threading.current_thread()][0]
    sock = conn.sock
    for _ in range(20):
        db.records.find({"labels": [BOOK]})
    db.records.create(BOOK, {"title": "Kept alive"})
    assert db.engine._connections[threading.current_thread()][0] is conn
    assert conn.sock is sock
    db.engine.close()
    assert (
        db.records.find({"labels": [BOOK], "where": {"title": "Kept alive"}}).total == 1
    )


def test_bad_token_raises_rushdb_error():
    db = RushDB("not-the-token", direct=True, engine_url=ENGINE_URL)
    with pytest.raises(RushDBError) as failure:
        db.records.create(BOOK, {"title": "Refused"})
    assert failure.value.status == 401
    assert failure.value.code == "unauthorized"


def capability(secret, scope):
    def encode(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = int(time.time())
    claims = encode(
        json.dumps(
            {"sub": "sdk-test", "scope": scope, "iat": now, "exp": now + 600}
        ).encode()
    )
    signature = hmac.new(bytes.fromhex(secret), claims.encode(), hashlib.sha256)
    return f"{claims}.{encode(signature.digest())}"


@pytest.mark.skipif(
    not os.environ.get("RUSHDB_TEST_ENGINE_CAPABILITY_SECRET"),
    reason="RUSHDB_TEST_ENGINE_CAPABILITY_SECRET is not set",
)
def test_write_with_read_only_capability_raises_rushdb_error(db):
    token = capability(os.environ["RUSHDB_TEST_ENGINE_CAPABILITY_SECRET"], "read")
    reader = RushDB(token, direct=True, engine_url=ENGINE_URL)
    assert reader.records.find({"labels": [BOOK]}).total >= 3
    with pytest.raises(RushDBError) as failure:
        reader.records.create(BOOK, {"title": "Refused"})
    assert failure.value.status == 401
    assert failure.value.code == "unauthorized"


# ── RushDB 3.0.14 (each feature skipped, or its fallback checked, on engines
# that do not advertise it) ──────────────────────────────────────────────────


def _supports(db, flag):
    return db.engine.supports(flag)


def test_typed_temporal_values(db):
    label = f"Event{RUN}"
    created = db.records.create(
        label,
        {
            "day": "2024-05-01",
            "at": "2024-05-01T12:30:00.25+02:00",
            "local": "2024-05-01T10:30:00",
            "opens": "10:30:00",
            "lasts": "P1DT2H",
        },
    )
    record = db.records.find_by_id(created.id)
    types = record.proptypes
    if not _supports(db, "typedTemporalValues"):
        # 3.0.13: a plain date and a zone-less date-time are UTC datetimes.
        assert types["day"] == "datetime" and types["local"] == "datetime"
        assert types["opens"] == "string" and types["lasts"] == "string"
        return
    assert {name: types[name] for name in ("day", "at", "local", "opens", "lasts")} == {
        "day": "date",
        "at": "datetime",
        "local": "localdatetime",
        "opens": "localtime",
        "lasts": "duration",
    }
    assert record["day"] == "2024-05-01"
    assert record["at"] == "2024-05-01T12:30:00.25+02:00"
    assert record["local"] == "2024-05-01T10:30:00"
    assert record["lasts"] == "P1DT2H"
    # Equality compares instants, whatever the offset.
    same = db.records.find(
        {"labels": [label], "where": {"at": "2024-05-01T10:30:00.25Z"}}
    )
    assert [r.id for r in same] == [created.id]
    bounds = db.records.find(
        {
            "labels": [label],
            "select": {"first": {"$min": "$record.day"}},
            "groupBy": ["first"],
        }
    )
    assert bounds.data[0]["first"] == "2024-05-01"
    schema = {
        prop["name"]: prop
        for item in db.ai.get_schema({"labels": [label]}).data
        for prop in item["properties"]
    }
    assert schema["day"]["type"] == "date" and schema["day"]["min"] == "2024-05-01"


def test_points_within_and_by_distance(db):
    if not _supports(db, "spatialFilters"):
        pytest.skip("engine does not advertise spatialFilters")
    from rushdb import distance_from, point, within_box, within_radius

    label = f"Cafe{RUN}"
    berlin = point(13.405, 52.52)
    db.records.create_many(
        label,
        [
            {"name": "Mitte", "location": point(13.404, 52.521)},
            {"name": "Kreuzberg", "location": point(13.41, 52.49)},
            {"name": "Potsdam", "location": point(13.06, 52.39)},
        ],
    )
    near = db.records.find(
        {
            "labels": [label],
            "where": {"location": within_radius(berlin, 5000)},
            "orderBy": {"location": distance_from(berlin)},
        }
    )
    assert [r["name"] for r in near] == ["Mitte", "Kreuzberg"]
    assert near.data[0].proptypes["location"] == "point"
    assert near.data[0]["location"]["coordinates"] == [13.404, 52.521]
    boxed = db.records.find(
        {
            "labels": [label],
            "where": {"location": within_box(point(13.0, 52.3), point(13.2, 52.45))},
        }
    )
    assert [r["name"] for r in boxed] == ["Potsdam"]


def test_catalog_warnings_and_strict_check(db):
    query = {"labels": [BOOK], "where": {"genre": "SF"}}
    if not _supports(db, "catalogCheck"):
        assert (
            db.records.find({**query, "context": {"check": "warn"}}).catalog_warnings
            == []
        )
        with pytest.raises(DirectModeError):
            db.records.find({**query, "context": {"check": "strict"}})
        return
    result = db.records.find(query)
    assert result.total == 0
    (warning,) = result.catalog_warnings
    assert warning["kind"] == "unknownValue" and warning["property"] == "genre"
    assert {"value": "sf", "reason": "spelling"}.items() <= warning["suggestions"][
        0
    ].items()
    assert (
        db.records.find({**query, "context": {"check": "off"}}).catalog_warnings == []
    )
    with pytest.raises(CatalogCheckError) as caught:
        db.records.find({**query, "context": {"check": "strict"}})
    assert caught.value.warnings and caught.value.code == "invalid_request"
    clean = db.records.find({"labels": [BOOK], "where": {"genre": "sf"}})
    assert clean.total == 2 and clean.catalog_warnings == []


def test_unique_index(db):
    label = f"User{RUN}"
    if not _supports(db, "uniqueIndexes"):
        with pytest.raises(DirectModeError):
            db.indexes.create({"label": label, "property": "email", "unique": True})
        return
    first = db.records.create(label, {"email": "ada@example.com"})
    created = db.indexes.create({"label": label, "property": "email", "unique": True})
    name = created.data["name"]
    assert created.data["kind"] == "unique" and created.data["unique"] is True
    deadline = time.time() + 30
    while time.time() < deadline:
        listed = {index["name"]: index for index in db.indexes.find().data}
        if listed[name]["status"] == "ready":
            break
        time.sleep(0.2)
    assert listed[name]["status"] == "ready"
    with pytest.raises(UniqueConstraintError) as caught:
        db.records.create(label, {"email": "ada@example.com"})
    assert caught.value.label == label and caught.value.record_id == first.id
    with pytest.raises(UniqueConstraintError):
        db.records.create_many(
            label, [{"email": "grace@example.com"}, {"email": "ada@example.com"}]
        )
    db.records.delete_by_id(first.id)
    db.records.create(label, {"email": "ada@example.com"})
    assert db.indexes.delete(name).data == {"deleted": True}
    duplicate = f"Dup{RUN}"
    db.records.create_many(duplicate, [{"code": "x"}, {"code": "x"}])
    with pytest.raises(RushDBError) as refused:
        db.indexes.create({"label": duplicate, "property": "code", "unique": True})
    assert refused.value.status == 409


def test_create_many_in_batches(db):
    label = f"Row{RUN}"
    result = db.records.create_many(
        label,
        [{"n": i} for i in range(12_000)],
        options={"returnResult": False},
        batch_size=5000,
    )
    assert result.total == 12_000
    assert db.records.find({"labels": [label], "limit": 1}).total == 12_000


def test_text_search_reads_its_own_writes(db):
    label = f"Note{RUN}"
    db.records.create(label, {"body": "seed"})
    created = db.text_indexes.create({"label": label, "property": "body"})
    name = created.data["name"]
    deadline = time.time() + 30
    while time.time() < deadline:
        if {i["name"]: i for i in db.text_indexes.find().data}[name][
            "status"
        ] == "ready":
            break
        time.sleep(0.2)
    db.records.create(label, {"body": "zeppelin overhead"})
    found = db.records.text_search(
        {"query": "zeppelin", "labels": [label]}, wait_for_pending=5
    )
    assert [r["body"] for r in found] == ["zeppelin overhead"]
    db.text_indexes.delete(name)
