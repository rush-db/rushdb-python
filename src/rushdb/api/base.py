from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import RushDB


class BaseAPI:
    """Base class for all API endpoints."""

    def __init__(self, client: "RushDB"):
        self.client = client
