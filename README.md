# RushDB Python SDK

A modern Python client for RushDB, a graph database built for modern applications.

## Installation

```bash
pip install rushdb
```

## Quick Start

```python
from rushdb import RushDBClient

# Initialize the client
client = RushDBClient("http://localhost:8000", "your-api-key")

# Create a record
record = client.records.create({
    "name": "John Doe",
    "age": 30,
    "email": "john@example.com"
})

# Find records
results = client.records.find({
    "where": {
        "age": {"$gt": 25},
        "status": "active"
    },
    "orderBy": {"created_at": "desc"},
    "limit": 10
})

# Create relations
client.records.attach(
    source_id="user123",
    target_ids=["order456"],
    relation_type="PLACED_ORDER"
)

# Use transactions
tx_id = client.transactions.begin()
try:
    client.records.create({"name": "Alice"}, transaction_id=tx_id)
    client.records.create({"name": "Bob"}, transaction_id=tx_id)
    client.transactions.commit(tx_id)
except Exception:
    client.transactions.rollback(tx_id)
    raise
```

## Features

- Full TypeScript-like type hints
- Transaction support
- Comprehensive query builder
- Graph traversal
- Property management
- Label management
- Error handling
- Connection pooling (with requests)

## API Documentation

### Records API

```python
client.records.find(query)  # Find records matching query
client.records.find_by_id(id_or_ids)  # Find records by ID(s)
client.records.find_one(query)  # Find single record
client.records.find_unique(query)  # Find unique record
client.records.create(data)  # Create record
client.records.create_many(data)  # Create multiple records
client.records.delete(query)  # Delete records matching query
client.records.delete_by_id(id_or_ids)  # Delete records by ID(s)
client.records.attach(source_id, target_ids, relation_type)  # Create relations
client.records.detach(source_id, target_ids, type_or_types)  # Remove relations
client.records.export(query)  # Export records to CSV
```

### Properties API

```python
client.properties.list()  # List all properties
client.properties.create(data)  # Create property
client.properties.get(property_id)  # Get property
client.properties.update(property_id, data)  # Update property
client.properties.delete(property_id)  # Delete property
client.properties.get_values(property_id)  # Get property values
```

### Labels API

```python
client.labels.list()  # List all labels
client.labels.create(label)  # Create label
client.labels.delete(label)  # Delete label
```

### Transactions API

```python
client.transactions.begin()  # Start transaction
client.transactions.commit(transaction_id)  # Commit transaction
client.transactions.rollback(transaction_id)  # Rollback transaction
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m unittest discover tests
```

## License

MIT License 