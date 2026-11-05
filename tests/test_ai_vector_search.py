import unittest
import warnings
from unittest.mock import Mock

from src.rushdb.api.ai import AIAPI
from src.rushdb.api.records import RecordsAPI
from src.rushdb.models.result import RecordSearchResult


class TestVectorAndSmartSearch(unittest.TestCase):
    def test_records_vector_search_posts_to_ai_search(self):
        client = Mock()
        client._make_request.return_value = {
            "success": True,
            "total": 1,
            "data": [
                {"__id": "doc_1", "__label": "Doc", "title": "Alpha", "__score": 0.91}
            ],
        }

        result = RecordsAPI(client).vector_search(
            {
                "labels": ["Doc"],
                "propertyName": "description",
                "queryVector": [1, 0, 0],
                "limit": 5,
            }
        )

        client._make_request.assert_called_once_with(
            "POST",
            "/ai/search",
            {
                "labels": ["Doc"],
                "propertyName": "description",
                "queryVector": [1, 0, 0],
                "limit": 5,
            },
            None,
        )
        self.assertIsInstance(result, RecordSearchResult)
        self.assertEqual(result.total, 1)
        self.assertEqual(result[0].get("title"), "Alpha")
        self.assertEqual(result[0].score, 0.91)

    def test_ai_search_prompt_generates_and_runs_sql(self):
        client = Mock()
        client._make_request.side_effect = [
            {
                "success": True,
                "data": {
                    "sql": 'SELECT __id FROM "Pilot" WHERE "ship" = \'Falcon\'',
                    "name": "Falcon pilots",
                    "warnings": ["ambiguous ship name"],
                },
            },
            {
                "success": True,
                "total": 1,
                "data": [{"__id": "pilot_1", "__label": "Pilot", "name": "Han"}],
            },
        ]

        result = AIAPI(client).search("Who are piloting Falcon?", limit=10)

        self.assertEqual(
            client._make_request.call_args_list[0].args,
            ("POST", "/ai/sql-search", {"prompt": "Who are piloting Falcon?"}),
        )
        sql = 'SELECT __id FROM "Pilot" WHERE "ship" = \'Falcon\''
        self.assertEqual(
            client._make_request.call_args_list[1].args,
            ("POST", "/records/sql-search", {"sql": sql, "skip": 0, "limit": 10}),
        )
        self.assertEqual(result.sql, sql)
        self.assertEqual(result.name, "Falcon pilots")
        self.assertEqual(result.warnings, ["ambiguous ship name"])
        self.assertEqual(result.search_query, {})
        self.assertEqual(result[0].get("name"), "Han")

    def test_smart_search_result_pages_through_its_sql(self):
        client = Mock()
        client._make_request.return_value = {"success": True, "total": 3, "data": []}
        client.ai = AIAPI(client)

        first = client.ai.run_sql('SELECT __id FROM "Pilot"', limit=2)
        self.assertEqual((first.skip, first.limit), (0, 2))
        second = first.next()

        self.assertEqual(
            client._make_request.call_args_list[1].args,
            (
                "POST",
                "/records/sql-search",
                {"sql": 'SELECT __id FROM "Pilot"', "skip": 2, "limit": 2},
            ),
        )
        self.assertEqual((second.skip, second.limit, second.sql), (2, 2, first.sql))

    def test_ai_search_dict_is_deprecated_vector_search_alias(self):
        client = Mock()
        client.records = Mock()
        client.records.vector_search.return_value = RecordSearchResult([], total=0)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = AIAPI(client).search(
                {"labels": ["Doc"], "propertyName": "body", "query": "graph"}
            )

        client.records.vector_search.assert_called_once_with(
            {"labels": ["Doc"], "propertyName": "body", "query": "graph"},
            transaction=None,
        )
        self.assertIsInstance(result, RecordSearchResult)
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, DeprecationWarning)


if __name__ == "__main__":
    unittest.main()
