"""What RushDB Cloud adds over a standalone engine, as SDK methods.

One list: the direct-mode router refuses these with ``CloudOnlyError``, and
the docs mark them. Everything else the SDK offers runs against a standalone
``rushdbd`` too.
"""

from typing import Dict

_PATTERNS = "relationship-pattern suggestions are produced and stored by the platform"

CLOUD_ONLY_METHODS: Dict[str, str] = {
    "ai.search": "natural-language search turns the prompt into a query with an LLM",
    "relationships.patterns.list": _PATTERNS,
    "relationships.patterns.analyze": _PATTERNS,
    "relationships.patterns.approve": _PATTERNS,
    "relationships.patterns.ignore": _PATTERNS,
    "relationships.patterns.delete": _PATTERNS,
    "settings.get": "project settings belong to the platform",
}
"""Methods that need RushDB Cloud, with the reason."""

CLOUD_ONLY_FORMS: Dict[str, str] = {
    "records.vector_search": (
        "a text `query` is embedded with the managed embedding model; "
        "in direct mode pass `queryVector`"
    ),
    "ai.indexes.create": (
        "a managed index is filled by the managed embedding model; in direct mode "
        "create an external index (`external: True`) and supply vectors"
    ),
}
"""Methods available in direct mode in one form only."""


def is_cloud_only_method(method: str) -> bool:
    """Whether ``method`` (e.g. ``relationships.patterns.list``) needs RushDB Cloud."""
    return method in CLOUD_ONLY_METHODS
