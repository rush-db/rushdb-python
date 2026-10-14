"""Direct mode answers the SDK's REST calls with protocol operations.

Every SDK method keeps one code path: in direct mode ``RushDB._make_request``
hands the call to :func:`handle`, which runs it against a standalone engine
the way RushDB Cloud runs it, and answers in the same shape. A Cloud-only
route raises :class:`~rushdb.common.CloudOnlyError` before anything is sent.
No request ever goes to RushDB Cloud.
"""

import os
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..common import CloudOnlyError, DirectModeError, RushDBError
from .capabilities import CLOUD_ONLY_FORMS, CLOUD_ONLY_METHODS
from .engine import DirectEngine
from .schema import build_schema, build_schema_markdown

Body = Dict[str, Any]


def _ok(data: Any, total: Optional[int] = None, meta: Optional[Body] = None) -> Body:
    out: Body = {"success": True, "data": data}
    if total is not None:
        out["total"] = total
    if meta is not None:
        out["meta"] = meta
    return out


def _http_error(status: int, message: str) -> RushDBError:
    return RushDBError(
        message, {"statusCode": status, "message": message}, status=status
    )


def _cloud_only(method: str) -> Callable[..., Body]:
    def handle(_request: "_Request") -> Body:
        raise CloudOnlyError(method, CLOUD_ONLY_METHODS[method])

    return handle


def _not_in_transaction(tx_id: Optional[str], what: str) -> None:
    if tx_id:
        raise DirectModeError(
            f"{what} inside a transaction is not supported in direct mode: the engine "
            "stages record creates, updates, deletes, links and imports. Run it "
            "outside the transaction."
        )


DEFAULT_RELATION_TYPE = "__RUSHDB__RELATION__DEFAULT__"
"""The relationship type a link gets when the caller names none."""


def _stage(engine: DirectEngine, tx_id: str, mutation: Body) -> Body:
    return engine.execute(
        {
            "kind": "transaction",
            "transaction": {
                "kind": "stage",
                "transactionId": tx_id,
                "mutation": mutation,
            },
        }
    )


def _staged_record(engine: DirectEngine, tx_id: str, record_id: str) -> Body:
    """A record as the transaction sees it, in the SDK's shape."""
    record = (
        _stage(engine, tx_id, {"kind": "getRecord", "record": {"id": record_id}}).get(
            "record"
        )
        or {}
    )
    return {
        **(record.get("properties") or {}),
        "__id": record_id,
        "__label": record.get("__label"),
        "__proptypes": {},
    }


class _Request:
    def __init__(
        self,
        body: Body,
        params: Tuple[str, ...],
        query: Body,
        tx_id: Optional[str],
        engine: DirectEngine,
    ):
        self.body = body
        self.params = params
        self.query = query
        self.tx_id = tx_id
        self.engine = engine


# ── shapes ──────────────────────────────────────────────────────────────────


def to_sdk_record(record: Optional[Body]) -> Optional[Body]:
    """An engine record (``{id, label, properties, propertyTypes, score}``) in the SDK's shape."""
    if not record:
        return record
    out: Body = dict(record.get("properties") or {})
    out["__id"] = record.get("id")
    out["__label"] = record.get("label")
    out["__proptypes"] = record.get("propertyTypes") or {}
    if record.get("score") is not None:
        out["__score"] = record["score"]
    return out


def _sdk_records(records: Optional[List[Body]]) -> List[Body]:
    return [to_sdk_record(record) or {} for record in records or []]


_RECORD_KEYS = {"label", "options", "vectors", "data", "properties"}


def _record_properties(body: Body) -> Body:
    """A write's flat data: ``data``, property drafts as an object, or the flat body."""
    data = body.get("data")
    if isinstance(data, dict):
        return data
    properties = body.get("properties")
    if isinstance(properties, list):
        return {item.get("name"): item.get("value") for item in properties}
    if isinstance(properties, dict):
        return properties
    return {key: value for key, value in body.items() if key not in _RECORD_KEYS}


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, dict) and not value)


def _protocol_order(order_by: Any) -> Any:
    if _is_empty(order_by):
        return "desc"
    if not isinstance(order_by, dict):
        return order_by
    return {
        ("id" if field == "__id" else field): direction
        for field, direction in order_by.items()
    }


def query_document(search: Optional[Body] = None) -> Body:
    """A SearchQuery as the engine's query document."""
    search = search or {}
    pagination = search.get("pagination") or {}
    document: Body = {
        "labels": search.get("labels") or [],
        "predicate": search.get("where") or {},
        "order": _protocol_order(search.get("orderBy")),
        "offset": search.get("skip", pagination.get("skip", 0)) or 0,
    }
    if search.get("select") is not None:
        document["select"] = search["select"]
    limit = search.get("limit", pagination.get("limit"))
    if limit is not None:
        document["limit"] = limit
    if search.get("groupBy"):
        document["groupBy"] = search["groupBy"]
    return document


# ── engine reads ────────────────────────────────────────────────────────────


def _get_record(engine: DirectEngine, record_id: str) -> Body:
    return (
        engine.execute(
            {"kind": "query", "query": {"kind": "record", "id": record_id}}
        ).get("record")
        or {}
    )


def _search_records(engine: DirectEngine, search: Body) -> Tuple[List[Body], int]:
    result = engine.execute(
        {"kind": "query", "query": {"kind": "records", "query": query_document(search)}}
    )
    if result.get("kind") == "rows":
        return result.get("rows") or [], result.get("total", 0)
    return _sdk_records(result.get("records")), result.get("total", 0)


def _vector_indexes(engine: DirectEngine) -> List[Body]:
    return (
        engine.execute({"kind": "describe", "describe": {"kind": "vectorIndexes"}}).get(
            "indexes"
        )
        or []
    )


def _declared_indexes(engine: DirectEngine) -> List[Body]:
    return (
        engine.execute({"kind": "describe", "describe": {"kind": "indexes"}}).get(
            "indexes"
        )
        or []
    )


def to_embedding_index(index: Body) -> Body:
    """An engine vector index as the SDK's embedding index (external in direct mode)."""
    dimensions = int(index.get("dimensions") or 0)
    return {
        "id": index.get("name"),
        "name": index.get("name"),
        "label": index.get("label"),
        "propertyName": index.get("property"),
        "vectorPropertyName": f"_emb_external_{index.get('similarity')}_{dimensions}",
        "similarityFunction": index.get("similarity"),
        "dimensions": dimensions,
        "sourceType": "external",
        "status": index.get("status"),
    }


def _to_text_index(index: Body) -> Body:
    return {
        "name": index.get("name"),
        "label": index.get("label"),
        "property": index.get("property"),
        "consistency": index.get("consistency") or "eventual",
        "status": index.get("state"),
        "pending": index.get("pending") or 0,
    }


def _text_indexes(engine: DirectEngine) -> List[Body]:
    return [
        _to_text_index(index)
        for index in _declared_indexes(engine)
        if index.get("kind") == "text"
    ]


# ── names ───────────────────────────────────────────────────────────────────

_NAME_MAX = 64


def _name_with(parts: List[str]) -> str:
    return re.sub(r"[.:-]+$", "", ".".join(parts)[:_NAME_MAX])


def _name_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", value)


def _first_free(base: str, taken: set) -> str:
    if base not in taken:
        return base
    n = 2
    while True:
        suffix = f"-{n}"
        name = base[: _NAME_MAX - len(suffix)] + suffix
        if name not in taken:
            return name
        n += 1


def _default_text_index_name(body: Body) -> str:
    prop = body.get("property") or ""
    return _name_with(
        [
            _name_part(body.get("label") or ""),
            "all" if prop == "*" else _name_part(prop),
            "text",
        ]
    )


def _default_vector_index_name(body: Body, dimensions: int, similarity: str) -> str:
    name = _name_with(
        [
            _name_part(body.get("label") or ""),
            _name_part(body.get("propertyName") or ""),
            "external",
            str(dimensions),
            similarity,
        ]
    )
    return re.sub(r"^emb__", "emb_", name)


# ── vectors ─────────────────────────────────────────────────────────────────


def _name_inline_vectors(
    engine: DirectEngine,
    entries: Optional[List[Body]],
    label: Optional[str],
    known: Optional[List[Body]] = None,
) -> List[Body]:
    """Names each inline vector entry's index: as given, or the one vector index of
    the record's label and property with the vector's dimensions."""
    if not entries:
        return []
    indexes = known if known is not None else _vector_indexes(engine)
    named = []
    for entry in entries:
        if isinstance(entry.get("index"), str):
            named.append(entry)
            continue
        if not label:
            raise _http_error(
                422, "inline vectors require a record label to select their index"
            )
        vector = entry.get("vector")
        dimensions = len(vector) if isinstance(vector, list) else None
        matches = [
            index
            for index in indexes
            if index.get("label") == label
            and index.get("property") == entry.get("propertyName")
            and (
                entry.get("similarityFunction") is None
                or index.get("similarity") == entry.get("similarityFunction")
            )
            and (dimensions is None or int(index.get("dimensions") or 0) == dimensions)
        ]
        if len(matches) != 1:
            raise _http_error(
                404 if not matches else 422,
                (
                    f'No vector index matches label "{label}", property "{entry.get("propertyName")}"'
                    if not matches
                    else f'{len(matches)} vector indexes match label "{label}", property '
                    f'"{entry.get("propertyName")}"; name one with `index`'
                ),
            )
        named.append({**entry, "index": matches[0]["name"]})
    return named


def _name_document_vectors(
    engine: DirectEngine, data: Any, label: Optional[str]
) -> Any:
    documents = data if isinstance(data, list) else [data]

    def carries(document: Any) -> bool:
        return isinstance(document, dict) and bool(document.get("$vectors"))

    if not any(carries(document) for document in documents):
        return data
    indexes = _vector_indexes(engine)
    named = [
        (
            {
                **document,
                "$vectors": _name_inline_vectors(
                    engine, document["$vectors"], label, indexes
                ),
            }
            if carries(document)
            else document
        )
        for document in documents
    ]
    return named if isinstance(data, list) else named[0]


# ── records ─────────────────────────────────────────────────────────────────


def _uuidv7() -> str:
    """A time-ordered UUID (v7), for a record created inside a transaction."""
    millis = int(time.time() * 1000)
    raw = bytearray(millis.to_bytes(6, "big") + os.urandom(10))
    raw[6] = (raw[6] & 0x0F) | 0x70
    raw[8] = (raw[8] & 0x3F) | 0x80
    h = raw.hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def _create_record(request: _Request) -> Body:
    body, engine = request.body, request.engine
    options = body.get("options") or {}
    upsert = bool(options.get("mergeStrategy")) or isinstance(
        options.get("mergeBy"), list
    )
    properties = _record_properties(body)
    if request.tx_id:
        if upsert or body.get("vectors"):
            _not_in_transaction(
                request.tx_id, "An upsert" if upsert else "A write with inline vectors"
            )
        record_id = _uuidv7()
        _stage(
            engine,
            request.tx_id,
            {
                "kind": "createRecord",
                "label": body.get("label"),
                "id": record_id,
                "properties": properties,
                "options": options,
            },
        )
        return _ok(_staged_record(engine, request.tx_id, record_id))
    if upsert:
        options = {**options, "mergeBy": options.get("mergeBy") or []}
    result = engine.execute(
        {
            "kind": "mutate",
            "mutation": {
                "kind": "putRecord",
                "mode": "create",
                "label": body.get("label"),
                "properties": properties,
                "vectors": _name_inline_vectors(
                    engine, body.get("vectors"), body.get("label")
                ),
                "options": options,
            },
        }
    )
    return _ok(to_sdk_record(result.get("record")))


def _put_record(mode: str) -> Callable[[_Request], Body]:
    def handle(request: _Request) -> Body:
        body, engine, (record_id,) = request.body, request.engine, request.params
        requested = body.get("label") or None
        if request.tx_id:
            if body.get("vectors"):
                _not_in_transaction(request.tx_id, "A write with inline vectors")
            if requested:
                current = _staged_record(engine, request.tx_id, record_id)
                if current["__label"] and current["__label"] != requested:
                    _stage(
                        engine,
                        request.tx_id,
                        {
                            "kind": "retypeRecord",
                            "record": {"id": record_id},
                            "fromLabel": current["__label"],
                            "toLabel": requested,
                        },
                    )
            _stage(
                engine,
                request.tx_id,
                {
                    "kind": "updateRecord",
                    "record": {"id": record_id},
                    "properties": _record_properties(body),
                    "replace": mode == "replace",
                },
            )
            return _ok(_staged_record(engine, request.tx_id, record_id))
        label = requested
        if requested or body.get("vectors"):
            current = _get_record(engine, record_id)
            if requested and current.get("label") and current["label"] != requested:
                engine.execute(
                    {
                        "kind": "mutate",
                        "mutation": {
                            "kind": "retypeRecord",
                            "id": record_id,
                            "fromLabel": current["label"],
                            "toLabel": requested,
                        },
                    }
                )
            label = requested or current.get("label")
        result = engine.execute(
            {
                "kind": "mutate",
                "mutation": {
                    "kind": "putRecord",
                    "mode": mode,
                    "id": record_id,
                    "properties": _record_properties(body),
                    "vectors": _name_inline_vectors(engine, body.get("vectors"), label),
                    "options": body.get("options") or {},
                },
            }
        )
        return _ok(to_sdk_record(result.get("record")))

    return handle


def _search_from(
    engine: DirectEngine, record_id: Optional[str], search: Body
) -> Optional[Body]:
    if not record_id:
        return search
    try:
        label = str(_get_record(engine, record_id).get("label"))
    except RushDBError as error:
        if error.status == 404:
            return None
        raise
    related: Body = {label: {"$id": record_id}}
    where = search.get("where")
    return {
        **search,
        "where": related if _is_empty(where) else {"$and": [where, related]},
    }


def _find_records(request: _Request) -> Body:
    search = _search_from(
        request.engine, request.params[0] if request.params else None, request.body
    )
    if search is None:
        return _ok([], total=0)
    data, total = _search_records(request.engine, search)
    return _ok(data, total=total)


def _ingest(engine: DirectEngine, tx_id: Optional[str], ingest: Body) -> Body:
    """Run an import, or stage it into the transaction (then it reports
    counts, not records)."""
    if tx_id:
        return _stage(engine, tx_id, {"kind": "ingest", "ingest": ingest})
    return engine.execute({"kind": "ingest", "ingest": ingest})


def _import_result(result: Body, return_result: Any) -> Body:
    if return_result and result.get("records"):
        return _ok(_sdk_records(result["records"]))
    return _ok(
        {
            "message": "Records have been successfully imported",
            "count": int(result.get("count") or 0),
        }
    )


_CSV_PARSE_CONFIG_KEYS = (
    "delimiter",
    "header",
    "skipEmptyLines",
    "dynamicTyping",
    "quoteChar",
    "escapeChar",
    "newline",
)


def _import_json(request: _Request) -> Body:
    body = request.body
    result = _ingest(
        request.engine,
        request.tx_id,
        {
            "kind": "documents",
            "label": body.get("label"),
            "documents": _name_document_vectors(
                request.engine, body.get("data"), body.get("label")
            ),
            "options": body.get("options") or {},
        },
    )
    return _import_result(result, (body.get("options") or {}).get("returnResult"))


def _import_csv(request: _Request) -> Body:
    body, engine = request.body, request.engine
    known = _vector_indexes(engine) if body.get("vectors") else []
    vectors = [
        _name_inline_vectors(engine, entries, body.get("label"), known)
        for entries in body.get("vectors") or []
    ]
    parse_config = {
        key: value
        for key, value in (body.get("parseConfig") or {}).items()
        if key in _CSV_PARSE_CONFIG_KEYS
    }
    result = _ingest(
        engine,
        request.tx_id,
        {
            "kind": "csv",
            "label": body.get("label"),
            "data": body.get("data") or "",
            "parseConfig": parse_config,
            "options": body.get("options") or {},
            "vectors": vectors,
        },
    )
    if int(result.get("count") or 0) == 0:
        return _ok(True)
    return _import_result(result, (body.get("options") or {}).get("returnResult"))


def _export_csv(request: _Request) -> Body:
    body = request.body
    result = request.engine.execute(
        {
            "kind": "query",
            "query": {
                "kind": "exportCsv",
                "query": query_document(
                    {
                        "labels": body.get("labels"),
                        "where": body.get("where"),
                        "orderBy": body.get("orderBy"),
                        "skip": (
                            body["skip"] if isinstance(body.get("skip"), int) else 0
                        ),
                        "limit": (
                            body["limit"] if isinstance(body.get("limit"), int) else 100
                        ),
                    }
                ),
            },
        }
    )
    stamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    return _ok({"fileContent": result.get("content"), "dateTime": stamp})


def _delete_record(request: _Request) -> Body:
    record_id = request.params[0]
    if request.tx_id:
        _stage(
            request.engine,
            request.tx_id,
            {"kind": "deleteRecord", "record": {"id": record_id}},
        )
    else:
        request.engine.execute(
            {"kind": "mutate", "mutation": {"kind": "deleteRecord", "id": record_id}}
        )
    return _ok({"message": "Record deleted"})


def _delete_records(request: _Request) -> Body:
    _not_in_transaction(request.tx_id, "records.delete")
    result = request.engine.execute(
        {
            "kind": "mutate",
            "mutation": {
                "kind": "deleteRecords",
                "query": query_document(request.body),
            },
        }
    )
    return _ok({"message": f"{result.get('affected', 0)} records deleted"})


# ── relationships ───────────────────────────────────────────────────────────


def _direction(value: Any) -> str:
    return "in" if str(value or "").lower() == "in" else "out"


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else [value]


def _relationship_command(body: Body) -> Body:
    source, target = body.get("source") or {}, body.get("target") or {}
    return {
        "relationType": body.get("type") or DEFAULT_RELATION_TYPE,
        "direction": _direction(body.get("direction")),
        "allowCartesian": body.get("manyToMany") or False,
        "properties": body.get("properties") or {},
        "source": {
            "label": source.get("label"),
            "property": source.get("key"),
            "predicate": source.get("where") or {},
        },
        "target": {
            "label": target.get("label"),
            "property": target.get("key"),
            "predicate": target.get("where") or {},
        },
    }


def _attach(request: _Request) -> Body:
    body, (source_id,) = request.body, request.params
    relation_type = body.get("type") or DEFAULT_RELATION_TYPE
    inbound = _direction(body.get("direction")) == "in"
    if request.tx_id:
        for target_id in _as_list(body.get("targetIds")):
            _stage(
                request.engine,
                request.tx_id,
                {
                    "kind": "createRelationship",
                    "relationType": relation_type,
                    "source": {"id": target_id if inbound else source_id},
                    "target": {"id": source_id if inbound else target_id},
                    "properties": body.get("properties") or {},
                },
            )
    else:
        request.engine.execute(
            {
                "kind": "mutate",
                "mutation": {
                    "kind": "linkRecordsById",
                    "command": {
                        "relationType": relation_type,
                        "direction": "in" if inbound else "out",
                        "sourceIds": [source_id],
                        "targetIds": _as_list(body.get("targetIds")),
                        "properties": body.get("properties") or {},
                    },
                },
            }
        )
    return _ok(
        {"message": f"Relations to Record {source_id} have been successfully created"}
    )


def _detach(request: _Request) -> Body:
    body, (source_id,) = request.body, request.params
    _not_in_transaction(request.tx_id, "records.detach")
    # No type removes every type, and no direction removes both ways.
    command: Body = {
        "relationTypes": [t for t in _as_list(body.get("typeOrTypes")) if t],
        "sourceIds": [source_id],
        "targetIds": _as_list(body.get("targetIds")),
    }
    direction = str(body.get("direction") or "").lower()
    if direction in ("in", "out"):
        command["direction"] = direction
    request.engine.execute(
        {
            "kind": "mutate",
            "mutation": {"kind": "unlinkRecordsById", "command": command},
        }
    )
    return _ok(
        {"message": f"Relations to Record {source_id} have been successfully deleted"}
    )


def _link_many(kind: str, message: str, what: str) -> Callable[[_Request], Body]:
    def handle(request: _Request) -> Body:
        _not_in_transaction(request.tx_id, what)
        request.engine.execute(
            {
                "kind": "mutate",
                "mutation": {
                    "kind": kind,
                    "command": _relationship_command(request.body),
                },
            }
        )
        return _ok({"message": message})

    return handle


def _find_relationships(request: _Request) -> Body:
    body = request.body
    where = body.get("where") or {}
    source, target = body.get("source") or {}, body.get("target") or {}
    query: Body = {
        "sourceLabels": source.get("labels") or [],
        "targetLabels": target.get("labels") or [],
        "predicate": {key: value for key, value in where.items() if key != "type"},
        "offset": body.get("skip") or 0,
    }
    if where.get("type") is not None:
        query["relationType"] = where["type"]
    if not _is_empty(source.get("where")):
        query["sourcePredicate"] = source["where"]
    if not _is_empty(target.get("where")):
        query["targetPredicate"] = target["where"]
    if body.get("limit") is not None:
        query["limit"] = body["limit"]
    result = request.engine.execute(
        {"kind": "query", "query": {"kind": "relationships", "query": query}}
    )
    return _ok(result.get("relationships") or [], total=result.get("total", 0))


# ── properties and labels ───────────────────────────────────────────────────


def _merge_properties(descriptions: List[Body]) -> List[Body]:
    """``describe.properties`` is per label; the Properties API is per definition."""
    by_id: Dict[str, Body] = {}
    for description in descriptions:
        current = by_id.get(description["id"])
        if current:
            current["recordsCount"] += int(description.get("recordsCount") or 0)
            current["isArray"] = (
                current["isArray"] or description.get("isArray") is True
            )
            continue
        by_id[description["id"]] = {
            "id": description["id"],
            "name": description.get("name"),
            "type": description.get("type"),
            "recordsCount": int(description.get("recordsCount") or 0),
            "isArray": description.get("isArray") is True,
        }
    out = []
    for prop in by_id.values():
        is_array = prop.pop("isArray")
        cardinality = "OrderedMany" if is_array else "Single"
        out.append(
            {
                **prop,
                "metadata": f'{{"cardinality":"{cardinality}","nullability":"Nullable"}}',
            }
        )
    return out


def _properties(engine: DirectEngine, search: Optional[Body] = None) -> List[Body]:
    search = search or {}
    describe: Body = {"kind": "properties", "query": query_document(search)}
    if _is_empty(search.get("where")):
        describe["detail"] = "catalog"
    return _merge_properties(
        engine.execute({"kind": "describe", "describe": describe}).get("properties")
        or []
    )


def _find_property(engine: DirectEngine, property_id: str) -> Optional[Body]:
    for prop in _properties(engine):
        if prop.get("name") == property_id or prop.get("id") == property_id:
            return {**prop, "id": prop.get("id") or prop.get("name")}
    return None


def _property_by_id(request: _Request) -> Body:
    prop = _find_property(request.engine, request.params[0])
    if not prop:
        raise _http_error(404, f"property `{request.params[0]}` does not exist")
    return _ok(prop)


def _delete_property(request: _Request) -> Body:
    _not_in_transaction(request.tx_id, "properties.delete")
    prop = _find_property(request.engine, request.params[0])
    if not prop:
        raise _http_error(404, f"property `{request.params[0]}` does not exist")
    request.engine.execute(
        {"kind": "mutate", "mutation": {"kind": "deleteProperty", "name": prop["name"]}}
    )
    return _ok(
        {"message": f"Property ({request.params[0]}) has been successfully deleted."}
    )


def _property_values(request: _Request) -> Body:
    body = request.body
    result = request.engine.execute(
        {
            "kind": "query",
            "query": {
                "kind": "propertyValues",
                "property": request.params[0],
                "query": query_document(
                    {
                        "labels": body.get("labels") or [],
                        "where": body.get("where") or {},
                    }
                ),
            },
        }
    )
    return _ok({"values": result.get("values") or []})


def _find_labels(request: _Request) -> Body:
    engine, body = request.engine, request.body
    labels = (
        engine.execute(
            {
                "kind": "describe",
                "describe": {"kind": "labels", "query": query_document(body)},
            }
        ).get("labels")
        or []
    )
    counts = {}
    for label in labels:
        counts[label] = _search_records(
            engine, {**body, "labels": [label], "skip": 0, "limit": 1}
        )[1]
    return _ok(counts)


# ── transactions ────────────────────────────────────────────────────────────


def _tx_begin(request: _Request) -> Body:
    transaction: Body = {
        "kind": "begin",
        "autocommit": bool(request.body.get("autocommit")),
    }
    if request.body.get("ttl") is not None:
        transaction["ttlMs"] = request.body["ttl"]
    result = request.engine.execute({"kind": "transaction", "transaction": transaction})
    return _ok({"id": result.get("transactionId")})


def _tx_commit(request: _Request) -> Body:
    tx_id = request.params[0]
    result = request.engine.execute(
        {
            "kind": "transaction",
            "transaction": {"kind": "commit", "transactionId": tx_id},
        }
    )
    if result.get("status") != "committed":
        raise _http_error(
            409,
            f"Transaction commit failed: {result.get('reason') or result.get('status')}",
        )
    return _ok({"message": f"Transaction ({tx_id}) has been successfully committed."})


def _tx_rollback(request: _Request) -> Body:
    tx_id = request.params[0]
    request.engine.execute(
        {
            "kind": "transaction",
            "transaction": {"kind": "rollback", "transactionId": tx_id},
        }
    )
    return _ok({"message": f"Transaction ({tx_id}) has been rolled back."})


# ── statements, schema, indexes, search ─────────────────────────────────────


def _raw_query(request: _Request) -> Body:
    _not_in_transaction(request.tx_id, "query.raw")
    result = request.engine.execute(
        {
            "kind": "query",
            "query": {
                "kind": "statement",
                "language": "cypher",
                "statement": request.body.get("query"),
                "parameters": request.body.get("params"),
            },
        }
    )
    return _ok({"records": result.get("rows") or []})


def _vector_search(request: _Request) -> Body:
    body, engine = request.body, request.engine
    query_vector = body.get("queryVector") or []
    if not query_vector:
        raise CloudOnlyError(
            "records.vector_search", CLOUD_ONLY_FORMS["records.vector_search"]
        )
    indexes = _vector_indexes(engine)
    if isinstance(body.get("index"), str):
        found = [index for index in indexes if index.get("name") == body["index"]]
        if not found:
            raise _http_error(404, f'No vector index named "{body["index"]}"')
        index = found[0]
    else:
        label = (body.get("labels") or [None])[0]
        dimensions = body.get("dimensions") or len(query_vector)
        matches = [
            candidate
            for candidate in indexes
            if candidate.get("label") == label
            and candidate.get("property") == body.get("propertyName")
            and (
                body.get("similarityFunction") is None
                or candidate.get("similarity") == body.get("similarityFunction")
            )
            and int(candidate.get("dimensions") or 0) == dimensions
        ]
        if len(matches) != 1:
            raise _http_error(
                404 if not matches else 422,
                (
                    f'No vector index matches label "{label}", property "{body.get("propertyName")}"'
                    if not matches
                    else f'{len(matches)} vector indexes match label "{label}", property '
                    f'"{body.get("propertyName")}"; name one with `index`'
                ),
            )
        index = matches[0]
    labels = body.get("labels") or [index.get("label")]
    leg = {
        "property": index.get("property"),
        "vector": query_vector,
        "similarity": index.get("similarity") or "cosine",
        "index": index.get("name"),
    }
    for key in ("mode", "ef", "scoreThreshold"):
        if body.get(key) is not None:
            leg[key] = body[key]
    window = {"offset": body.get("skip") or 0, "limit": body.get("limit") or 10}
    text = body.get("text")
    if text:
        text_leg = _text_leg(
            engine, {**text, "query": text.get("query") or body.get("query")}, labels
        )
        hybrid_text = {k: text_leg[k] for k in ("index", "query", "allTerms", "phrase")}
        for key in ("weight", "prefetchLimit"):
            if text.get(key) is not None:
                hybrid_text[key] = text[key]
        vector_leg = dict(leg)
        for key in ("weight", "prefetchLimit"):
            if body.get(key) is not None:
                vector_leg[key] = body[key]
        hybrid: Body = {
            "labels": labels,
            "predicate": body.get("where") or {},
            "vector": vector_leg,
            "text": hybrid_text,
            **window,
        }
        for key in ("fusion", "rrfK"):
            if body.get(key) is not None:
                hybrid[key] = body[key]
        query: Body = {"kind": "hybrid", "query": hybrid}
    else:
        query = {
            "kind": "vector",
            "query": {
                **leg,
                "labels": labels,
                "predicate": body.get("where") or {},
                **window,
            },
        }
    result = engine.execute({"kind": "query", "query": query})
    data = _sdk_records(result.get("records"))
    return _ok(
        data,
        total=len(data),
        meta={
            "vectorSearch": result.get("vectorSearch"),
            "textSearch": result.get("textSearch"),
            "fusion": result.get("fusion"),
        },
    )


def _text_leg(engine: DirectEngine, text: Body, labels: List[str]) -> Body:
    """The text leg of a hybrid search: the named text index, or the one ready
    text index of the first label."""
    query = text.get("query")
    if not isinstance(query, str) or not query.strip():
        raise _http_error(422, "text.query is required")
    indexes = _text_indexes(engine)
    if text.get("index") is not None:
        found = [index for index in indexes if index["name"] == text["index"]]
        if not found:
            raise _http_error(404, f'No text index named "{text["index"]}"')
        index = found[0]
    else:
        label = labels[0] if labels else None
        if not label:
            raise _http_error(422, "Name a text index with `index`, or give `labels`")
        candidates = [
            index
            for index in indexes
            if index["label"] == label
            and index["status"] == "ready"
            and (text.get("property") is None or index["property"] == text["property"])
        ]
        if not candidates:
            raise _http_error(404, f'No ready text index on label "{label}"')
        if len(candidates) > 1:
            names = ", ".join(index["name"] for index in candidates)
            raise _http_error(
                422,
                f'Label "{label}" has several text indexes ({names}); name one with `index`',
            )
        index = candidates[0]
    return {
        "index": index["name"],
        "label": index["label"],
        "query": query,
        "allTerms": bool(text.get("allTerms")),
        "phrase": bool(text.get("phrase")),
    }


# ── text indexes and keyword search ─────────────────────────────────────────


def _taken_index_names(engine: DirectEngine) -> set:
    return {str(index.get("name")) for index in _declared_indexes(engine)}


def _create_text_index(request: _Request) -> Body:
    body, engine = request.body, request.engine
    taken = _taken_index_names(engine)
    if body.get("name") is not None and body["name"] in taken:
        raise _http_error(409, f'An index named "{body["name"]}" already exists')
    result = engine.execute(
        {
            "kind": "index",
            "index": {
                "kind": "create",
                "definition": {
                    "name": body.get("name")
                    or _first_free(_default_text_index_name(body), taken),
                    "label": body.get("label"),
                    "property": body.get("property"),
                    "kind": "text",
                    "consistency": body.get("consistency") or "eventual",
                },
            },
        }
    )
    return _ok(_to_text_index(result.get("index") or {}))


def _suggest_text_index_name(request: _Request) -> Body:
    taken = _taken_index_names(request.engine)
    return _ok({"name": _first_free(_default_text_index_name(request.body), taken)})


def _drop_text_index(request: _Request) -> Body:
    name = request.params[0]
    if not any(index["name"] == name for index in _text_indexes(request.engine)):
        raise _http_error(404, f'No text index named "{name}"')
    request.engine.execute({"kind": "index", "index": {"kind": "drop", "name": name}})
    return _ok({"deleted": True})


def _text_search(request: _Request) -> Body:
    body, engine = request.body, request.engine
    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise _http_error(422, "query is required")
    labels = body.get("labels") or []
    leg = _text_leg(engine, body, labels)
    result = engine.execute(
        {
            "kind": "query",
            "query": {
                "kind": "hybrid",
                "query": {
                    "labels": labels or [leg["label"]],
                    "predicate": body.get("where") or {},
                    "text": {
                        key: leg[key]
                        for key in ("index", "query", "allTerms", "phrase")
                    },
                    "offset": body.get("skip") or 0,
                    "limit": body.get("limit") or 10,
                },
            },
        }
    )
    data = _sdk_records(result.get("records"))
    report = result.get("textSearch")
    return _ok(
        data,
        total=(report or {}).get("matches", len(data)),
        meta={"textSearch": report},
    )


def _create_vector_index(request: _Request) -> Body:
    body, engine = request.body, request.engine
    if body.get("sourceType") != "external" and body.get("external") is not True:
        raise CloudOnlyError("ai.indexes.create", CLOUD_ONLY_FORMS["ai.indexes.create"])
    dimensions = body.get("dimensions")
    if not isinstance(dimensions, int) or not 1 <= dimensions <= 4096:
        raise _http_error(422, "dimensions must be an integer between 1 and 4096")
    similarity = body.get("similarityFunction") or "cosine"
    existing = _vector_indexes(engine)
    for index in existing:
        if (
            index.get("label") == body.get("label")
            and index.get("property") == body.get("propertyName")
            and index.get("similarity") == similarity
            and int(index.get("dimensions") or 0) == dimensions
        ):
            raise _http_error(
                409,
                f'An embedding index for label "{body.get("label")}", property "{body.get("propertyName")}", '
                f'sourceType "external", similarityFunction "{similarity}", and dimensions {dimensions} '
                f'already exists ("{index.get("name")}")',
            )
    taken = {str(index.get("name")) for index in existing}
    if body.get("name") is not None and body["name"] in taken:
        raise _http_error(
            409, f'An embedding index named "{body["name"]}" already exists'
        )
    result = engine.execute(
        {
            "kind": "index",
            "index": {
                "kind": "createVector",
                "definition": {
                    "label": body.get("label"),
                    "property": body.get("propertyName"),
                    "dimensions": dimensions,
                    "similarity": similarity,
                    "name": body.get("name")
                    or _first_free(
                        _default_vector_index_name(body, dimensions, similarity), taken
                    ),
                },
            },
        }
    )
    return _ok(to_embedding_index(result.get("index") or {}))


def _index_stats(request: _Request) -> Body:
    result = request.engine.execute(
        {
            "kind": "describe",
            "describe": {"kind": "vectorIndex", "name": request.params[0]},
        }
    )
    stats = result.get("stats") or {}
    return _ok({**stats, "index": to_embedding_index(stats.get("index") or {})})


def _upsert_vectors(request: _Request) -> Body:
    result = request.engine.execute(
        {
            "kind": "index",
            "index": {
                "kind": "upsertVectors",
                "name": request.params[0],
                "items": request.body.get("items") or [],
            },
        }
    )
    return _ok({"updated": result.get("updated"), "requested": result.get("requested")})


def _drop_vector_index(request: _Request) -> Body:
    request.engine.execute(
        {"kind": "index", "index": {"kind": "dropVector", "name": request.params[0]}}
    )
    return _ok({"deleted": True, "queued": False})


# ── routes ──────────────────────────────────────────────────────────────────

_ID = r"([^/]+)"


_ROUTES: List[Tuple[str, "re.Pattern[str]", Callable[[_Request], Body]]] = [
    (
        "GET",
        re.compile(rf"^/records/{_ID}$"),
        lambda r: _ok(to_sdk_record(_get_record(r.engine, r.params[0]))),
    ),
    ("POST", re.compile(r"^/records$"), _create_record),
    ("PATCH", re.compile(rf"^/records/{_ID}$"), _put_record("merge")),
    ("PUT", re.compile(rf"^/records/{_ID}$"), _put_record("replace")),
    ("DELETE", re.compile(rf"^/records/{_ID}$"), _delete_record),
    ("POST", re.compile(r"^/records/delete$"), _delete_records),
    ("POST", re.compile(r"^/records/search$"), _find_records),
    ("POST", re.compile(rf"^/records/{_ID}/search$"), _find_records),
    ("POST", re.compile(r"^/records/import/json$"), _import_json),
    ("POST", re.compile(r"^/records/import/csv$"), _import_csv),
    ("POST", re.compile(r"^/records/export/csv$"), _export_csv),
    ("POST", re.compile(rf"^/relationships/{_ID}$"), _attach),
    ("PUT", re.compile(rf"^/relationships/{_ID}$"), _detach),
    (
        "POST",
        re.compile(r"^/relationships/create-many$"),
        _link_many(
            "linkRecords",
            "Relations have been successfully created",
            "relationships.create_many",
        ),
    ),
    (
        "POST",
        re.compile(r"^/relationships/delete-many$"),
        _link_many(
            "unlinkRecords",
            "Relations have been successfully deleted",
            "relationships.delete_many",
        ),
    ),
    ("POST", re.compile(r"^/relationships/search$"), _find_relationships),
    (
        "GET",
        re.compile(r"^/relationships/patterns$"),
        _cloud_only("relationships.patterns.list"),
    ),
    (
        "POST",
        re.compile(r"^/relationships/patterns/analyze$"),
        _cloud_only("relationships.patterns.analyze"),
    ),
    (
        "POST",
        re.compile(rf"^/relationships/patterns/{_ID}/approve$"),
        _cloud_only("relationships.patterns.approve"),
    ),
    (
        "POST",
        re.compile(rf"^/relationships/patterns/{_ID}/ignore$"),
        _cloud_only("relationships.patterns.ignore"),
    ),
    (
        "DELETE",
        re.compile(rf"^/relationships/patterns/{_ID}$"),
        _cloud_only("relationships.patterns.delete"),
    ),
    (
        "POST",
        re.compile(r"^/properties/search$"),
        lambda r: _ok(
            _properties(
                r.engine,
                {
                    "labels": r.body.get("labels") or [],
                    "where": r.body.get("where") or {},
                },
            )
        ),
    ),
    ("GET", re.compile(rf"^/properties/{_ID}$"), _property_by_id),
    ("DELETE", re.compile(rf"^/properties/{_ID}$"), _delete_property),
    ("POST", re.compile(rf"^/properties/{_ID}/values$"), _property_values),
    ("POST", re.compile(r"^/labels/search$"), _find_labels),
    ("POST", re.compile(r"^/tx$"), _tx_begin),
    ("GET", re.compile(rf"^/tx/{_ID}$"), lambda r: _ok({"id": r.params[0]})),
    ("POST", re.compile(rf"^/tx/{_ID}/commit$"), _tx_commit),
    ("POST", re.compile(rf"^/tx/{_ID}/rollback$"), _tx_rollback),
    ("POST", re.compile(r"^/query/raw$"), _raw_query),
    (
        "POST",
        re.compile(r"^/ai/schema$"),
        lambda r: _ok(build_schema(r.engine, r.body.get("labels"), to_embedding_index)),
    ),
    (
        "POST",
        re.compile(r"^/ai/schema/md$"),
        lambda r: _ok(
            build_schema_markdown(
                build_schema(r.engine, r.body.get("labels"), to_embedding_index)
            )
        ),
    ),
    ("GET", re.compile(r"^/text-indexes$"), lambda r: _ok(_text_indexes(r.engine))),
    ("POST", re.compile(r"^/text-indexes$"), _create_text_index),
    (
        "POST",
        re.compile(r"^/text-indexes/name-suggestion$"),
        _suggest_text_index_name,
    ),
    ("DELETE", re.compile(rf"^/text-indexes/{_ID}$"), _drop_text_index),
    ("POST", re.compile(r"^/search/text$"), _text_search),
    ("POST", re.compile(r"^/ai/search-query$"), _cloud_only("ai.search")),
    ("POST", re.compile(r"^/ai/search$"), _vector_search),
    (
        "GET",
        re.compile(r"^/ai/indexes$"),
        lambda r: _ok(
            [to_embedding_index(index) for index in _vector_indexes(r.engine)]
        ),
    ),
    ("POST", re.compile(r"^/ai/indexes$"), _create_vector_index),
    ("DELETE", re.compile(rf"^/ai/indexes/{_ID}$"), _drop_vector_index),
    ("GET", re.compile(rf"^/ai/indexes/{_ID}/stats$"), _index_stats),
    ("POST", re.compile(rf"^/ai/indexes/{_ID}/vectors/upsert$"), _upsert_vectors),
    ("GET", re.compile(r"^/sdk/settings$"), _cloud_only("settings.get")),
]


def handle(
    engine: DirectEngine,
    method: str,
    path: str,
    data: Optional[Body] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Body] = None,
) -> Body:
    """Answer one SDK REST call from the engine."""
    path = "/" + "/".join(
        urllib.parse.unquote(part) for part in path.split("/") if part
    )
    candidates = [
        (pattern, handler)
        for verb, pattern, handler in _ROUTES
        if verb == method and pattern.match(path)
    ]
    if not candidates:
        raise DirectModeError(f"{method} {path} has no direct-mode mapping")
    # A literal path (`/relationships/search`) wins over a parameter (`/relationships/{id}`).
    pattern, handler = min(
        candidates, key=lambda candidate: candidate[0].pattern.count("(")
    )
    match = pattern.match(path)
    assert match is not None
    tx_id = next(
        (
            value
            for key, value in (headers or {}).items()
            if key.lower() == "x-transaction-id"
        ),
        None,
    )
    return handler(
        _Request(
            data or {},
            tuple(g for g in match.groups() if g is not None),
            params or {},
            tx_id,
            engine,
        )
    )


__all__ = ["handle", "query_document", "to_sdk_record", "to_embedding_index"]
