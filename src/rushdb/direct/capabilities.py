"""What RushDB Cloud adds over a standalone engine, as SDK methods.

One list: the direct-mode router refuses these with ``CloudOnlyError``, and
the docs mark them. Everything else the SDK offers runs against a standalone
``rushdb`` too.
"""

from typing import Dict

_PATTERNS = "relationship-pattern suggestions are produced and stored by the platform"
_IMPORTS = "file imports run on the platform"
_CONNECTIONS = "connections and their syncs run on the platform"

CLOUD_ONLY_METHODS: Dict[str, str] = {
    "ai.search": "natural-language search turns the prompt into a SQL statement with an LLM",
    "ai.run_sql": "Smart search SQL runs on the platform, which loads the full records the statement selects",
    "ai.get_join_candidates": (
        "join suggestions are computed by the platform "
        "(its heuristics over the engine's value overlap)"
    ),
    "relationships.patterns.list": _PATTERNS,
    "relationships.patterns.analyze": _PATTERNS,
    "relationships.patterns.approve": _PATTERNS,
    "relationships.patterns.ignore": _PATTERNS,
    "relationships.patterns.delete": _PATTERNS,
    "settings.get": "project settings belong to the platform",
    "imports.create": _IMPORTS,
    "imports.add_files": _IMPORTS,
    "imports.remove_file": _IMPORTS,
    "imports.upload": _IMPORTS,
    "imports.preview": _IMPORTS,
    "imports.start": _IMPORTS,
    "imports.get": _IMPORTS,
    "imports.list": _IMPORTS,
    "imports.wait": _IMPORTS,
    "imports.cancel": _IMPORTS,
    "imports.retry": _IMPORTS,
    "imports.delete": _IMPORTS,
    "imports.import_files": _IMPORTS,
    "connections.catalog": _CONNECTIONS,
    "connections.push_templates": _CONNECTIONS,
    "connections.list": _CONNECTIONS,
    "connections.get": _CONNECTIONS,
    "connections.create": _CONNECTIONS,
    "connections.update": _CONNECTIONS,
    "connections.delete": _CONNECTIONS,
    "connections.test": _CONNECTIONS,
    "connections.preview": _CONNECTIONS,
    "connections.fields": _CONNECTIONS,
    "connections.review_fields": _CONNECTIONS,
    "connections.sync": _CONNECTIONS,
    "connections.runs": _CONNECTIONS,
    "connections.pause": _CONNECTIONS,
    "connections.resume": _CONNECTIONS,
    "connections.rotate_webhook_token": _CONNECTIONS,
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
