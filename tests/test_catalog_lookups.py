"""Catalog lookups send their bodies to the platform routes the TypeScript SDK
uses, with snake_case options as camelCase keys and unset ones left out."""

import unittest
from unittest.mock import Mock

from rushdb.api.ai import AIAPI
from rushdb.api.properties import PropertiesAPI
from rushdb.models.api_response import ApiResponse


def _client(data):
    client = Mock()
    client._make_request.return_value = {"success": True, "data": data}
    return client


class TestCatalogLookups(unittest.TestCase):
    def test_search_values_posts_the_search(self):
        data = {
            "matches": [
                {"label": "Hero", "property": "name", "value": "Spider-Man", "count": 3}
            ],
            "total": 1,
        }
        client = _client(data)

        result = AIAPI(client).search_values(
            "spiderman",
            match="similar",
            labels=["Hero"],
            limit=5,
            min_similarity=0.7,
            case_sensitive=True,
        )

        client._make_request.assert_called_once_with(
            "POST",
            "/ai/values/search",
            {
                "text": "spiderman",
                "match": "similar",
                "caseSensitive": True,
                "minSimilarity": 0.7,
                "labels": ["Hero"],
                "limit": 5,
            },
        )
        self.assertIsInstance(result, ApiResponse)
        self.assertEqual(result.data, data)

    def test_search_values_sends_only_the_text_by_default(self):
        client = _client({"matches": [], "total": 0})
        AIAPI(client).search_values("positive")
        client._make_request.assert_called_once_with(
            "POST", "/ai/values/search", {"text": "positive"}
        )

    def test_get_schema_summary_posts_labels_and_few_values(self):
        client = _client([{"name": "Patient", "recordsCount": 2, "properties": []}])

        result = AIAPI(client).get_schema_summary(labels=["Patient"], few_values=5)

        client._make_request.assert_called_once_with(
            "POST", "/ai/schema/summary", {"labels": ["Patient"], "fewValues": 5}
        )
        self.assertEqual(result.data[0]["name"], "Patient")

    def test_get_schema_summary_without_options_posts_an_empty_body(self):
        client = _client([])
        AIAPI(client).get_schema_summary()
        client._make_request.assert_called_once_with("POST", "/ai/schema/summary", {})

    def test_resolve_names_posts_the_name(self):
        client = _client([{"label": "Patient", "property": "Birthday", "score": 0.9}])

        result = AIAPI(client).resolve_names("patients.birthdate", limit=3)

        client._make_request.assert_called_once_with(
            "POST", "/ai/schema/names", {"text": "patients.birthdate", "limit": 3}
        )
        self.assertEqual(result.data[0]["property"], "Birthday")

    def test_get_join_candidates_posts_labels_and_min_confidence(self):
        candidate = {
            "source": {"label": "Order", "property": "customerId"},
            "target": {"label": "Customer", "property": "id"},
            "reasons": ["name", "values"],
            "relationshipType": "CUSTOMER",
            "confidence": 0.9,
            "evidence": {"coverage": 1.0},
            "rationale": "customerId values are Customer ids",
        }
        client = _client([candidate])

        result = AIAPI(client).get_join_candidates(labels=["Order"], min_confidence=0.8)

        client._make_request.assert_called_once_with(
            "POST",
            "/ai/schema/join-candidates",
            {"labels": ["Order"], "minConfidence": 0.8},
        )
        self.assertEqual(result.data, [candidate])

    def test_property_values_sends_the_value_search(self):
        client = _client({"values": ["+"], "counts": [4]})

        PropertiesAPI(client).values(
            "prop-1",
            {"labels": ["Test"], "orderBy": "desc"},
            query="positive",
            match="contains",
            limit=10,
            domain_on_miss=20,
            min_similarity=0.5,
        )

        client._make_request.assert_called_once_with(
            "POST",
            "/properties/prop-1/values",
            {
                "labels": ["Test"],
                "orderBy": "desc",
                "query": "positive",
                "match": "contains",
                "limit": 10,
                "domainOnMiss": 20,
                "minSimilarity": 0.5,
            },
            None,
        )

    def test_property_values_keeps_a_search_query_dict(self):
        client = _client({"values": []})
        search_query = {"query": "pos", "domainOnMiss": 5}

        PropertiesAPI(client).values("prop-1", search_query)

        client._make_request.assert_called_once_with(
            "POST",
            "/properties/prop-1/values",
            {"query": "pos", "domainOnMiss": 5},
            None,
        )
        self.assertEqual(search_query, {"query": "pos", "domainOnMiss": 5})


if __name__ == "__main__":
    unittest.main()
