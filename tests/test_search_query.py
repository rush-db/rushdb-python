"""Test cases for RushDB search query functionality."""

import time
import unittest
import uuid

from src.rushdb import RushDB, RushDBError

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


class TestMultihopAndCycles(TestBase):
    """Variable-length traversal ($relation.hops) and cycle detection ($cycle).

    Seeds its own graph, isolated by a unique tenantId:

        Reporting chain (MHEmployee, REPORTS_TO, directed "up"):
            E1 -> E2 -> E3 -> E4

        Transfer ring + linear chain (MHAccount, TRANSFERRED_TO):
            A -> B -> C -> A        (3-hop directed ring)
            X -> Y -> Z             (no cycle)
    """

    tenant: str

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = f"multihop-{uuid.uuid4().hex[:8]}"
        # TestBase only creates a client per-test (setUp); seeding needs one here.
        cls.client = RushDB(cls.token, base_url=cls.base_url)

        # TestBase skips per-test in setUp when the server is unreachable; this
        # class seeds data in setUpClass, so it must skip here for the same
        # reason (e.g. CI without a running RushDB) instead of erroring.
        try:
            if not cls.client.ping():
                raise unittest.SkipTest(
                    f"Could not connect to RushDB at {cls.base_url}"
                )
        except RushDBError as e:
            raise unittest.SkipTest(f"RushDB connection error: {str(e)}")

        cls.client.records.create_many(
            "MHEmployee",
            [
                {"name": "E1", "managerName": "E2", "tenantId": cls.tenant},
                {"name": "E2", "managerName": "E3", "tenantId": cls.tenant},
                {"name": "E3", "managerName": "E4", "tenantId": cls.tenant},
                {"name": "E4", "tenantId": cls.tenant},
            ],
        )
        cls.client.relationships.create_many(
            source={
                "label": "MHEmployee",
                "key": "managerName",
                "where": {"tenantId": cls.tenant},
            },
            target={
                "label": "MHEmployee",
                "key": "name",
                "where": {"tenantId": cls.tenant},
            },
            type="REPORTS_TO",
            direction="out",
        )

        cls.client.records.create_many(
            "MHAccount",
            [
                {"name": "A", "sendsTo": "B", "tenantId": cls.tenant},
                {"name": "B", "sendsTo": "C", "tenantId": cls.tenant},
                {"name": "C", "sendsTo": "A", "tenantId": cls.tenant},
                {"name": "X", "sendsTo": "Y", "tenantId": cls.tenant},
                {"name": "Y", "sendsTo": "Z", "tenantId": cls.tenant},
                {"name": "Z", "tenantId": cls.tenant},
            ],
        )
        cls.client.relationships.create_many(
            source={
                "label": "MHAccount",
                "key": "sendsTo",
                "where": {"tenantId": cls.tenant},
            },
            target={
                "label": "MHAccount",
                "key": "name",
                "where": {"tenantId": cls.tenant},
            },
            type="TRANSFERRED_TO",
            direction="out",  # sender -> receiver
        )

        # relationships.create_many is applied via apoc.periodic.iterate — poll
        # until both relationship sets are visible.
        for _ in range(10):
            employee_rels = cls.client.relationships.find(
                {
                    "source": {
                        "labels": ["MHEmployee"],
                        "where": {"tenantId": cls.tenant},
                    },
                    "limit": 100,
                }
            )
            account_rels = cls.client.relationships.find(
                {
                    "source": {
                        "labels": ["MHAccount"],
                        "where": {"tenantId": cls.tenant},
                    },
                    "limit": 100,
                }
            )
            if len(employee_rels.data) >= 3 and len(account_rels.data) >= 5:
                break
            time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        cls.client.records.delete({"where": {"tenantId": cls.tenant}})
        super().tearDownClass()

    def _names(self, result):
        return sorted(record.get("name") for record in result)

    def test_hops_range_reaches_chain_top(self):
        """hops {max: 3} reaches E4 from every subordinate"""
        result = self.client.records.find(
            {
                "labels": ["MHEmployee"],
                "where": {
                    "tenantId": self.tenant,
                    "MHEmployee": {
                        "$relation": {
                            "type": "REPORTS_TO",
                            "direction": "out",
                            "hops": {"max": 3},
                        },
                        "name": "E4",
                    },
                },
            }
        )
        self.assertEqual(self._names(result), ["E1", "E2", "E3"])

    def test_hops_range_is_bounded(self):
        """hops {max: 2} does not reach 3 hops away"""
        result = self.client.records.find(
            {
                "labels": ["MHEmployee"],
                "where": {
                    "tenantId": self.tenant,
                    "MHEmployee": {
                        "$relation": {
                            "type": "REPORTS_TO",
                            "direction": "out",
                            "hops": {"max": 2},
                        },
                        "name": "E4",
                    },
                },
            }
        )
        self.assertEqual(self._names(result), ["E2", "E3"])

    def test_hops_exact_count(self):
        """hops: 3 matches exactly 3 hops"""
        result = self.client.records.find(
            {
                "labels": ["MHEmployee"],
                "where": {
                    "tenantId": self.tenant,
                    "MHEmployee": {
                        "$relation": {
                            "type": "REPORTS_TO",
                            "direction": "out",
                            "hops": 3,
                        },
                        "name": "E4",
                    },
                },
            }
        )
        self.assertEqual(self._names(result), ["E1"])

    def test_cycle_flags_ring_members(self):
        """$cycle returns exactly the ring participants with a deduplicated total"""
        result = self.client.records.find(
            {
                "labels": ["MHAccount"],
                "where": {
                    "tenantId": self.tenant,
                    "RING": {
                        "$cycle": True,
                        "$relation": {
                            "type": "TRANSFERRED_TO",
                            "direction": "out",
                            "hops": {"min": 2, "max": 6},
                        },
                    },
                },
            }
        )
        self.assertEqual(self._names(result), ["A", "B", "C"])
        self.assertEqual(result.total, 3)

    def test_not_cycle_excludes_ring_members(self):
        """$not around a $cycle block finds acyclic accounts"""
        result = self.client.records.find(
            {
                "labels": ["MHAccount"],
                "where": {
                    "tenantId": self.tenant,
                    "$not": {
                        "RING": {
                            "$cycle": True,
                            "$relation": {
                                "type": "TRANSFERRED_TO",
                                "direction": "out",
                                "hops": {"min": 2, "max": 6},
                            },
                        }
                    },
                },
            }
        )
        self.assertEqual(self._names(result), ["X", "Y", "Z"])


if __name__ == "__main__":
    unittest.main()
