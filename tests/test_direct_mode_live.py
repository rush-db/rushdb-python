"""Direct mode against a real standalone engine. Runs only when
``RUSHDB_TEST_ENGINE_URL`` (and ``RUSHDB_TEST_ENGINE_TOKEN``, default
``local-token``) point at a single-tenant ``rushdbd`` started with
``--languages cypher``::

    rushdbd --data-dir /tmp/rushdb-test --port 3877 --languages cypher
    RUSHDB_TEST_ENGINE_URL=http://127.0.0.1:3877 pytest tests/test_direct_mode_live.py
"""

import os
import time
import uuid

import pytest

from rushdb import CloudOnlyError, DirectModeError, RushDB

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
