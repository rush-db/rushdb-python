"""Catalog lookups: the shapes of ``db.ai.search_values``,
``db.ai.get_schema_summary``, ``db.ai.resolve_names`` and
``db.ai.get_join_candidates``."""

from typing import List, Literal, TypedDict

from .property import PropertyValue, ValueMatchMode


class _SearchValuesParamsRequired(TypedDict):
    text: str


class SearchValuesParams(_SearchValuesParamsRequired, total=False):
    """Body of ``db.ai.search_values`` (``POST /ai/values/search``)."""

    match: ValueMatchMode
    caseSensitive: bool
    minSimilarity: float
    labels: List[str]
    """Labels to search (all when omitted)."""
    limit: int
    """Most matches (default 50, at most 1000)."""


class ValueMatch(TypedDict):
    """A stored value matching ``db.ai.search_values``, with where it is held."""

    label: str
    property: str
    value: PropertyValue
    count: int


class _ValueMatchesDataRequired(TypedDict):
    matches: List[ValueMatch]
    total: int
    """Matches before ``limit``."""


class ValueMatchesData(_ValueMatchesDataRequired, total=False):
    """``data`` of ``db.ai.search_values``."""

    skipped: List[str]
    """Properties that could not be searched within the request limits, as
    ``label.property``."""


class _NameSuggestionRequired(TypedDict):
    label: str
    score: float
    """Spelling similarity, 0 to 1."""


class NameSuggestion(_NameSuggestionRequired, total=False):
    """A label or property spelled like a requested name (``db.ai.resolve_names``)."""

    property: str


class _SchemaSummaryPropertyRequired(TypedDict):
    name: str
    type: str
    recordsCount: int


class SchemaSummaryProperty(_SchemaSummaryPropertyRequired, total=False):
    """One property of a :class:`SchemaSummaryLabel`."""

    isArray: bool
    distinctCount: int
    min: PropertyValue
    max: PropertyValue
    values: List[PropertyValue]
    """Every value, by record count, when the property holds few."""


class SchemaSummaryRelationship(TypedDict):
    """One relationship shape of a :class:`SchemaSummaryLabel`."""

    type: str
    label: str
    direction: Literal["in", "out"]
    count: int


class _SchemaSummaryLabelRequired(TypedDict):
    name: str
    recordsCount: int
    properties: List[SchemaSummaryProperty]


class SchemaSummaryLabel(_SchemaSummaryLabelRequired, total=False):
    """One label of ``db.ai.get_schema_summary``."""

    relationships: List[SchemaSummaryRelationship]


class JoinEndpoint(TypedDict):
    """One side of a :class:`JoinCandidate`."""

    label: str
    property: str


class JoinEvidence(TypedDict, total=False):
    """What a :class:`JoinCandidate` rests on."""

    sourceDistinct: int
    targetDistinct: int
    matchedDistinct: int
    matchedRecords: int
    coverage: float
    targetUniqueness: float
    notCompared: str


class JoinCandidate(TypedDict):
    """A reference suggested by ``db.ai.get_join_candidates``, with its evidence."""

    source: JoinEndpoint
    target: JoinEndpoint
    reasons: List[str]
    """``name``, ``chain`` and/or ``values``: the rules that proposed it."""
    relationshipType: str
    confidence: float
    evidence: JoinEvidence
    rationale: str


__all__ = [
    "JoinCandidate",
    "JoinEndpoint",
    "JoinEvidence",
    "NameSuggestion",
    "SchemaSummaryLabel",
    "SchemaSummaryProperty",
    "SchemaSummaryRelationship",
    "SearchValuesParams",
    "ValueMatch",
    "ValueMatchesData",
]
