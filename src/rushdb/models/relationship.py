from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

RelationshipDirection = Literal["in", "out"]


class Relationship(TypedDict, total=False):
    targetLabel: str
    targetId: str
    type: str
    direction: RelationshipDirection
    sourceId: str
    sourceLabel: str
    properties: Dict[str, Any]


class RelationshipOptions(TypedDict, total=False):
    """Options for creating relations."""

    direction: Optional[RelationshipDirection]
    type: Optional[str]
    properties: Optional[Dict[str, Any]]


class RelationshipDetachOptions(TypedDict, total=False):
    """Options for detaching relations."""

    direction: Optional[RelationshipDirection]
    typeOrTypes: Optional[Union[str, List[str]]]
