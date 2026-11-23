"""RushDB Client Package

Exposes the RushDB class.
"""

from .api.ai import AIAPI
from .api.connections import ConnectionsAPI
from .api.imports import ImportsAPI
from .api.indexes import IndexesAPI
from .api.query import QueryAPI
from .api.records import pick_record_id
from .api.relationship_patterns import RelationshipPatternsAPI
from .api.relationships import RelationsAPI
from .api.text_indexes import TextIndexesAPI
from .client import RushDB
from .common import (
    CatalogCheckError,
    CloudOnlyError,
    DirectModeError,
    NonUniqueResultError,
    RushDBError,
    UniqueConstraintError,
)
from .direct.capabilities import (
    CLOUD_ONLY_FORMS,
    CLOUD_ONLY_METHODS,
    is_cloud_only_method,
)
from .models.api_response import ApiResponse
from .models.catalog import (
    JoinCandidate,
    NameSuggestion,
    SchemaSummaryLabel,
    SearchValuesParams,
    ValueMatch,
    ValueMatchesData,
)
from .models.ingest import FINISHED_IMPORT_RUN_STATUSES
from .models.property import (
    ORDERED_PROPERTY_TYPES,
    PROPERTY_TYPES,
    TEMPORAL_PROPERTY_TYPES,
    PointValue,
    Property,
    PropertyType,
    PropertyValuesData,
    PropertyValuesSearch,
    ValueMatchMode,
)
from .models.record import Record, RecordTarget, RelationTarget
from .models.relationship import (
    Relationship,
    RelationshipDetachOptions,
    RelationshipDirection,
    RelationshipOptions,
)
from .models.result import RecordSearchResult, SearchResult
from .models.search_query import (
    CatalogSuggestion,
    CatalogWarning,
    CheckMode,
    DistanceOrder,
    QueryContext,
    RelationshipEndpointQuery,
    RelationshipSearchQuery,
    SearchQuery,
    TraversalHops,
    TraversalHopsRange,
    TraversalRelationOptions,
    WithinBox,
    WithinRadius,
    WithinRegion,
    distance_from,
    point,
    within_box,
    within_radius,
)
from .models.transaction import Transaction

__all__ = [
    "CatalogCheckError",
    "UniqueConstraintError",
    "IndexesAPI",
    "PROPERTY_TYPES",
    "TEMPORAL_PROPERTY_TYPES",
    "ORDERED_PROPERTY_TYPES",
    "PointValue",
    "PropertyType",
    "CatalogSuggestion",
    "CatalogWarning",
    "CheckMode",
    "DistanceOrder",
    "QueryContext",
    "WithinBox",
    "WithinRadius",
    "WithinRegion",
    "distance_from",
    "point",
    "within_box",
    "within_radius",
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
    "PropertyValuesData",
    "PropertyValuesSearch",
    "ValueMatchMode",
    "JoinCandidate",
    "NameSuggestion",
    "SchemaSummaryLabel",
    "SearchValuesParams",
    "ValueMatch",
    "ValueMatchesData",
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
    "ImportsAPI",
    "ConnectionsAPI",
    "FINISHED_IMPORT_RUN_STATUSES",
]
