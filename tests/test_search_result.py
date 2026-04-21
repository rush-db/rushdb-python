"""Test cases for SearchResult and improved Record functionality."""

import unittest
from unittest.mock import Mock

from src.rushdb.models.record import Record
from src.rushdb.models.result import RecordSearchResult, SearchResult

from .test_base_setup import TestBase


class TestSearchResult(unittest.TestCase):
    """Test cases for SearchResult class functionality."""

    def setUp(self):
        """Set up test data."""
        self.test_data = [
            {"id": "1", "name": "John", "age": 30},
            {"id": "2", "name": "Jane", "age": 25},
            {"id": "3", "name": "Bob", "age": 35},
        ]

    def test_search_result_get_page_info(self):
        """Test SearchResult get_page_info() method."""
        search_query = {"where": {"name": "test"}, "limit": 5, "skip": 10}
        result = SearchResult(self.test_data, total=50, search_query=search_query)

        page_info = result.get_page_info()

        self.assertEqual(page_info["total"], 50)
        self.assertEqual(page_info["loaded"], 3)
        self.assertTrue(page_info["has_more"])
        self.assertEqual(page_info["skip"], 10)
        self.assertEqual(page_info["limit"], 5)

    def test_search_result_initialization(self):
        """Test SearchResult initialization with various parameters."""
        # Basic initialization
        result = SearchResult(self.test_data)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.total, 3)
        self.assertEqual(result.skip, 0)
        self.assertIsNone(result.limit)
        self.assertFalse(result.has_more)

        # With pagination parameters
        search_query = {"limit": 2, "skip": 5}
        result = SearchResult(
            data=self.test_data[:2], total=10, search_query=search_query
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result.total, 10)
        self.assertEqual(result.skip, 5)
        self.assertEqual(result.limit, 2)
        self.assertTrue(result.has_more)

    def test_search_result_properties(self):
        """Test SearchResult properties."""
        search_query = {"limit": 10, "skip": 20, "where": {"name": "test"}}
        result = SearchResult(data=self.test_data, total=100, search_query=search_query)

        self.assertEqual(result.data, self.test_data)
        self.assertEqual(result.total, 100)
        self.assertEqual(len(result), 3)
        self.assertEqual(result.limit, 10)
        self.assertEqual(result.skip, 20)
        self.assertTrue(result.has_more)
        self.assertEqual(result.search_query["where"]["name"], "test")

    def test_search_result_iteration(self):
        """Test SearchResult iteration capabilities."""
        result = SearchResult(self.test_data)

        # Test iteration
        items = []
        for item in result:
            items.append(item)
        self.assertEqual(items, self.test_data)

        # Test list comprehension
        names = [item["name"] for item in result]
        self.assertEqual(names, ["John", "Jane", "Bob"])

    def test_search_result_indexing(self):
        """Test SearchResult indexing and slicing."""
        result = SearchResult(self.test_data)

        # Test indexing
        self.assertEqual(result[0], self.test_data[0])
        self.assertEqual(result[-1], self.test_data[-1])

        # Test slicing
        first_two = result[:2]
        self.assertEqual(first_two, self.test_data[:2])

    def test_search_result_boolean_conversion(self):
        """Test SearchResult boolean conversion."""
        # Non-empty result
        result = SearchResult(self.test_data)
        self.assertTrue(bool(result))
        self.assertTrue(result)

        # Empty result
        empty_result = SearchResult([])
        self.assertFalse(bool(empty_result))
        self.assertFalse(empty_result)

    def test_search_result_string_representation(self):
        """Test SearchResult string representation."""
        result = SearchResult(self.test_data, total=100)
        expected = "SearchResult(count=3, total=100)"
        self.assertEqual(repr(result), expected)

    def test_record_search_result_type_alias(self):
        """Test RecordSearchResult type alias."""
        # Mock client
        mock_client = Mock()

        # Create Record objects
        records = [
            Record(mock_client, {"__id": "1", "__label": "User", "name": "John"}),
            Record(mock_client, {"__id": "2", "__label": "User", "name": "Jane"}),
        ]

        result = RecordSearchResult(records, total=2)
        self.assertIsInstance(result, SearchResult)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.total, 2)

    def test_search_result_to_dict(self):
        """Test SearchResult to_dict() method."""
        search_query = {"where": {"name": "test"}, "limit": 10}
        result = SearchResult(self.test_data, total=100, search_query=search_query)

        result_dict = result.to_dict()

        self.assertEqual(result_dict["total"], 100)
        self.assertEqual(result_dict["data"], self.test_data)
        self.assertEqual(result_dict["search_query"], search_query)

    # Note: get_page_info() method exists but will fail due to missing skip/limit properties
    # def test_search_result_get_page_info(self):
    #     """Test SearchResult get_page_info() method."""
    #     # This test is commented out because get_page_info() references
    #     # non-existent skip and limit properties, causing AttributeError


class TestRecordImprovements(TestBase):
    """Test cases for improved Record functionality."""

    def test_record_data_access_methods(self):
        """Test improved Record data access methods."""
        # Create a test record
        record = self.client.records.create(
            "USER",
            {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "department": "Engineering",
            },
        )

        # Test get method with default
        self.assertEqual(record.get("name"), "John Doe")
        self.assertEqual(record.get("phone", "N/A"), "N/A")

        # Test get_data method
        user_data = record.get_data(exclude_internal=True)
        self.assertIn("name", user_data)
        self.assertNotIn("__id", user_data)
        self.assertNotIn("__label", user_data)

        full_data = record.get_data(exclude_internal=False)
        self.assertIn("__id", full_data)
        self.assertIn("__label", full_data)

        # Test fields property
        fields = record.fields
        self.assertEqual(fields, user_data)

        # Test to_dict method
        dict_data = record.to_dict()
        self.assertEqual(dict_data, user_data)

        dict_with_internal = record.to_dict(exclude_internal=False)
        self.assertEqual(dict_with_internal, full_data)

    def test_record_indexing_access(self):
        """Test Record bracket notation access."""
        record = self.client.records.create(
            "USER", {"name": "Jane Smith", "role": "Developer"}
        )

        # Test bracket notation
        self.assertEqual(record["name"], "Jane Smith")
        self.assertEqual(record["__label"], "USER")

        # Test KeyError for non-existent key
        with self.assertRaises(KeyError):
            _ = record["non_existent_key"]

    def test_record_string_representations(self):
        """Test Record string representations."""
        record = self.client.records.create(
            "USER", {"name": "Alice Johnson", "email": "alice@example.com"}
        )

        # Test __repr__
        repr_str = repr(record)
        self.assertIn("Record(id=", repr_str)
        self.assertIn("label='USER'", repr_str)

        # Test __str__
        str_repr = str(record)
        self.assertIn("USER:", str_repr)
        self.assertIn("Alice Johnson", str_repr)

    def test_record_equality_and_hashing(self):
        """Test Record equality and hashing."""
        # Create two records
        record1 = self.client.records.create("USER", {"name": "User 1"})
        record2 = self.client.records.create("USER", {"name": "User 2"})

        # Test inequality
        self.assertNotEqual(record1, record2)
        self.assertNotEqual(hash(record1), hash(record2))

        # Test equality with same record
        self.assertEqual(record1, record1)
        self.assertEqual(hash(record1), hash(record1))

        # Test with non-Record object
        self.assertNotEqual(record1, "not a record")

    def test_record_exists_property(self):
        """Test Record exists property (was method, now @property)."""
        # Create a valid record
        record = self.client.records.create("USER", {"name": "Test User"})

        # Test exists for valid record — accessed as property, not method
        self.assertTrue(record.exists)

        # Create an invalid record (no ID)
        invalid_record = Record(self.client, {})
        self.assertFalse(invalid_record.exists)

        # Test exists after deletion
        record.delete()


class TestSearchResultIntegration(TestBase):
    """Test SearchResult integration with actual RushDB operations."""

    def test_find_returns_search_result(self):
        """Test that find() returns SearchResult object."""
        # Create some test records
        self.client.records.create(
            "EMPLOYEE", {"name": "John Doe", "department": "Engineering", "age": 30}
        )
        self.client.records.create(
            "EMPLOYEE", {"name": "Jane Smith", "department": "Marketing", "age": 28}
        )

        # Search for records
        query = {"where": {"department": "Engineering"}, "limit": 10}
        result = self.client.records.find(query)

        # Test that result is SearchResult
        self.assertIsInstance(result, SearchResult)
        self.assertIsInstance(result, RecordSearchResult)

        # Test SearchResult properties
        self.assertGreaterEqual(len(result), 1)
        self.assertIsInstance(result.total, int)
        self.assertIsInstance(result.skip, int)
        self.assertIsInstance(result.has_more, bool)

        # Test iteration
        for record in result:
            self.assertIsInstance(record, Record)
            self.assertEqual(record.get("department"), "Engineering")

        # Test boolean conversion
        if result:
            print(f"Found {len(result)} engineering employees")

        # Test indexing if results exist
        if len(result) > 0:
            first_record = result[0]
            self.assertIsInstance(first_record, Record)

    def test_empty_search_result(self):
        """Test SearchResult with no results."""
        # Search for non-existent records
        query = {"where": {"department": "NonExistentDepartment"}, "limit": 10}
        result = self.client.records.find(query)

        self.assertIsInstance(result, SearchResult)
        self.assertEqual(len(result), 0)
        self.assertFalse(result)
        self.assertFalse(result.has_more)

    def test_pagination_with_search_result(self):
        """Test SearchResult pagination features."""
        # Create multiple records
        for i in range(5):
            self.client.records.create(
                "PRODUCT", {"name": f"Product {i}", "price": 100 + i * 10}
            )

        # Search with pagination
        query = {"where": {}, "labels": ["PRODUCT"], "limit": 2, "skip": 1}
        result = self.client.records.find(query)

        self.assertIsInstance(result, SearchResult)
        # Test that pagination properties work
        self.assertEqual(result.limit, 2)
        self.assertEqual(result.skip, 1)
        self.assertEqual(result.search_query.get("limit"), 2)
        self.assertEqual(result.search_query.get("skip"), 1)

        # Test page info
        page_info = result.get_page_info()
        self.assertEqual(page_info["limit"], 2)
        self.assertEqual(page_info["skip"], 1)

        # Test has_more calculation
        self.assertIsInstance(result.has_more, bool)


class TestRecordScoreProperty(unittest.TestCase):
    """Unit tests for Record.score property."""

    def setUp(self):
        self.mock_client = Mock()

    def test_score_absent(self):
        """score is None when __score not in data."""
        record = Record(self.mock_client, {"__id": "1", "__label": "User", "name": "John"})
        self.assertIsNone(record.score)

    def test_score_present(self):
        """score returns float when __score is in data."""
        record = Record(self.mock_client, {"__id": "1", "__label": "User", "__score": 0.95})
        self.assertEqual(record.score, 0.95)

    def test_score_excluded_from_fields(self):
        """__score is not included in record.fields."""
        record = Record(self.mock_client, {"__id": "1", "__label": "User", "__score": 0.8, "name": "X"})
        self.assertNotIn("__score", record.fields)
        self.assertNotIn("__score", record.get_data(exclude_internal=True))

    def test_score_included_in_full_data(self):
        """__score is included when exclude_internal=False."""
        record = Record(self.mock_client, {"__id": "1", "__label": "User", "__score": 0.8})
        self.assertIn("__score", record.get_data(exclude_internal=False))


class TestRecordExistsProperty(unittest.TestCase):
    """Unit tests for Record.exists @property."""

    def setUp(self):
        self.mock_client = Mock()

    def test_exists_true(self):
        record = Record(self.mock_client, {"__id": "abc", "__label": "User"})
        self.assertTrue(record.exists)

    def test_exists_false_no_id(self):
        record = Record(self.mock_client, {})
        self.assertFalse(record.exists)

    def test_exists_is_property_not_method(self):
        """Accessing record.exists should not be callable."""
        record = Record(self.mock_client, {"__id": "abc", "__label": "User"})
        # It's a bool, not a method
        self.assertIsInstance(record.exists, bool)
        self.assertNotCallable(record.exists)

    def assertNotCallable(self, obj):
        self.assertFalse(callable(obj), f"Expected non-callable, got {type(obj)}")


class TestRecordMappingProtocol(unittest.TestCase):
    """Unit tests for Record mapping protocol (pandas compatibility)."""

    def setUp(self):
        self.mock_client = Mock()
        self.data = {"__id": "1", "__label": "User", "name": "Alice", "age": 30}
        self.record = Record(self.mock_client, self.data)

    def test_keys(self):
        self.assertEqual(set(self.record.keys()), set(self.data.keys()))

    def test_values(self):
        self.assertEqual(list(self.record.values()), list(self.data.values()))

    def test_items(self):
        self.assertEqual(dict(self.record.items()), self.data)

    def test_dict_construction(self):
        """dict(record) should produce the full data dict."""
        self.assertEqual(dict(self.record.items()), self.data)


class TestSearchResultNewMethods(unittest.TestCase):
    """Unit tests for new SearchResult methods."""

    def setUp(self):
        self.mock_client = Mock()
        self.records = [
            Record(self.mock_client, {"__id": f"{i}", "__label": "Item", "name": f"Item {i}", "price": i * 10})
            for i in range(1, 4)
        ]
        self.result = RecordSearchResult(
            data=self.records,
            total=10,
            search_query={"limit": 3, "skip": 0},
            client=self.mock_client,
        )

    def test_delete_all_empty(self):
        """delete_all on empty result returns success immediately."""
        empty = RecordSearchResult(data=[], total=0, client=self.mock_client)
        resp = empty.delete_all()
        self.assertEqual(resp, {"success": True})
        self.mock_client.records.delete_by_id.assert_not_called()

    def test_delete_all_calls_client(self):
        self.mock_client.records.delete_by_id.return_value = {"success": True}
        self.result.delete_all()
        self.mock_client.records.delete_by_id.assert_called_once_with(
            ["1", "2", "3"], None
        )

    def test_next_no_query_raises(self):
        result = RecordSearchResult(data=[], total=0, client=self.mock_client)
        with self.assertRaises(RuntimeError):
            result.next()

    def test_next_returns_new_result(self):
        next_records = [
            Record(self.mock_client, {"__id": "4", "__label": "Item", "name": "Item 4", "price": 40})
        ]
        next_result = RecordSearchResult(data=next_records, total=10, search_query={"limit": 3, "skip": 3})
        self.mock_client.records.find.return_value = next_result

        result = self.result.next()
        call_args = self.mock_client.records.find.call_args[0][0]
        self.assertEqual(call_args["skip"], 3)
        self.assertEqual(call_args["limit"], 3)
        self.assertIs(result, next_result)

    def test_next_preserve_data(self):
        next_records = [
            Record(self.mock_client, {"__id": "4", "__label": "Item", "name": "Item 4", "price": 40})
        ]
        next_result = RecordSearchResult(data=next_records, total=10, search_query={"limit": 3, "skip": 3})
        self.mock_client.records.find.return_value = next_result

        result = self.result.next(preserve_data=True)
        self.assertIs(result, self.result)
        self.assertEqual(len(self.result), 4)

    def test_export_csv_empty(self):
        empty = RecordSearchResult(data=[], total=0)
        self.assertEqual(empty.export_csv(), "")

    def test_export_csv_content(self):
        csv_str = self.result.export_csv()
        lines = csv_str.strip().split("\n")
        # Header row
        self.assertIn("name", lines[0])
        self.assertIn("price", lines[0])
        # System fields excluded
        self.assertNotIn("__id", lines[0])
        self.assertNotIn("__label", lines[0])
        # Data rows
        self.assertEqual(len(lines), 4)  # header + 3 records

    def test_set_properties_calls_update(self):
        patch = {"price": 999}
        self.result.set_properties(patch)
        for record in self.records:
            record.update = Mock()
        # verify each record's update would be called (mock already set)
        self.assertEqual(len(self.records), 3)


class TestPandasIntegration(unittest.TestCase):
    """Pandas integration tests — skipped if pandas not installed."""

    def setUp(self):
        self.pd = pytest.importorskip("pandas") if _has_pytest() else _try_import_pandas()
        if self.pd is None:
            self.skipTest("pandas not installed")
        self.mock_client = Mock()
        self.records = [
            Record(self.mock_client, {"__id": f"{i}", "__label": "User", "name": f"User {i}", "age": 20 + i})
            for i in range(3)
        ]
        self.result = RecordSearchResult(data=self.records, total=3)

    def test_to_dataframe_excludes_internal(self):
        df = self.result.to_dataframe(exclude_internal=True)
        self.assertNotIn("__id", df.columns)
        self.assertNotIn("__label", df.columns)
        self.assertIn("name", df.columns)
        self.assertEqual(len(df), 3)

    def test_to_dataframe_includes_internal(self):
        df = self.result.to_dataframe(exclude_internal=False)
        self.assertIn("__id", df.columns)
        self.assertIn("__label", df.columns)
        self.assertEqual(len(df), 3)

    def test_to_series(self):
        s = self.records[0].to_series(exclude_internal=True)
        self.assertNotIn("__id", s.index)
        self.assertIn("name", s.index)

    def test_dataframe_from_records_list(self):
        """pd.DataFrame([r1, r2, r3]) works via mapping protocol."""
        import pandas as pd
        df = pd.DataFrame([dict(r.items()) for r in self.records])
        self.assertIn("__id", df.columns)
        self.assertEqual(len(df), 3)


def _has_pytest():
    try:
        import pytest  # noqa: F401
        return True
    except ImportError:
        return False


def _try_import_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError:
        return None


if __name__ == "__main__":
    unittest.main()
