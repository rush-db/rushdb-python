"""Test cases for RushDB search query functionality."""

import unittest

from .test_base_setup import TestBase


class TestSearchQuery(TestBase):
    def test_basic_equality_search(self):
        """Test basic equality search"""
        query = {"where": {"name": "John Doe"}}  # Implicit equality
        result = self.client.records.find(query)

        # Test that result is SearchResult
        self.assertIsNotNone(result)
        print(f"Search returned {len(result)} results out of {result.total} total")

        # Test iteration
        for record in result:
            print(f"Found record: {record.get('name', 'Unknown')}")

        # Test boolean check
        if result:
            print("Search found results")
        else:
            print("No results found")

    def test_empty_criteria_search(self):
        """Test basic equality search"""

        result = self.client.records.find()

        # Test that result is SearchResult
        self.assertIsNotNone(result)
        print(f"Search returned {len(result)} results out of {result.total} total")

        # Test iteration
        for record in result:
            print(f"Found record: {record.get('name', 'Unknown')}")
            print(f"ID: {record.id}")

        # Test boolean check
        if result:
            print("Search found results")
        else:
            print("No results found")

    def test_basic_comparison_operators(self):
        """Test basic comparison operators"""
        query = {
            "where": {
                "age": {"$gt": 25},
                "score": {"$lte": 100},
                "status": {"$ne": "inactive"},
            }
        }
        result = self.client.records.find(query)

        # Test SearchResult properties
        print(f"Comparison search: {len(result)} results, has_more: {result.has_more}")

        # Test data access for results
        for record in result:
            age = record.get("age")
            if age:
                self.assertGreater(age, 25)

    def test_string_operations(self):
        """Test string-specific operations"""
        query = {
            "where": {
                "name": {"$startsWith": "J"},
                "email": {"$contains": "@example.com"},
                "code": {"$endsWith": "XYZ"},
            }
        }
        self.client.records.find(query)

    def test_array_operations(self):
        """Test array operations (in/not in)"""
        query = {
            "where": {
                "status": {"$in": ["active", "pending"]},
                "category": {"$nin": ["archived", "deleted"]},
                "tags": {"$contains": "important"},
            }
        }
        self.client.records.find(query)

    def test_logical_operators(self):
        """Test logical operators (AND, OR, NOT)"""
        query = {
            "where": {
                "$and": [{"age": {"$gte": 18}}, {"status": "active"}],
                "$or": [{"role": "admin"}, {"permissions": {"$contains": "write"}}],
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
                            {"status": "employed"},
                        ]
                    },
                    {"$and": [{"age": {"$gte": 65}}, {"status": "retired"}]},
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
                                    "revenue": {"$gt": 1000000},
                                },
                            }
                        },
                    ]
                }
            },
            "orderBy": {"created_at": "desc"},
            "limit": 10,
        }
        self.client.records.find(query)

    def test_query_builder_simple(self):
        """Test simple query conditions"""
        query = {"where": {"$and": [{"age": {"$gt": 25}}, {"status": "active"}]}}
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
                            {"status": "employed"},
                        ]
                    },
                    {"$and": [{"age": {"$gte": 65}}, {"status": "retired"}]},
                ]
            },
            "orderBy": {"age": "desc"},
            "limit": 20,
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
                                                        "rating": {"$gte": 4},
                                                    }
                                                },
                                            ]
                                        }
                                    },
                                ]
                            }
                        },
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
                                    {"guardian_approved": True},
                                ]
                            },
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
                                                    "name": {
                                                        "$in": ["feature1", "feature2"]
                                                    },
                                                    "enabled": True,
                                                }
                                            },
                                        ]
                                    }
                                },
                            ]
                        }
                    },
                ]
            },
            "orderBy": {"created_at": "desc", "name": "asc"},
            "skip": 0,
            "limit": 50,
        }
        self.client.records.find(query)

    def test_select_self_group_single_kpi(self):
        """Test select with self-group groupBy for a single global metric"""
        query = {
            "select": {"total": {"$sum": "$record.amount"}},
            "groupBy": ["total"],
            "orderBy": {"total": "asc"},
        }
        self.client.records.find(query)

    def test_select_self_group_multiple_kpis(self):
        """Test select with self-group groupBy for multiple global metrics"""
        query = {
            "select": {
                "totalRevenue": {"$sum": "$record.amount"},
                "orderCount": {"$count": "*"},
                "avgOrder": {"$avg": "$record.amount", "$precision": 2},
            },
            "groupBy": ["totalRevenue", "orderCount", "avgOrder"],
            "orderBy": {"totalRevenue": "asc"},
        }
        self.client.records.find(query)

    def test_select_dimensional_groupby(self):
        """Test select with dimensional groupBy (one row per distinct value)"""
        query = {
            "select": {
                "count": {"$count": "*"},
                "avg": {"$avg": "$record.score", "$precision": 2},
            },
            "groupBy": ["$record.status"],
            "orderBy": {"count": "desc"},
        }
        self.client.records.find(query)

    def test_select_per_record_with_related_label(self):
        """Test select projecting fields from root and a related label via $alias"""
        query = {
            "labels": ["PROJECT"],
            "where": {"EMPLOYEE": {"$alias": "$employee"}},
            "select": {
                "projectName": "$record.name",
                "headcount": {"$count": "$employee.id"},
                "totalWage": {"$sum": "$employee.salary"},
                "avgSalary": {"$avg": "$employee.salary", "$precision": 0},
            },
            "limit": 10,
        }
        self.client.records.find(query)

    def test_select_derived_metrics_with_ref(self):
        """Test select using $ref to build derived (post-aggregation) metrics"""
        query = {
            "select": {
                "revenue": {"$sum": "$record.amount"},
                "cost": {"$sum": "$record.cost"},
                "profit": {"$subtract": [{"$ref": "revenue"}, {"$ref": "cost"}]},
                "margin": {"$divide": [{"$ref": "profit"}, {"$ref": "revenue"}]},
            },
            "groupBy": ["revenue", "cost", "profit", "margin"],
            "orderBy": {"revenue": "asc"},
        }
        self.client.records.find(query)

    def test_select_timebucket(self):
        """Test select with $timeBucket for time-series grouping"""
        query = {
            "select": {
                "month": {
                    "$timeBucket": {"field": "$record.createdAt", "unit": "month"}
                },
                "count": {"$count": "*"},
            },
            "groupBy": ["month"],
            "orderBy": {"month": "asc"},
        }
        self.client.records.find(query)

    def test_select_collect_label_based(self):
        """Test select with label-based $collect for nested hierarchy"""
        query = {
            "labels": ["COMPANY"],
            "select": {
                "company": "$record.name",
                "departments": {
                    "$collect": {
                        "label": "DEPARTMENT",
                        "select": {
                            "name": "$self.name",
                            "projects": {
                                "$collect": {
                                    "label": "PROJECT",
                                    "select": {
                                        "name": "$self.name",
                                        "employees": {
                                            "$collect": {
                                                "label": "EMPLOYEE",
                                                "orderBy": {"salary": "desc"},
                                                "limit": 3,
                                            }
                                        },
                                    },
                                }
                            },
                        },
                    }
                },
            },
        }
        self.client.records.find(query)

    def test_select_collect_alias_based(self):
        """Test select with alias-based $collect (requires $alias in where)"""
        query = {
            "where": {"USER": {"$alias": "$user"}},
            "select": {
                "users": {
                    "$collect": {
                        "from": "$user",
                        "select": {"id": "$user.id", "name": "$user.name"},
                        "orderBy": {"name": "asc"},
                        "limit": 10,
                    }
                }
            },
        }
        self.client.records.find(query)

    def test_select_math_inside_aggregation(self):
        """Test select with math expressions nested inside aggregation"""
        query = {
            "select": {
                "total": {"$sum": {"$multiply": ["$record.price", "$record.quantity"]}}
            },
            "groupBy": ["total"],
            "orderBy": {"total": "asc"},
        }
        self.client.records.find(query)


if __name__ == "__main__":
    unittest.main()
