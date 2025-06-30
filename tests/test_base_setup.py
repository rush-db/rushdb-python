import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

from src.rushdb import RushDB, RushDBError


def load_env():
    """Load environment variables from .env file."""
    # Try to load from the root directory first
    root_env = Path(__file__).parent.parent / ".env"
    if root_env.exists():
        load_dotenv(root_env)
    else:
        # Fallback to default .env.example if no .env exists
        example_env = Path(__file__).parent.parent / ".env.example"
        if example_env.exists():
            load_dotenv(example_env)
            print(
                "Warning: Using .env.example for testing. Create a .env file with your credentials for proper testing."
            )


class TestBase(unittest.TestCase):
    """Base test class with common setup."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        load_env()

        # Get configuration from environment variables
        cls.token = os.getenv("RUSHDB_API_KEY")
        cls.base_url = os.getenv("RUSHDB_URL")

        if not cls.token:
            raise ValueError(
                "RUSHDB_API_KEY environment variable is not set. "
                "Please create a .env file with your credentials. "
                "You can use .env.example as a template."
            )

    def setUp(self):
        """Set up test client."""
        self.client = RushDB(self.token, base_url=self.base_url)

        # Verify connection
        try:
            if not self.client.ping():
                self.skipTest(f"Could not connect to RushDB at {self.base_url}")
        except RushDBError as e:
            self.skipTest(f"RushDB connection error: {str(e)}")
