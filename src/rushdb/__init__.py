"""RushDB Client Package

Exposes the RushDB class.
"""

from .api.ai import AIAPI
from .api.query import QueryAPI
from .api.records import pick_record_id
from .api.relationship_patterns import RelationshipPatternsAPI
from .api.relationships import RelationsAPI
from .api.text_indexes import TextIndexesAPI
from .client import RushDB
from .common import CloudOnlyError, DirectModeError, NonUniqueResultError, RushDBError
from .direct.capabilities import (
    CLOUD_ONLY_FORMS,
    CLOUD_ONLY_METHODS,
    is_cloud_only_method,
)
from .models.api_response import ApiResponse
from .models.property import Property
from .models.record import Record, RecordTarget, RelationTarget
from .models.relationship import (
    Relationship,
    RelationshipDetachOptions,
    RelationshipDirection,
    RelationshipOptions,
)
from .models.result import RecordSearchResult, SearchResult
from .models.search_query import (
    RelationshipEndpointQuery,
    RelationshipSearchQuery,
    SearchQuery,
    TraversalHops,
    TraversalHopsRange,
    TraversalRelationOptions,
)
from .models.transaction import Transaction

__all__ = [
    "CLOUD_ONLY_FORMS",
    "CLOUD_ONLY_METHODS",
    "CloudOnlyError",
    "DirectModeError",
    "is_cloud_only_method",
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
    "Relationship",
    "RelationshipDirection",
    "RelationshipOptions",
    "RelationshipDetachOptions",
    "SearchQuery",
    "RelationshipEndpointQuery",
    "RelationshipSearchQuery",
    "TraversalHops",
    "TraversalHopsRange",
    "TraversalRelationOptions",
    "QueryAPI",
    "RelationsAPI",
    "RelationshipPatternsAPI",
    "ApiResponse",
    "AIAPI",
    "TextIndexesAPI",
]
