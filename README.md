<div align="center">

![RushDB Logo](https://raw.githubusercontent.com/rush-db/rushdb/main/rushdb-logo.svg)

# RushDB — Python SDK

### RushDB — the database for AI

One database for your records, their relationships, and search over them.

![PyPI - Version](https://img.shields.io/pypi/v/rushdb)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rushdb)
![PyPI - License](https://img.shields.io/pypi/l/rushdb)

[📖 Documentation](https://docs.rushdb.com/3.x/connect/sdks/) • [🌐 Website](https://rushdb.com) • [☁️ Cloud](https://app.rushdb.com)

</div>

---

## Why RushDB

Agents need memory. Apps need connected data. The standard answer involves multiple databases, schema design, and an embedding pipeline before you write a single useful line of business logic.

RushDB skips all of that. Push any JSON — nested structure becomes a traversable graph, string properties become semantically searchable, type inference happens automatically.

Works with LangChain, CrewAI, AutoGen, or any Python AI framework.

---

## Installation

```bash
pip install rushdb
```

---

## Compatibility

| Package | RushDB 3.x and RushDB Cloud | RushDB 2.x (legacy) |
|---|---|---|
| `@rushdb/javascript-sdk` | 3.x | 2.11.0: `npm i @rushdb/javascript-sdk@2` |
| `rushdb` (PyPI) | 3.x | 2.10.0: `pip install "rushdb<3"` |
| `@rushdb/mcp-server` | 3.x | 2.13.0: `npx @rushdb/mcp-server@2` |

---

## RushDB Cloud or a self-hosted engine

The SDK works with RushDB in one of two ways:

| | RushDB Cloud | Self-hosted RushDB engine (direct mode) |
| --- | --- | --- |
| What you run | nothing: the managed service at [app.rushdb.com](https://app.rushdb.com) | one `rushdb` binary, on your own infrastructure |
| Connect with | an API key | the engine URL and the engine token |

The engine is what you can self-host. RushDB Cloud runs that engine for you and adds the dashboard,
managed embeddings and the AI features (natural-language search, relationship-pattern and join suggestions),
which exist only in RushDB Cloud.

```python
from rushdb import RushDB

# RushDB Cloud
db = RushDB("RUSHDB_API_KEY")

# A self-hosted engine
db = RushDB(
    "ENGINE_TOKEN",
    direct=True,
    engine_url="http://127.0.0.1:3000",
    scope="tenant-1",  # only for an engine started with --multitenant
)
```

What each offers:

| Feature | Cloud | Self-hosted engine |
| --- | :---: | :---: |
| Records: create, read, update, set, upsert, delete, `find` with `where`, `orderBy`, `select`, `groupBy` | ✓ | ✓ |
| Relationships: `attach`/`detach`, `relationships.create_many`/`delete_many`/`find`/`update` | ✓ | ✓ |
| Labels, properties, property values | ✓ | ✓ |
| Import JSON and CSV, export CSV | ✓ | ✓ |
| External vector indexes; vector search with a `queryVector` you supply | ✓ | ✓ |
| Raw openCypher (`query.raw`; the engine needs `--languages cypher`) | ✓ | ✓ |
| Schema (`ai.get_schema`, `ai.get_schema_markdown`) | ✓ | ✓ |
| Catalog lookups: `ai.search_values` (a value across every property, also near spellings), `ai.get_schema_summary`, `ai.resolve_names`, and value search in `properties.values` (`query`, `match`, `domain_on_miss`) | ✓ | ✓ |
| Keyword (BM25) search (`records.text_search`), text indexes (`text_indexes.*`), hybrid search | ✓ | ✓ |
| Transactions | ✓ | record creates, updates, sets, deletes by id, attaches and imports are staged; other writes refuse a transaction |
| Managed embeddings: managed indexes, `records.vector_search` by text `query` | ✓ | — |
| Natural-language search on SQL (`ai.search`, `ai.run_sql`) | ✓ | — |
| Relationship-pattern suggestions (`relationships.patterns.*`) and join suggestions (`ai.get_join_candidates`) | ✓ | — |
| Background file imports (`imports.*`) and SaaS connections (`connections.*`) | ✓ | — |
| Project settings (`settings.get`), dashboard, team access | ✓ | — |

In direct mode a Cloud-only method raises `CloudOnlyError` (with `method` and `reason`) before
sending anything, and no request ever goes to RushDB Cloud. A write the engine cannot stage into a
transaction raises `DirectModeError`, also before sending anything. The list is available in code:

```python
from rushdb import CLOUD_ONLY_METHODS, CloudOnlyError, is_cloud_only_method
```

`db.engine.execute()` runs any Protocol v1 operation directly.

---

## Agent memory in 3 lines

Get an API key at [app.rushdb.com](https://app.rushdb.com).

```python
from rushdb import RushDB

db = RushDB('RUSHDB_API_KEY')

# Store an agent action — graph links sessions and context automatically
db.records.create(
    label='MEMORY',
    data={
        'agent_id': 'agent-42',
        'session_id': 'sess-001',
        'action': 'summarized',
        'topic': 'Q4 results',
        'output': summary_text,
    },
)

# Recall — traverse relationships, filter by properties
results = db.records.find({
    'labels': ['MEMORY'],
    'where': {
        'agent_id': 'agent-42',
        'topic': {'$contains': 'Q4'},
    },
    'limit': 10,
})

for memory in results:
    print(memory.get('output'))
```

---

## Graph traversal

```python
# Push nested JSON — relationships created automatically
db.records.create_many('COMPANY', {
    'name': 'Acme Corp',
    'DEPARTMENT': [{
        'name': 'Engineering',
        'EMPLOYEE': [{
            'name': 'Alice',
            'role': 'Staff Engineer',
        }]
    }]
})

# Traverse the auto-created graph
engineers = db.records.find({
    'labels': ['EMPLOYEE'],
    'where': {
        'role': {'$contains': 'Engineer'},
        'DEPARTMENT': {'COMPANY': {'name': 'Acme Corp'}},
    },
})

# Constrain by relationship type and direction
authored_posts = db.records.find({
    'labels': ['USER'],
    'where': {
        'POST': {
            '$relation': {'type': 'AUTHORED', 'direction': 'out'},
            'title': {'$contains': 'graph'},
        }
    },
    'limit': 10,
})

# Multi-hop: add hops to $relation — everyone in Alice's reporting chain, up to 4 levels
chain = db.records.find({
    'labels': ['EMPLOYEE'],
    'where': {
        'EMPLOYEE': {
            '$relation': {'type': 'REPORTS_TO', 'direction': 'out', 'hops': {'min': 1, 'max': 4}},
            'name': {'$contains': 'Alice'},
        }
    },
})

# Cycle detection: accounts on a circular transfer ring (fraud rings, circular ownership)
ring_members = db.records.find({
    'labels': ['ACCOUNT'],
    'where': {
        'RING': {  # key is a display name — the $cycle block holds only $relation
            '$cycle': True,
            '$relation': {'type': 'TRANSFERRED_TO', 'direction': 'out', 'hops': {'min': 2, 'max': 6}},
        }
    },
})

# Manage relationships explicitly
user = db.records.find_uniq({'labels': ['USER'], 'where': {'name': 'Alice'}})
company = db.records.find_uniq({'labels': ['COMPANY'], 'where': {'name': 'Acme Corp'}})
user.attach(
    target=company,
    options={'type': 'WORKS_AT', 'direction': 'out', 'properties': {'source': 'profile'}},
)

# Relationship search: where filters edge type/properties, source/target filter endpoint records
relationships = db.relationships.find({
    'source': {'labels': ['USER'], 'where': {'name': 'Alice'}},
    'target': {'labels': ['COMPANY']},
    'where': {'type': 'WORKS_AT', 'source': 'profile'},
})

# Change properties on existing relationships (RushDB 3.0.4+): set writes, unset removes
db.relationships.update(user, company, type='WORKS_AT', set={'source': 'hr'}, unset=['legacy'])
# types marks values JSON can't type: 'datetime' stores an ISO string as a datetime
db.relationships.update(
    user, company, type='WORKS_AT', set={'since': '2024-03-01'}, types={'since': 'datetime'}
)
```

---

## Importing CSV

```python
csv_data = "name,email,age\nJohn,john@example.com,30\nJane,jane@example.com,25"

db.records.import_csv(
    label='USER',
    data=csv_data,
    # skipEmptyValues: treat empty cells ("" / []) as unset instead of storing them (0/False are kept)
    options={'returnResult': True, 'suggestTypes': True, 'skipEmptyValues': True},
    parse_config={'header': True, 'skipEmptyLines': True, 'dynamicTyping': True},
)
```

---

## File imports and connections (RushDB Cloud)

Large files and SaaS data load in the background: the client hands the data over and the run
continues on the server. Every file import and every connection sync is an **import run**; follow it
with `db.imports.get(id)` or `db.imports.wait(id)` until its status is `completed`, `partial`,
`failed` or `cancelled`.

### Import files

```python
# One call: create → upload every file → start (→ wait)
run = db.imports.import_files(
    [
        {'data': 'customers.csv', 'label': 'Customer'},  # a path: name and size come from it
        open('orders.csv.gz', 'rb'),                     # a binary file object works too
    ],
    mappings={0: {'keyColumn': 'id'}},  # re-importing upserts by `id`
    links=[{'source': 1, 'sourceColumn': 'customer_id', 'target': 0, 'targetColumn': 'id', 'type': 'PLACED_BY'}],
    parallelism=4,
    wait=True,
    wait_interval=2,
    on_progress=lambda p: print(f"{p['loaded']}/{p['total']}" if p['phase'] == 'upload' else p['run']['status']),
)
print(run.data['recordsWritten'], run.data['summary'])
```

Or step by step, to show a preview before starting:

```python
import os

created = db.imports.create([{'name': 'orders.csv', 'size': os.path.getsize('orders.csv')}]).data
db.imports.upload(created['id'], created['files'][0], 'orders.csv', parallelism=4, retries=3)
preview = db.imports.preview(created['id']).data  # column types, suggested key and links, personal data
columns = preview['files'][0]['columns']  # each has `suggestion` ('include' | 'skip' | 'hash') and `pii` when it looks personal
mapping = {
    'skip': [c['name'] for c in columns if c['suggestion'] == 'skip'],
    'hash': [c['name'] for c in columns if c['suggestion'] == 'hash'],  # keyed hash: joins, not readable
}
if preview['files'][0].get('suggestedKey'):
    mapping['keyColumn'] = preview['files'][0]['suggestedKey']
db.imports.start(created['id'], files=[{'id': created['files'][0]['id'], 'mapping': mapping}])
finished = db.imports.wait(created['id'], timeout=30 * 60).data  # TimeoutError after 30 minutes
```

`upload` follows the upload mode the server returns: `s3-multipart` sends parts to their presigned
URLs (`parallelism` at a time on a thread pool, default 4; each failed part retried, `retries`
default 3) and completes with their ETags; `direct` sends the bytes through the API. Upload data can
be a file path (`str` or `Path`), `bytes`/`bytearray`/`memoryview`, or a binary file object (read
from its current position). A non-seekable stream (a pipe, a socket) needs its `size` up front in
`import_files`, and a direct upload of one is not retried.

Also: `imports.list(kind=, connection_id=, limit=, skip=)`, `cancel`, `retry`, `delete`,
`add_files`, `remove_file`.

### Connections

```python
import os

catalog = db.connections.catalog().data  # connectors with their streams and config fields

created = db.connections.create({
    'connectorId': 'hubspot',
    'auth': {'type': 'bearer', 'token': os.environ['HUBSPOT_TOKEN']},
    'mode': 'scheduled',
    'scheduleMinutes': 60,
    'streams': [{'stream': 'contacts', 'policy': {'mode': 'auto', 'exclude': ['mobilephone']}}],
}).data
connection_id = created['connection']['id']
db.connections.test(connection_id)
db.connections.preview(connection_id, 'contacts')  # first records, nothing written

# Field review: profiles with personal-data findings (masked examples), the policy, unreviewed fields
review = db.connections.fields(connection_id, 'contacts', limit=100).data
db.connections.review_fields(
    connection_id,
    'contacts',
    [{'name': f['name'], 'action': f['suggestion']} for f in review['fields']],  # or your own choices
)

sync_run = db.connections.sync(connection_id).data  # or sync(connection_id, streams=['contacts'], full=True)
db.imports.wait(sync_run['id'])
```

A stream's `policy` decides which fields reach the graph: `auto` keeps everything except `exclude`
and `hash`; `review_fields` switches it to an `allowlist` of the fields marked `include` or `hash`,
and fields that appear later wait in the stream's `unreviewed` list until the next review.

On-prem databases sync through `rushdb-agent`: create an agent connection and hand the token
(shown once) to the agent.

```python
agent = db.connections.create({'connectorId': 'agent', 'name': 'Warehouse', 'agent': {'intervalMinutes': 15}}).data
print(agent['agentToken'])  # connection['agent'] shows what the agent last reported
```

Also: `list`, `get`, `update`, `delete(id, delete_data=True)`, `runs(id, limit=, skip=)`, `pause`,
`resume`, `rotate_webhook_token` (a new webhook URL, or a new agent token), `push_templates()`
(Zapier, Make and n8n recipes for push connections). Credentials are sealed on the server and never
returned.

---

## SearchResult

`db.records.find()` returns a `SearchResult` — a list-like container with pagination metadata.

```python
result = db.records.find({
    'where': {'status': 'active'},
    'limit': 10,
    'skip': 0,
})

# List-like usage
print(f"Loaded {len(result)} of {result.total} total")
print(f"Has more: {result.has_more}")

for record in result:
    print(record.get('name'))

# Indexing and slicing
first = result[0]
top_five = result[:5]

# Boolean check
if result:
    process(result[0])
```

| Property       | Type           | Description                                 |
| -------------- | -------------- | ------------------------------------------- |
| `data`         | `List[Record]` | The result items                            |
| `total`        | `int`          | Total matching records in the database      |
| `has_more`     | `bool`         | Whether more records exist beyond this page |
| `search_query` | `dict`         | The query that produced this result         |
| `sql`          | `str`          | For Smart search, the SQL statement it ran  |

---

## Vector Search And Smart Search

Use `db.records.vector_search()` for direct semantic/vector retrieval over an
embedding index:

```python
results = db.records.vector_search({
    'labels': ['MEMORY'],
    'propertyName': 'content',
    'query': 'how agents remember things',
    'where': {'agent_id': 'agent-42'},
    'limit': 5,
})

for record in results:
    print(record.score, record.get('content'))
```

Use `db.ai.search()` when you want RushDB to turn a natural-language request
into one read-only SQL statement over your schema and run it (RushDB Cloud):

```python
results = db.ai.search('Find active memories about Q4 results for agent-42')
print(results.name)  # a short title, e.g. to save the query under
print(results.sql)   # the statement it ran
more = results.next()  # the next page of the statement's rows

# Run a statement directly, e.g. a saved one:
rows = db.ai.run_sql('SELECT agent_id, count(*) AS memories FROM "MEMORY" GROUP BY agent_id')
```

Rows that select a record's `__id` come back as full records; aggregates come
back as plain rows.

`db.ai.search({...})` still works as a deprecated vector-search alias, but new
code should use `db.records.vector_search({...})`.

## Keyword And Hybrid Search

Declare a BM25 text index, then search it by keywords:

```python
db.text_indexes.create({'label': 'MEMORY', 'property': 'content'})

results = db.records.text_search({
    'query': 'quarterly results',
    'labels': ['MEMORY'],
    'where': {'agent_id': 'agent-42'},
    'limit': 5,
})
print(results.total, results.meta['textSearch'])
```

Add a `text` leg to a vector search to fuse keyword and vector ranking. `fusion`
is `rrf` (default) or `dbsf`; `weight` and `prefetchLimit` tune each leg:

```python
results = db.records.vector_search({
    'labels': ['MEMORY'],
    'propertyName': 'content',
    'queryVector': embedding,
    'text': {'query': 'quarterly results', 'weight': 0.5},
    'fusion': 'dbsf',
    'limit': 5,
})
```

## Catalog Lookups

Map the words of a question to what the data actually stores before building a
query. Each is one read of the live catalog:

```python
# Where is a value stored? Every property, with label, property and record count
found = db.ai.search_values('spiderman', match='similar')  # contains | prefix | exact | similar
for m in found.data['matches']:
    print(m['label'], m['property'], m['value'], m['count'])

# Every label with its properties, distinct counts, ranges and the values of small fields
summary = db.ai.get_schema_summary(labels=['Patient'], few_values=10)

# The real label or property behind a name that is not in the schema
db.ai.resolve_names('patients.birthdate')  # -> Patient.Birthday

# Value search within one property: ranked by record count, with counts;
# when nothing matches, list the whole domain of a small property
db.properties.values(property_id, query='positive', domain_on_miss=20)

# How labels reference each other, with evidence (RushDB Cloud only)
db.ai.get_join_candidates(labels=['Order'], min_confidence=0.5)
```

---

## Record API

```python
user = db.records.create('USER', {
    'name': 'Alice',
    'email': 'alice@example.com',
})

# Safe field access
name = user.get('name')                  # 'Alice'
phone = user.get('phone', 'N/A')         # 'N/A'

# Clean data (excludes internal __id, __label fields)
data = user.get_data()                   # {'name': 'Alice', 'email': '...'}
full = user.get_data(exclude_internal=False)  # includes __id, __label, etc.

# Existence check (no exception if record was deleted)
if user.exists:
    user.update({'status': 'active'})

# String representations
repr(user)   # Record(id='abc-123', label='USER')
str(user)    # USER: Alice
```

---

## Transactions

```python
with db.transactions.begin() as tx:
    record_a = db.records.create('NODE', {'value': 1}, transaction=tx)
    record_b = db.records.create('NODE', {'value': 2}, transaction=tx)
    record_a.attach(target=record_b, options={'type': 'LINKED'}, transaction=tx)
# auto-committed on exit, rolled back on exception
```

---

## Configuration

```python
from rushdb import RushDB

db = RushDB(
    'RUSHDB_API_KEY',
    url='https://api.rushdb.com/api/v1',  # a different RushDB Cloud API endpoint; this is the default
    timeout=30,
)
```

---

## Documentation

[docs.rushdb.com/3.x/connect/sdks](https://docs.rushdb.com/3.x/connect/sdks/) and the [Python reference](https://docs.rushdb.com/3.x/learn/reference/python/) — full API reference, vector search, aggregations, and more.

---

## Support

- [GitHub Issues](https://github.com/rush-db/rushdb-python/issues) — bug reports and feature requests
- [Email](mailto:support@rushdb.com) — direct support

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.
