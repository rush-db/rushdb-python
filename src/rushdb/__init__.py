"""RushDB Client Package

Exposes the RushDB class.
"""

from .api.ai import AIAPI
from .api.query import QueryAPI
from .api.relationships import RelationsAPI
from .client import RushDB
from .common import NonUniqueResultError, RushDBError
from .models.api_response import ApiResponse
from .models.property import Property
from .models.record import Record
from .models.relationship import RelationshipDetachOptions, RelationshipOptions
from .models.result import RecordSearchResult, SearchResult
from .models.transaction import Transaction

__all__ = [
    "RushDB",
    "RushDBError",
    "NonUniqueResultError",
    "Record",
    "RecordSearchResult",
    "SearchResult",
    "Transaction",
    "Property",
    "RelationshipOptions",
    "RelationshipDetachOptions",
    "QueryAPI",
    "RelationsAPI",
    "ApiResponse",
    "AIAPI",
]
