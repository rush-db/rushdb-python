from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, Union

from .property import PointValue


class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TraversalHopsRange(TypedDict, total=False):
    """Hop range for variable-length traversal.

    ``min`` defaults to 1 (2 inside a ``$cycle`` block). Omitting ``max``
    means up to 10 hops (the engine default); RushDB Cloud also caps ``max``
    per deployment.
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


class WithinRadius(TypedDict):
    """Points at most ``meters`` from ``center``: great-circle meters for
    WGS-84 points, plane units for Cartesian ones."""

    center: PointValue
    meters: float


class WithinBox(TypedDict):
    """Points inside the box from its south-west corner to its north-east
    corner, edges included. A WGS-84 box whose south-west longitude is east of
    its north-east longitude crosses the antimeridian."""

    box: Union[Tuple[PointValue, PointValue], List[PointValue]]


WithinRegion = Union[WithinRadius, WithinBox]
"""The operand of ``$within`` (RushDB 3.0.14)."""


DistanceOrder = TypedDict("DistanceOrder", {"$distance": PointValue})
"""``orderBy`` value that sorts a point property nearest first; build it with
:func:`distance_from`."""


def point(
    longitude: float,
    latitude: float,
    height: Optional[float] = None,
    *,
    crs: Optional[str] = None,
) -> PointValue:
    """A GeoJSON point, longitude first (``x, y[, z]`` with a Cartesian
    ``crs``)."""
    coordinates = [longitude, latitude] + ([height] if height is not None else [])
    value: PointValue = {"type": "Point", "coordinates": coordinates}
    if crs is not None:
        value["crs"] = crs  # type: ignore[typeddict-item]
    return value


def within_radius(center: PointValue, meters: float) -> Dict[str, WithinRadius]:
    """``{"$within": {"center": ..., "meters": ...}}``, for a ``where`` value."""
    return {"$within": {"center": center, "meters": meters}}


def within_box(south_west: PointValue, north_east: PointValue) -> Dict[str, WithinBox]:
    """``{"$within": {"box": [south_west, north_east]}}``, for a ``where`` value."""
    return {"$within": {"box": [south_west, north_east]}}


def distance_from(center: PointValue) -> DistanceOrder:
    """``{"$distance": center}``, for an ``orderBy`` value: nearest first.
    Records without a point in the property sort last."""
    return {"$distance": center}


CheckMode = Literal["warn", "strict", "off"]
"""How a query's labels, properties and compared texts are checked against
the data (RushDB 3.0.14, sent as ``context.check``):

- ``warn`` (the server default): run the query and report misses in
  ``SearchResult.catalog_warnings``;
- ``strict``: refuse a query with a miss (``RushDBError`` with the warnings
  in ``details``);
- ``off``: no check.
"""


class QueryContext(TypedDict, total=False):
    """Request options sent beside a query as ``context``. Sent only when
    set, so servers before RushDB 3.0.14 never see it."""

    check: CheckMode


class CatalogSuggestion(TypedDict, total=False):
    """What a query most likely meant: the stored spelling, another property
    that stores the text, or a stored value containing it."""

    reason: Literal["spelling", "storedIn", "contains"]
    label: str
    property: str
    value: str


class CatalogWarning(TypedDict, total=False):
    """A label, property or compared text no record holds (RushDB 3.0.14)."""

    kind: Literal["unknownLabel", "unknownProperty", "unknownValue"]
    label: str
    labels: List[str]
    property: str
    value: str
    suggestions: List[CatalogSuggestion]
    """Omitted when the server has none."""


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
    orderBy: Optional[
        Union[Dict[str, Union[OrderDirection, DistanceOrder]], OrderDirection]
    ]
    """A direction, or one per property; ``{"location": {"$distance":
    point}}`` sorts a point property nearest first."""
    select: Optional[Dict[str, Any]]
    groupBy: Optional[List[str]]
    context: QueryContext
    """``{"check": "strict"}`` refuses a query naming a label, property or
    text no record holds; see :data:`CheckMode`."""


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
