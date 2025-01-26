"""Test cases for RushDB search query functionality."""

import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from rushdb.client import (
    RushDBClient,

    RushDBError
)

def load_env():
    """Load environment variables from .env file."""
    # Try to load from the root directory first
    root_env = Path(__file__).parent.parent / '.env'
    if root_env.exists():
        load_dotenv(root_env)
    else:
        # Fallback to default .env.example if no .env exists
        example_env = Path(__file__).parent.parent / '.env.example'
        if example_env.exists():
            load_dotenv(example_env)
            print("Warning: Using .env.example for testing. Create a .env file with your credentials for proper testing.")

class TestBase(unittest.TestCase):
    """Base test class with common setup."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        load_env()

        # Get configuration from environment variables
        cls.token = os.getenv('RUSHDB_TOKEN')
        cls.base_url = os.getenv('RUSHDB_URL', 'http://localhost:3000')

        if not cls.token:
            raise ValueError(
                "RUSHDB_TOKEN environment variable is not set. "
                "Please create a .env file with your credentials. "
                "You can use .env.example as a template."
            )

    def setUp(self):
        """Set up test client."""
        self.client = RushDBClient(self.token, base_url=self.base_url)

        # Verify connection
        try:
            if not self.client.ping():
                self.skipTest(f"Could not connect to RushDB at {self.base_url}")
        except RushDBError as e:
            self.skipTest(f"RushDB connection error: {str(e)}")

class TestSearchQuery(TestBase):
    def test_basic_equality_search(self):
        """Test basic equality search"""
        query = {
            "where": {
                "name": "John"  # Implicit equality
            }
        }
        self.client.records.find(query)

    def test_basic_comparison_operators(self):
        """Test basic comparison operators"""
        query = {
            "where": {
                "age": {"$gt": 25},
                "score": {"$lte": 100},
                "status": {"$ne": "inactive"}
            }
        }
        self.client.records.find(query)

    def test_string_operations(self):
        """Test string-specific operations"""
        query = {
            "where": {
                "name": {"$startsWith": "J"},
                "email": {"$contains": "@example.com"},
                "code": {"$endsWith": "XYZ"}
            }
        }
        self.client.records.find(query)

    def test_array_operations(self):
        """Test array operations (in/not in)"""
        query = {
            "where": {
                "status": {"$in": ["active", "pending"]},
                "category": {"$nin": ["archived", "deleted"]},
                "tags": {"$contains": "important"}
            }
        }
        self.client.records.find(query)

    def test_logical_operators(self):
        """Test logical operators (AND, OR, NOT)"""
        query = {
            "where": {
                "$and": [
                    {"age": {"$gte": 18}},
                    {"status": "active"}
                ],
                "$or": [
                    {"role": "admin"},
                    {"permissions": {"$contains": "write"}}
                ]
            }
        }
        self.client.records.find(query)

    def test_nested_logical_operators(self):
        """Test nested logical operators"""
        query = {
            "where": {
                "$or": [
                    {
                        "$and": [
                            {"age": {"$gte": 18}},
                            {"age": {"$lt": 65}},
                            {"status": "employed"}
                        ]
                    },
                    {
                        "$and": [
                            {"age": {"$gte": 65}},
                            {"status": "retired"},
                            {"pension": {"$exists": True}}
                        ]
                    }
                ]
            }
        }
        self.client.records.find(query)

    def test_complex_nested_relations(self):
        """Test complex nested relations"""
        query = {
            "where": {
                "EMPLOYEE": {
                    "$and": [
                        {"position": {"$contains": "Manager"}},
                        {
                            "DEPARTMENT": {
                                "name": "Engineering",
                                "COMPANY": {
                                    "industry": "Technology",
                                    "revenue": {"$gt": 1000000}
                                }
                            }
                        }
                    ]
                }
            },
            "orderBy": {"created_at": "desc"},
            "limit": 10
        }
        self.client.records.find(query)

    def test_query_builder_simple(self):
        """Test simple query conditions"""
        query = {
            "where": {
                "$and": [
                    {"age": {"$gt": 25}},
                    {"status": "active"}
                ]
            }
        }
        self.client.records.find(query)

    def test_query_builder_complex(self):
        """Test complex query conditions"""
        query = {
            "where": {
                "$or": [
                    {
                        "$and": [
                            {"age": {"$gte": 18}},
                            {"age": {"$lt": 65}},
                            {"status": "employed"}
                        ]
                    },
                    {
                        "$and": [
                            {"age": {"$gte": 65}},
                            {"status": "retired"}
                        ]
                    }
                ]
            },
            "orderBy": {"age": "desc"},
            "limit": 20
        }
        self.client.records.find(query)

    def test_advanced_graph_traversal(self):
        """Test advanced graph traversal with multiple relations"""
        query = {
            "where": {
                "USER": {
                    "$and": [
                        {"role": "customer"},
                        {
                            "PLACED_ORDER": {
                                "$and": [
                                    {"status": "completed"},
                                    {"total": {"$gt": 100}},
                                    {
                                        "CONTAINS_PRODUCT": {
                                            "$and": [
                                                {"category": "electronics"},
                                                {"price": {"$gt": 50}},
                                                {
                                                    "MANUFACTURED_BY": {
                                                        "country": "Japan",
                                                        "rating": {"$gte": 4}
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
        self.client.records.find(query)

    def test_complex_query_with_all_features(self):
        """Test combining all query features"""
        query = {
            "labels": ["User", "Customer"],
            "where": {
                "$and": [
                    {
                        "$or": [
                            {"age": {"$gte": 18}},
                            {
                                "$and": [
                                    {"guardian": {"$exists": True}},
                                    {"guardian_approved": True}
                                ]
                            }
                        ]
                    },
                    {"status": {"$in": ["active", "pending"]}},
                    {"email": {"$endsWith": "@company.com"}},
                    {
                        "BELONGS_TO_GROUP": {
                            "$and": [
                                {"name": {"$startsWith": "Premium"}},
                                {"status": "active"},
                                {
                                    "HAS_SUBSCRIPTION": {
                                        "$and": [
                                            {"type": "premium"},
                                            {"expires_at": {"$gt": "2024-01-01"}},
                                            {
                                                "INCLUDES_FEATURES": {
                                                    "name": {"$in": ["feature1", "feature2"]},
                                                    "enabled": True
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
            "orderBy": {
                "created_at": "desc",
                "name": "asc"
            },
            "skip": 0,
            "limit": 50
        }
        self.client.records.find(query)

if __name__ == '__main__':
    unittest.main() 