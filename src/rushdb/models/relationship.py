from typing import List, Literal, Optional, TypedDict, Union

RelationshipDirection = Literal["in", "out"]


class Relationship(TypedDict, total=False):
    targetLabel: str
    targetId: str
    type: str
    sourceId: str
    sourceLabel: str


class RelationshipOptions(TypedDict, total=False):
    """Options for creating relations."""

    direction: Optional[RelationshipDirection]
    type: Optional[str]


class RelationshipDetachOptions(TypedDict, total=False):
    """Options for detaching relations."""

    direction: Optional[RelationshipDirection]
    typeOrTypes: Optional[Union[str, List[str]]]
