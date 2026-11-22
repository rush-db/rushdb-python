from typing import Any, List, Literal, Optional, TypedDict, Union


# Value types
class DatetimeObject(TypedDict, total=False):
    """Datetime object structure"""

    year: int
    month: Optional[int]
    day: Optional[int]
    hour: Optional[int]
    minute: Optional[int]
    second: Optional[int]
    millisecond: Optional[int]
    microsecond: Optional[int]
    nanosecond: Optional[int]


DatetimeValue = Union[DatetimeObject, str]
BooleanValue = bool
NumberValue = Union[float, int]
StringValue = str

DateValue = str
"""A calendar date, ``"2024-05-01"``."""
LocalTimeValue = str
"""A time of day without a zone, ``"10:30:00"`` or ``"10:30:00.5"``."""
LocalDatetimeValue = str
"""A wall-clock date and time without a zone, ``"2024-05-01T10:30:00"``."""
DurationValue = str
"""An ISO 8601 duration, ``"P1DT2H"``; months, days and seconds kept apart."""

PointCrs = Literal["wgs-84", "wgs-84-3d", "cartesian", "cartesian-3d", "EPSG:7203"]


class _PointBase(TypedDict):
    type: Literal["Point"]
    coordinates: List[float]
    """``[longitude, latitude]`` (``[lon, lat, height]`` in 3D), or ``[x, y]``
    / ``[x, y, z]`` for a Cartesian point."""


class PointValue(_PointBase, total=False):
    """A GeoJSON point. Without ``crs`` it is a WGS-84 position, longitude
    first; ``"crs": "cartesian"`` puts it in a plane."""

    crs: PointCrs


# Property types. A None/null value means the field is unset; `None` is still accepted as an
# input value in `PropertyWithValue.value` below.
PropertyType = Literal[
    "boolean",
    "datetime",
    "date",
    "localtime",
    "localdatetime",
    "duration",
    "point",
    "number",
    "string",
]
"""A property's type. RushDB 3.0.14 adds ``date``, ``localtime``,
``localdatetime``, ``duration`` and ``point``; earlier servers store all of
those as ``datetime`` or ``string``."""

PROPERTY_TYPES = (
    "boolean",
    "datetime",
    "date",
    "localtime",
    "localdatetime",
    "duration",
    "point",
    "number",
    "string",
)
"""Every :data:`PropertyType`, in the order RushDB documents them."""

TEMPORAL_PROPERTY_TYPES = ("datetime", "date", "localtime", "localdatetime")
"""The types whose values are ISO 8601 temporal text ordered in time."""

ORDERED_PROPERTY_TYPES = ("number",) + TEMPORAL_PROPERTY_TYPES + ("duration",)
"""The types with a range: ``min``/``max``, ``$gt``/``$lt`` and sorting apply."""

PropertyValue = Union[
    DatetimeValue,
    BooleanValue,
    None,
    NumberValue,
    StringValue,
    PointValue,
]
"""One stored value of a property. Dates, times and durations are ISO 8601
text; a point is a GeoJSON object."""


class Property(TypedDict):
    """Base property structure"""

    id: str
    name: str
    type: PropertyType
    metadata: Optional[str]
    recordsCount: Optional[int]


class PropertyWithValue(Property):
    """Property with a value"""

    value: Union[PropertyValue, List[PropertyValue]]


class PropertyValuesData(TypedDict, total=False):
    """Property values data structure"""

    max: Optional[Union[float, str]]
    """A number for ``number`` properties; ISO 8601 text in the property's
    type for temporal and duration ones (RushDB 3.0.14; earlier servers
    answer datetimes in epoch milliseconds)."""
    min: Optional[Union[float, str]]
    values: List[Any]
    counts: List[int]
    """Record counts aligned with ``values`` (a searched or ``limit``-ed read)."""
    distinctCount: int
    """Distinct values matching the search, before ``limit``."""
    searchMissed: bool
    """The search matched nothing and ``values`` lists the whole (small) domain
    (``domainOnMiss``)."""


ValueMatchMode = Literal["contains", "prefix", "exact", "similar"]
"""How a value search matches stored values. ``similar`` finds near spellings."""


class PropertyValuesSearch(TypedDict, total=False):
    """Value-search options for ``db.properties.values``."""

    query: Optional[str]
    """Keep the values whose text matches."""
    match: ValueMatchMode
    limit: Optional[int]
    """Most values returned, by record count (default 100 with ``query``)."""
    domainOnMiss: int
    """With no match, list every value of a property holding at most this many."""
    minSimilarity: float
    """``similar`` only: least similarity, 0 to 1 (default 0.6)."""
