from typing import TypedDict, Optional, Union, Literal, List, Any

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
NullValue = None
NumberValue = float
StringValue = str

# Property types
PROPERTY_TYPE_BOOLEAN = 'boolean'
PROPERTY_TYPE_DATETIME = 'datetime'
PROPERTY_TYPE_NULL = 'null'
PROPERTY_TYPE_NUMBER = 'number'
PROPERTY_TYPE_STRING = 'string'

PropertyType = Literal[
    PROPERTY_TYPE_BOOLEAN,
    PROPERTY_TYPE_DATETIME,
    PROPERTY_TYPE_NULL,
    PROPERTY_TYPE_NUMBER,
    PROPERTY_TYPE_STRING
]

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
        NullValue,
        NumberValue,
        StringValue,
        List[Union[DatetimeValue, BooleanValue, NullValue, NumberValue, StringValue]]
    ]


class PropertyValuesData(TypedDict, total=False):
    """Property values data structure"""
    max: Optional[float]
    min: Optional[float]
    values: List[Any]
