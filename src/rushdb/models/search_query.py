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
    aggregate: Optional[Dict[str, Any]]
