"""Test cases for RushDB create and import operations."""

import unittest

from src.rushdb import (
    RelationshipOptions,
    RelationshipDetachOptions,
    Record
)
import json

from .test_base_setup import TestBase


class TestCreateImport(TestBase):
    """Test cases for record creation and import operations."""

    def test_create_with_data(self):
        """Test creating a record with data"""
        data = {
            "name": "Google LLC",
            "address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
            "foundedAt": "1998-09-04T00:00:00.000Z",
            "rating": 4.9
        }
        record = self.client.records.create("COMPANY", data)

        print("\nDEBUG Record Data:")
        print("Raw _data:", json.dumps(record.data, indent=2))
        print("Available keys:", list(record.data.keys()))
        print("Timestamp:", record.timestamp)
        print("Date:", record.date)

        self.assertIsInstance(record, Record)
        self.assertEqual(record.data['__label'], "COMPANY")
        self.assertEqual(record.data["name"], "Google LLC")
        self.assertEqual(record.data["rating"], 4.9)

    def test_record_methods(self):
        """Test Record class methods"""
        # Create a company record
        company = self.client.records.create("COMPANY", {
            "name": "Apple Inc",
            "rating": 4.8
        })
        self.assertIsInstance(company, Record)
        self.assertEqual(company.data["name"], "Apple Inc")

        # Create a department and attach it to the company
        department = self.client.records.create("DEPARTMENT", {
            "name": "Engineering",
            "location": "Cupertino"
        })
        self.assertIsInstance(department, Record)

        # Test attach method
        company.attach(
            target=department.id,
            options=RelationshipOptions(type="HAS_DEPARTMENT", direction="in")
        )

        # Test detach method
        company.detach(
            target=department.id,
            options=RelationshipDetachOptions(typeOrTypes="HAS_DEPARTMENT", direction="in")
        )

        # Test delete method
        department.delete()

    def test_create_with_transaction(self):
        """Test creating records within a transaction"""
        # Start a transaction
        with self.client.transactions.begin() as transaction:
            # Create company
            company = self.client.records.create("COMPANY", {
                "name": "Apple Inc",
                "rating": 4.8
            }, transaction=transaction)
            self.assertIsInstance(company, Record)

            # Create department
            department = self.client.records.create("DEPARTMENT", {
                "name": "Engineering",
                "location": "Cupertino"
            }, transaction=transaction)
            self.assertIsInstance(department, Record)

            # Create relation
            company.attach(
                target=department,
                options=RelationshipOptions(type="HAS_DEPARTMENT", direction="out"),
                transaction=transaction
            )

            transaction.commit()

    def test_create_many_records(self):
        """Test creating multiple records"""
        data = [
            {
                "name": "Apple Inc",
                "address": "One Apple Park Way, Cupertino, CA 95014, USA",
                "foundedAt": "1976-04-01T00:00:00.000Z",
                "rating": 4.8
            },
            {
                "name": "Microsoft Corporation",
                "address": "One Microsoft Way, Redmond, WA 98052, USA",
                "foundedAt": "1975-04-04T00:00:00.000Z",
                "rating": 4.7
            }
        ]
        records = self.client.records.create_many("COMPANY", data, {
            "returnResult": True,
            "suggestTypes": True
        })
        self.assertTrue(all(isinstance(record, Record) for record in records))
        self.assertEqual(len(records), 2)

        print("\nDEBUG Record Data:")
        print("Raw data:", json.dumps(records[1].data, indent=2))

        self.assertEqual(records[0].label, "COMPANY")
        self.assertEqual(records[1].label, "COMPANY")

    def test_create_with_relations(self):
        """Test creating records with relations"""
        # Create employee
        employee = self.client.records.create("EMPLOYEE", {
            "name": "John Doe",
            "position": "Senior Engineer"
        })

        # Create project
        project = self.client.records.create("PROJECT", {
            "name": "Secret Project",
            "budget": 1000000
        })

        # Create relation with options
        options = RelationshipOptions(type="HAS_EMPLOYEE", direction="out")
        self.client.records.attach(
            source=project,
            target=employee,
            options=options
        )

        # Test detaching with options
        detach_options = RelationshipDetachOptions(
            typeOrTypes="HAS_EMPLOYEE",
            direction="out"
        )
        self.client.records.detach(
            source=project,
            target=employee,
            options=detach_options
        )

    def test_create_with_nested_data(self):
        """Test creating records with nested data structure"""
        data = {
            "name": "Meta Platforms Inc",
            "rating": 4.6,
            "DEPARTMENT": [{
                "name": "Reality Labs",
                "PROJECT": [{
                    "name": "Quest 3",
                    "active": True,
                    "EMPLOYEE": [{
                        "name": "Mark Zuckerberg",
                        "position": "CEO"
                    }]
                }]
            }]
        }
        self.client.records.create_many("COMPANY", data)

    def test_transaction_rollback(self):
        """Test transaction rollback"""
        transaction = self.client.transactions.begin()
        try:
            # Create some records
            company = self.client.records.create("COMPANY", {
                "name": "Failed Company",
                "rating": 1.0
            }, transaction=transaction)

            # Simulate an error
            raise ValueError("Simulated error")

            # This won't be executed due to the error
            self.client.records.create("DEPARTMENT", {
                "name": "Failed Department"
            }, transaction=transaction)

        except ValueError:
            # Rollback the transaction
            transaction.rollback()

    def test_import_csv(self):
        """Test importing data from CSV"""
        csv_data = '''name,age,department,role,salary
John Doe,30,Engineering,Senior Engineer,120000
Jane Smith,28,Product,Product Manager,110000
Bob Wilson,35,Engineering,Tech Lead,140000'''

        self.client.records.import_csv("EMPLOYEE", csv_data)

if __name__ == '__main__':
    unittest.main() 