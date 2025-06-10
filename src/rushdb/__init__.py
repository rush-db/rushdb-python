"""RushDB Client Package

Exposes the RushDB class.
"""

from .client import RushDB
from .common import RushDBError
from .models.property import Property
from .models.record import Record
from .models.relationship import RelationshipDetachOptions, RelationshipOptions
from .models.result import RecordSearchResult, SearchResult
from .models.transaction import Transaction

__all__ = [
    "RushDB",
    "RushDBError",
    "Record",
    "RecordSearchResult",
    "SearchResult",
    "Transaction",
    "Property",
    "RelationshipOptions",
    "RelationshipDetachOptions",
]
