from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SearchQuery(TypedDict, total=False):
    """TypedDict representing the query structure for finding records."""

    where: Optional[Dict[str, Any]]
    labels: Optional[List[str]]
    skip: Optional[int]
    limit: Optional[int]
    orderBy: Optional[Union[Dict[str, OrderDirection], OrderDirection]]
    select: Optional[Dict[str, Any]]
    groupBy: Optional[List[str]]


class RelationshipEndpointQuery(TypedDict, total=False):
    """Endpoint record predicates for relationship search."""

    where: Optional[Dict[str, Any]]
    labels: Optional[List[str]]


class RelationshipSearchQuery(TypedDict, total=False):
    """TypedDict representing the query structure for finding relationship edges."""

    where: Optional[Dict[str, Any]]
    source: Optional[RelationshipEndpointQuery]
    target: Optional[RelationshipEndpointQuery]
    skip: Optional[int]
    limit: Optional[int]
    orderBy: Optional[Union[Dict[str, OrderDirection], OrderDirection]]
