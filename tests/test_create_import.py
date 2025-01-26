"""Test cases for RushDB create and import operations."""

import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from rushdb.client import (
    RushDBClient,
    RelationOptions,
    RelationDetachOptions,
    Record,
    RushDBError
)
import json

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
        cls.base_url = os.getenv('RUSHDB_URL', 'http://localhost:8000')

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
            options=RelationOptions(type="HAS_DEPARTMENT", direction="in")
        )

        # Test detach method
        company.detach(
            target=department.id,
            options=RelationDetachOptions(typeOrTypes="HAS_DEPARTMENT", direction="in")
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
                options=RelationOptions(type="HAS_DEPARTMENT", direction="out"),
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
        print("Raw _data:", json.dumps(records[1].data, indent=2))

        self.assertEqual(records[0].data['__label'], "COMPANY")
        self.assertEqual(records[1].data['__label'], "COMPANY")

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
        options = RelationOptions(type="HAS_EMPLOYEE", direction="out")
        self.client.records.attach(
            source=project,
            target=employee,
            options=options
        )

        # Test detaching with options
        detach_options = RelationDetachOptions(
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