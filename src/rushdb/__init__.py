"""RushDB Client Package

Exposes the RushDB class.
"""

from .api.ai import AIAPI
from .api.query import QueryAPI
from .api.records import pick_record_id
from .api.relationship_patterns import RelationshipPatternsAPI
from .api.relationships import RelationsAPI
from .client import RushDB
from .common import NonUniqueResultError, RushDBError
from .models.api_response import ApiResponse
from .models.property import Property
from .models.record import Record, RecordTarget, RelationTarget
from .models.relationship import RelationshipDetachOptions, RelationshipOptions
from .models.result import RecordSearchResult, SearchResult
from .models.transaction import Transaction

__all__ = [
    "RushDB",
    "RushDBError",
    "NonUniqueResultError",
    "Record",
    "RecordTarget",
    "RelationTarget",
    "pick_record_id",
    "RecordSearchResult",
    "SearchResult",
    "Transaction",
    "Property",
    "RelationshipOptions",
    "RelationshipDetachOptions",
    "QueryAPI",
    "RelationsAPI",
    "RelationshipPatternsAPI",
    "ApiResponse",
    "AIAPI",
]
