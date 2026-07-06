from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TraversalHopsRange(TypedDict, total=False):
    """Hop range for variable-length traversal.

    ``min`` defaults to 1 (2 inside a ``$cycle`` block). Omitting ``max``
    requests unbounded traversal, which is only allowed on self-hosted
    deployments and projects with a custom Neo4j instance; the shared cloud
    connection caps ``max`` per deployment (default 25).
    """

    min: int
    max: int


TraversalHops = Union[int, TraversalHopsRange]
"""Depth of a variable-length traversal: an exact hop count or a range."""


class TraversalRelationOptions(TypedDict, total=False):
    """Value for the ``$relation`` key of a traversal block in ``where``.

    ``type`` and ``direction`` constrain every hop; ``hops`` makes the
    traversal variable-length. The nested label constrains only the final
    record — intermediate records are anonymous.

    Example::

        {
            "labels": ["EMPLOYEE"],
            "where": {
                "EMPLOYEE": {
                    "$alias": "$manager",
                    "$relation": {
                        "type": "REPORTS_TO",
                        "direction": "out",
                        "hops": {"min": 1, "max": 4},
                    },
                    "name": {"$contains": "Alice"},
                }
            },
        }
    """

    type: str
    direction: str  # 'in' | 'out'
    hops: TraversalHops


class SearchQuery(TypedDict, total=False):
    """TypedDict representing the query structure for finding records.

    Inside ``where``, a nested key that is a label name traverses to related
    records. Traversal blocks accept ``$alias`` (name the endpoint for
    ``select``/``groupBy``), ``$relation`` (a type string or
    :class:`TraversalRelationOptions`, including variable-length ``hops``),
    and ``$cycle`` (``True`` binds the traversal back to the parent record to
    detect rings; requires ``$relation`` with ``hops`` where ``min`` >= 2 and
    accepts no other keys).
    """

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
