"""``ai.get_schema`` and ``ai.get_schema_markdown`` in direct mode: the engine's
``describe.schema`` arranged per label exactly as RushDB Cloud arranges it,
with each property's vector indexes attached."""

from typing import Any, Callable, Dict, List, Optional

from .engine import DirectEngine

Body = Dict[str, Any]

_SAMPLE_VALUES = 10


def build_schema(
    engine: DirectEngine,
    labels: Optional[List[str]],
    to_embedding_index: Callable[[Body], Body],
) -> List[Body]:
    described = engine.execute(
        {
            "kind": "describe",
            "describe": {
                "kind": "schema",
                "query": {"labels": [], "predicate": {}, "offset": 0},
            },
        }
    )
    vector_indexes = (
        engine.execute({"kind": "describe", "describe": {"kind": "vectorIndexes"}}).get(
            "indexes"
        )
        or []
    )
    native = described.get("schema") or {
        "labels": [],
        "properties": [],
        "relationships": [],
    }

    props_by_label: Dict[str, List[Body]] = {}
    for definition in native.get("properties") or []:
        label = definition.get("label") or ""
        if not label:
            continue
        prop: Body = {
            "id": str(definition.get("id")),
            "name": str(definition.get("name")),
            "type": str(definition.get("type") or "string"),
            "recordsCount": int(definition.get("recordsCount") or 0),
        }
        if definition.get("isArray") is not None:
            prop["isArray"] = definition["isArray"]
        if prop["type"] == "boolean":
            prop["values"] = ["true", "false"]
        elif prop["type"] == "string":
            samples: List[str] = []
            for value in definition.get("sampleValues") or []:
                if value is not None and str(value) not in samples:
                    samples.append(str(value))
            prop["values"] = samples[:_SAMPLE_VALUES]
        for bound in ("min", "max"):
            if definition.get(bound) is not None:
                prop[bound] = (
                    float(definition[bound])
                    if prop["type"] == "number"
                    else str(definition[bound])
                )
                if prop["type"] == "number" and float(prop[bound]).is_integer():
                    prop[bound] = int(prop[bound])
        props_by_label.setdefault(label, []).append(prop)

    schema: List[Body] = [
        {
            "label": label["name"],
            "count": int(label.get("recordsCount") or 0),
            "properties": props_by_label.get(label["name"], []),
            "relationships": [],
        }
        for label in native.get("labels") or []
    ]
    by_label = {item["label"]: item for item in schema}

    def add_relationship(label: str, relationship: Body) -> None:
        item = by_label.get(label)
        if item is None:
            return
        for existing in item["relationships"]:
            if (existing["direction"], existing["label"], existing["type"]) == (
                relationship["direction"],
                relationship["label"],
                relationship["type"],
            ):
                return
        item["relationships"].append(relationship)

    for relationship in native.get("relationships") or []:
        edge_properties = relationship.get("properties") or None
        outgoing = {
            "label": relationship["targetLabel"],
            "type": relationship["type"],
            "direction": "out",
            "count": relationship.get("count"),
        }
        if edge_properties:
            outgoing["properties"] = edge_properties
        add_relationship(relationship["sourceLabel"], outgoing)
        if relationship["sourceLabel"] != relationship["targetLabel"]:
            incoming = {
                **outgoing,
                "label": relationship["sourceLabel"],
                "direction": "in",
            }
            add_relationship(relationship["targetLabel"], incoming)

    index_map: Dict[str, List[Body]] = {}
    for index in (to_embedding_index(raw) for raw in vector_indexes):
        index_map.setdefault(f"{index['label']}|{index['propertyName']}", []).append(
            {
                "id": str(index.get("id") or ""),
                "name": str(index.get("name") or ""),
                "sourceType": str(index.get("sourceType") or "external"),
                "similarityFunction": str(index.get("similarityFunction") or "cosine"),
                "dimensions": int(index.get("dimensions") or 0),
                "status": str(index.get("status") or "pending"),
                "modelKey": str(index.get("modelKey") or ""),
            }
        )
    for item in schema:
        item["relationships"].sort(
            key=lambda r: f"{r['direction']}|{r['label']}|{r['type']}"
        )
        for prop in item["properties"]:
            indexes = index_map.get(f"{item['label']}|{prop['name']}")
            if indexes:
                prop["vectorIndexes"] = indexes
    schema.sort(key=lambda item: -item["count"])
    return [item for item in schema if item["label"] in labels] if labels else schema


def build_schema_markdown(schema: List[Body]) -> str:
    """The schema as compact Markdown tables, for an LLM to read."""

    def esc(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("`", "\\`")

    def truncate(value: str) -> str:
        return value[:48] + "…" if len(value) > 48 else value

    def fmt_values(prop: Body) -> str:
        kind = (prop.get("type") or "").lower()
        if kind in ("number", "datetime"):
            if prop.get("min") is not None and prop.get("max") is not None:
                return f"`{prop['min']}`..`{prop['max']}`"
            return "—"
        values = prop.get("values") or []
        if values:
            shown = ", ".join(f"`{esc(truncate(str(v)))}`" for v in values[:5])
            tail = f" (+{len(values) - 5} more)" if len(values) > 5 else ""
            return shown + tail
        return "—"

    md = "# Graph Schema\n\n## Labels\n\n| Label | Count |\n|-------|------:|\n"
    for item in schema:
        md += f"| `{esc(item['label'])}` | {item['count']} |\n"
    md += "\n"
    for item in schema:
        word = "record" if item["count"] == 1 else "records"
        md += f"---\n\n## `{esc(item['label'])}` ({item['count']} {word})\n\n"
        if item["properties"]:
            md += "### Properties\n\n"
            md += "| Property | Type | Values / Range | Semantic Search |\n|----------|------|----------------|-----------------|\n"
            for prop in item["properties"]:
                semantic = (
                    ", ".join(
                        f"`{vi['name']}` ({vi['sourceType']}, {vi['similarityFunction']}, {vi['dimensions']}d) [{vi['status']}]"
                        for vi in prop["vectorIndexes"]
                    )
                    if prop.get("vectorIndexes")
                    else "—"
                )
                prop_type = f"{prop['type']}[]" if prop.get("isArray") else prop["type"]
                md += f"| `{esc(prop['name'])}` | {esc(prop_type)} | {fmt_values(prop)} | {semantic} |\n"
            md += "\n"
        if item["relationships"]:
            md += "### Relationships\n\n"
            md += "| Traversal | Count | Edge Properties |\n|-----------|------:|-----------------|\n"
            for rel in item["relationships"]:
                edge = (
                    ", ".join(
                        f"`{esc(p['name'])}:{esc(p['type'])}`"
                        for p in rel["properties"]
                    )
                    if rel.get("properties")
                    else "—"
                )
                pattern = (
                    f"({item['label']})-[:{rel['type']}]->({rel['label']})"
                    if rel["direction"] == "out"
                    else f"({item['label']})<-[:{rel['type']}]-({rel['label']})"
                )
                count = str(rel["count"]) if isinstance(rel.get("count"), int) else "—"
                md += f"| `{esc(pattern)}` | {count} | {edge} |\n"
            md += "\n"
    return md.strip()
