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
NumberValue = float
StringValue = str

# Property types
PropertyType = Literal["boolean", "datetime", "null", "number", "string"]


class Property(TypedDict):
    """Base property structure"""

    id: str
    name: str
    type: PropertyType
    metadata: Optional[str]


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
