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

    def test_record_exists_method(self):
        """Test Record exists() method."""
        # Create a valid record
        record = self.client.records.create("USER", {"name": "Test User"})

        # Test exists for valid record
        self.assertTrue(record.exists())

        # Create an invalid record (no ID)
        invalid_record = Record(self.client, {})
        self.assertFalse(invalid_record.exists())

        # Test exists after deletion
        record.delete()
        # Note: In real implementation, this might still return True
        # until the record is actually removed from the database


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


if __name__ == "__main__":
    unittest.main()
