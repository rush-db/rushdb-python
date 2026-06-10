<div align="center">

![RushDB Logo](https://raw.githubusercontent.com/rush-db/rushdb/main/rushdb-logo.svg)

# RushDB — Python SDK

### The memory layer for AI agents and apps.

Push any JSON. Get graph relationships and vector search — automatically.
No schema. No pipeline. No glue code.

![PyPI - Version](https://img.shields.io/pypi/v/rushdb)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rushdb)
![PyPI - License](https://img.shields.io/pypi/l/rushdb)

[📖 Documentation](https://docs.rushdb.com/python-sdk/introduction) • [🌐 Website](https://rushdb.com) • [☁️ Cloud](https://app.rushdb.com)

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
```

---

## Importing CSV

```python
csv_data = "name,email,age\nJohn,john@example.com,30\nJane,jane@example.com,25"

db.records.import_csv(
    label='USER',
    data=csv_data,
    options={'returnResult': True, 'suggestTypes': True},
    parse_config={'header': True, 'skipEmptyLines': True, 'dynamicTyping': True},
)
```

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
    url='http://your-rushdb-server.com/api/v1',  # default: https://api.rushdb.com/api/v1
    timeout=30,
)
```

---

## Documentation

[docs.rushdb.com/python-sdk](https://docs.rushdb.com/python-sdk/introduction) — full API reference, vector search, aggregations, and more.

---

## Support

- [GitHub Issues](https://github.com/rush-db/rushdb-python/issues) — bug reports and feature requests
- [Email](mailto:support@rushdb.com) — direct support

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.
