from unittest.mock import Mock

from src.rushdb.api.records import RecordsAPI
from src.rushdb.api.relationship_patterns import RelationshipPatternsAPI
from src.rushdb.api.relationships import RelationsAPI


def test_relationships_exposes_patterns_namespace():
    client = Mock()

    relationships = RelationsAPI(client)

    assert isinstance(relationships.patterns, RelationshipPatternsAPI)


def test_list_relationship_patterns():
    client = Mock()
    client._make_request.return_value = {
        "data": {"patterns": [], "relationships": [], "analysis": {"status": "idle"}},
        "success": True,
    }

    response = RelationsAPI(client).patterns.list()

    client._make_request.assert_called_once_with("GET", "/relationships/patterns")
    assert response.data["patterns"] == []
    assert response.data["analysis"]["status"] == "idle"


def test_mutate_relationship_patterns():
    client = Mock()
    client._make_request.return_value = {"data": {"deleted": True}, "success": True}
    patterns = RelationsAPI(client).patterns

    patterns.analyze()
    client._make_request.assert_called_with(
        "POST", "/relationships/patterns/analyze", {}
    )

    patterns.approve("pattern-id")
    client._make_request.assert_called_with(
        "POST", "/relationships/patterns/pattern-id/approve", {}
    )

    patterns.ignore("pattern-id")
    client._make_request.assert_called_with(
        "POST", "/relationships/patterns/pattern-id/ignore", {}
    )

    patterns.delete("pattern-id", delete_existing=True)
    client._make_request.assert_called_with(
        "DELETE",
        "/relationships/patterns/pattern-id",
        params={"deleteExisting": "true"},
    )


def test_relationships_find_uses_edge_where_and_endpoint_filters():
    client = Mock()
    edge = {
        "sourceId": "user-1",
        "sourceLabel": "USER",
        "targetId": "order-1",
        "targetLabel": "ORDER",
        "type": "ORDERED",
        "direction": "out",
        "properties": {"confidence": 0.9},
    }
    client._make_request.return_value = {"data": [edge], "total": 1}

    search_query = {
        "source": {"labels": ["USER"], "where": {"status": "active"}},
        "target": {"labels": ["ORDER"]},
        "where": {"type": "ORDERED", "confidence": {"$gte": 0.8}},
        "limit": 25,
    }

    response = RelationsAPI(client).find(search_query)

    # Pagination travels in the body, same as records search.
    client._make_request.assert_called_once_with(
        method="POST",
        path="/relationships/search",
        data=search_query,
        headers=None,
    )
    assert response.total == 1
    assert list(response) == [edge]
    assert response[0]["properties"]["confidence"] == 0.9


def test_relationships_find_explicit_pagination_wins_over_query_limit():
    client = Mock()
    client._make_request.return_value = {"data": [], "total": 0}

    search_query = {"where": {"type": "ORDERED"}, "limit": 25}
    RelationsAPI(client).find(search_query, pagination={"limit": 10, "skip": 5})

    # The pagination argument overrides limit/skip in the body, leaving the
    # caller's search_query object untouched.
    client._make_request.assert_called_once_with(
        method="POST",
        path="/relationships/search",
        data={"where": {"type": "ORDERED"}, "limit": 10, "skip": 5},
        headers=None,
    )
    assert search_query == {"where": {"type": "ORDERED"}, "limit": 25}


def test_relationships_create_many_forwards_edge_properties():
    client = Mock()
    client._make_request.return_value = {"success": True}

    RelationsAPI(client).create_many(
        source={"label": "USER", "key": "id"},
        target={"label": "ORDER", "key": "userId"},
        type="ORDERED",
        direction="out",
        properties={"source": "import", "confidence": 0.9},
    )

    client._make_request.assert_called_once_with(
        "POST",
        "/relationships/create-many",
        {
            "source": {"label": "USER", "key": "id"},
            "target": {"label": "ORDER", "key": "userId"},
            "type": "ORDERED",
            "direction": "out",
            "properties": {"source": "import", "confidence": 0.9},
        },
        None,
    )


def test_records_attach_forwards_edge_properties():
    client = Mock()
    client._make_request.return_value = {"success": True}

    RecordsAPI(client).attach(
        source="source-id",
        target="target-id",
        options={
            "type": "RELATED_TO",
            "direction": "out",
            "properties": {"source": "test"},
        },
    )

    client._make_request.assert_called_once_with(
        "POST",
        "/relationships/source-id",
        {
            "targetIds": ["target-id"],
            "type": "RELATED_TO",
            "direction": "out",
            "properties": {"source": "test"},
        },
        None,
    )
