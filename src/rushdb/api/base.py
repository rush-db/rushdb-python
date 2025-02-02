from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import RushDBClient


class BaseAPI:
    """Base class for all API endpoints."""

    def __init__(self, client: "RushDBClient"):
        self.client = client
