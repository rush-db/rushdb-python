from unittest.mock import Mock

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
