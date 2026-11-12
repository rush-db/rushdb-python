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

# Property types. A None/null value means the field is unset; `None` is still accepted as an
# input value in `PropertyWithValue.value` below.
PropertyType = Literal["boolean", "datetime", "number", "string"]

PropertyValue = Union[DatetimeValue, BooleanValue, None, NumberValue, StringValue]
"""One stored value of a property."""


class Property(TypedDict):
    """Base property structure"""

    id: str
    name: str
    type: PropertyType
    metadata: Optional[str]
    recordsCount: Optional[int]


class PropertyWithValue(Property):
    """Property with a value"""

    value: Union[
        DatetimeValue,
        BooleanValue,
        None,
        NumberValue,
        StringValue,
        List[Union[DatetimeValue, BooleanValue, None, NumberValue, StringValue]],
    ]


class PropertyValuesData(TypedDict, total=False):
    """Property values data structure"""

    max: Optional[float]
    min: Optional[float]
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
