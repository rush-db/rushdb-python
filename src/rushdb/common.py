from typing import Dict, List, Optional, Union, TypedDict, Literal

# Relation types
RelationDirection = Literal['in', 'out']

class RelationOptions(TypedDict, total=False):
    """Options for creating relations."""
    direction: Optional[RelationDirection]
    type: Optional[str]

class RelationDetachOptions(TypedDict, total=False):
    """Options for detaching relations."""
    direction: Optional[RelationDirection]
    typeOrTypes: Optional[Union[str, List[str]]]

class RushDBError(Exception):
    """Custom exception for RushDB client errors."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}