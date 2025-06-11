<div align="center">

![RushDB Logo](https://raw.githubusercontent.com/rush-db/rushdb/main/rushdb-logo.svg)

# RushDB Python SDK

![PyPI - Version](https://img.shields.io/pypi/v/rushdb)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/rushdb)
![PyPI - License](https://img.shields.io/pypi/l/rushdb)

RushDB is an instant database for modern apps and DS/ML ops built on top of Neo4j.
It automates data normalization, manages relationships, and infers data types.

[📖 Documentation](https://docs.rushdb.com/python-sdk/introduction) • [🌐 Website](https://rushdb.com) • [☁️ Cloud Platform](https://app.rushdb.com)

</div>

## Installation

```sh
pip install rushdb
```

## Quick Start

```python
from rushdb import RushDB

# Initialize the client
db = RushDB("YOUR_API_TOKEN")

# Create a record
user = db.records.create(
    label="USER",
    data={
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30
    }
)

# Find records
result = db.records.find({
    "where": {
        "age": {"$gte": 18},
        "name": {"$startsWith": "J"}
    },
    "limit": 10
})

# Work with SearchResult
print(f"Found {len(result)} records out of {result.total} total")

# Iterate over results
for record in result:
    print(f"User: {record.get('name')} (Age: {record.get('age')})")

# Check if there are more results
if result.has_more:
    print("There are more records available")

# Access specific records
first_user = result[0] if result else None

# Create relationships
company = db.records.create(
    label="COMPANY",
    data={"name": "Acme Inc."}
)

# Attach records with a relationship
user.attach(
    target=company,
    options={"type": "WORKS_AT", "direction": "out"}
)
```

## Pushing Nested JSON

RushDB automatically normalizes nested objects into a graph structure:

```python
# Push nested JSON with automatic relationship creation
db.records.create_many("COMPANY", {
    "name": "Google LLC",
    "rating": 4.9,
    "DEPARTMENT": [{
        "name": "Research & Development",
        "PROJECT": [{
            "name": "Bard AI",
            "EMPLOYEE": [{
                "name": "Jeff Dean",
                "position": "Head of AI Research"
            }]
        }]
    }]
})
```

## SearchResult API

RushDB Python SDK uses a modern `SearchResult` container that follows Python SDK best practices similar to boto3, google-cloud libraries, and other popular SDKs.

### SearchResult Features

- **Generic type support**: Uses Python's typing generics (`SearchResult[T]`) with `RecordSearchResult` as a type alias for `SearchResult[Record]`
- **List-like access**: Index, slice, and iterate like a regular list
- **Search context**: Access total count, pagination info, and the original search query
- **Boolean conversion**: Use in if statements naturally (returns `True` if the result contains any items)
- **Pagination support**: Built-in pagination information and `has_more` property

### Basic Usage

```python
# Perform a search
result = db.records.find({
    "where": {"status": "active"},
    "limit": 10,
    "skip": 20
})

# Check if we have results
if result:
    print(f"Found {len(result)} records")

# Access search result information
print(f"Total matching records: {result.total}")
print(f"Current page size: {result.count}")
print(f"Records skipped: {result.skip}")
print(f"Has more results: {result.has_more}")
print(f"Search query: {result.search_query}")

# Iterate over results
for record in result:
    print(f"Record: {record.get('name')}")

# List comprehensions work
names = [r.get('name') for r in result]

# Indexing and slicing
first_record = result[0] if result else None
first_five = result[:5]

# String representation
print(repr(result))  # SearchResult(count=10, total=42)
```

### SearchResult Constructor

```python
def __init__(
    self,
    data: List[T],
    total: Optional[int] = None,
    search_query: Optional[SearchQuery] = None,
):
    """
    Initialize search result.

    Args:
        data: List of result items
        total: Total number of matching records (defaults to len(data) if not provided)
        search_query: The search query used to generate this result (defaults to {})
    """
```

### SearchResult Properties

| Property       | Type            | Description                              |
| -------------- | --------------- | ---------------------------------------- |
| `data`         | `List[T]`       | The list of result items (generic type)  |
| `total`        | `int`           | Total number of matching records         |
| `count`        | `int`           | Number of records in current result set  |
| `limit`        | `Optional[int]` | Limit that was applied to the search     |
| `skip`         | `int`           | Number of records that were skipped      |
| `has_more`     | `bool`          | Whether there are more records available |
| `search_query` | `SearchQuery`   | The search query used to generate result |

> **Implementation Notes:**
>
> - If `search_query` is not provided during initialization, it defaults to an empty dictionary `{}`
> - The `skip` property checks if `search_query` is a dictionary and returns the "skip" value or 0
> - The `has_more` property is calculated as `total > (skip + len(data))`, allowing for efficient pagination
> - The `__bool__` method returns `True` if the result contains any items (`len(data) > 0`)

### Pagination Example

```python
# Paginated search
page_size = 10
current_page = 0

while True:
    result = db.records.find({
        "where": {"category": "electronics"},
        "limit": page_size,
        "skip": current_page * page_size,
        "orderBy": {"created_at": "desc"}
    })

    if not result:
        break

    print(f"Page {current_page + 1}: {len(result)} records")

    for record in result:
        process_record(record)

    if not result.has_more:
        break

    current_page += 1
```

### RecordSearchResult Type

The SDK provides a specialized type alias for search results containing Record objects:

```python
# Type alias for record search results
RecordSearchResult = SearchResult[Record]
```

This type is what's returned by methods like `db.records.find()`, providing type safety and specialized handling for Record objects while leveraging all the functionality of the generic SearchResult class.

## Improved Record API

The Record class has been enhanced with better data access patterns and utility methods.

### Enhanced Data Access

```python
# Create a record
user = db.records.create("User", {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30,
    "department": "Engineering"
})

# Safe field access with defaults
name = user.get("name")                    # "John Doe"
phone = user.get("phone", "Not provided") # "Not provided"

# Get clean user data (excludes internal fields like __id, __label)
user_data = user.get_data()
# Returns: {"name": "John Doe", "email": "john@example.com", "age": 30, "department": "Engineering"}

# Get all data including internal fields
full_data = user.get_data(exclude_internal=False)
# Includes: __id, __label, __proptypes, etc.

# Convenient fields property
fields = user.fields  # Same as user.get_data()

# Dictionary conversion
user_dict = user.to_dict()  # Clean user data
full_dict = user.to_dict(exclude_internal=False)  # All data

# Direct field access
user_name = user["name"]        # Direct access
user_id = user["__id"]          # Internal field access
```

### Record Existence Checking

```python
# Safe existence checking (no exceptions)
if user.exists():
    print("Record is valid and accessible")
    user.update({"status": "active"})
else:
    print("Record doesn't exist or is not accessible")

# Perfect for validation workflows
def process_record_safely(record):
    if not record.exists():
        return None
    return record.get_data()

# Conditional operations
records = db.records.find({"where": {"status": "pending"}})
for record in records:
    if record.exists():
        record.update({"processed_at": datetime.now()})
```

### String Representations

```python
user = db.records.create("User", {"name": "Alice Johnson"})

print(repr(user))  # Record(id='abc-123', label='User')
print(str(user))   # User: Alice Johnson

# For records without names
product = db.records.create("Product", {"sku": "ABC123"})
print(str(product))  # Product (product-id-here)
```

## Complete Documentation

For comprehensive documentation, tutorials, and examples, please visit:

**[docs.rushdb.com/python-sdk](https://docs.rushdb.com/python-sdk/introduction)**

Documentation includes:

- Complete Records API reference
- Relationship management
- Complex query examples
- Transaction usage
- Vector search capabilities
- Data import tools

## Support

- [GitHub Issues](https://github.com/rush-db/rushdb-python/issues) - Bug reports and feature requests
- [Discord Community](https://discord.gg/rushdb) - Get help from the community
- [Email Support](mailto:support@rushdb.com) - Direct support from the RushDB team

---

<div align="center">
  <p>
    <a href="https://docs.rushdb.com/python-sdk/introduction">
      <img src="https://img.shields.io/badge/Full_Documentation-docs.rushdb.com-6D28D9?style=for-the-badge" alt="View Documentation" />
    </a>
  </p>
</div>

### set()

Updates a record by ID, replacing all data.

**Signature:**

```python
def set(
    self,
    record_id: str,
    data: Dict[str, Any],
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `record_id` (str): ID of the record to update
- `data` (Dict[str, Any]): New record data
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Update entire record data
new_data = {
    "name": "Updated Company Name",
    "rating": 5.0
}

response = db.records.set(
    record_id="record-123",
    data=new_data
)
```

### update()

Updates specific fields of a record by ID.

**Signature:**

```python
def update(
    self,
    record_id: str,
    data: Dict[str, Any],
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `record_id` (str): ID of the record to update
- `data` (Dict[str, Any]): Partial record data to update
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Update specific fields
updates = {
    "rating": 4.8,
    "status": "active"
}

response = db.records.update(
    record_id="record-123",
    data=updates
)
```

### find()

Searches for records matching specified criteria.

**Signature:**

```python
def find(
    self,
    search_query: Optional[SearchQuery] = None,
    record_id: Optional[str] = None,
    transaction: Optional[Transaction] = None
) -> RecordSearchResult
```

**Arguments:**

- `search_query` (Optional[SearchQuery]): Search query parameters
- `record_id` (Optional[str]): Optional record ID to search from
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `RecordSearchResult`: SearchResult container with matching records and metadata

**Example:**

```python
# Search for records with complex criteria
query = {
    "where": {
        "$and": [
            {"age": {"$gte": 18}},
            {"status": "active"},
            {"department": "Engineering"}
        ]
    },
    "orderBy": {"created_at": "desc"},
    "limit": 10
}

result = db.records.find(query=query)

# Work with SearchResult
print(f"Found {len(result)} out of {result.total} total records")

# Iterate over results
for record in result:
    print(f"Employee: {record.get('name')} - {record.get('department')}")

# Check pagination
if result.has_more:
    print("More results available")

# Access specific records
first_employee = result[0] if result else None

# List operations
senior_employees = [r for r in result if r.get('age', 0) > 30]
```

### delete()

Deletes records matching a query.

**Signature:**

```python
def delete(
    self,
    query: SearchQuery,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `query` (SearchQuery): Query to match records for deletion
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Delete records matching criteria
query = {
    "where": {
        "status": "inactive",
        "lastActive": {"$lt": "2023-01-01"}
    }
}

response = db.records.delete(query)
```

### delete_by_id()

Deletes one or more records by ID.

**Signature:**

```python
def delete_by_id(
    self,
    id_or_ids: Union[str, List[str]],
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `id_or_ids` (Union[str, List[str]]): Single ID or list of IDs to delete
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Delete single record
response = db.records.delete_by_id("record-123")

# Delete multiple records
response = db.records.delete_by_id([
    "record-123",
    "record-456",
    "record-789"
])
```

### attach()

Creates relationships between records.

**Signature:**

```python
def attach(
    self,
    source: Union[str, Dict[str, Any]],
    target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]],
    options: Optional[RelationshipOptions] = None,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `source` (Union[str, Dict[str, Any]]): Source record ID or data
- `target` (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]): Target record(s)
- `options` (Optional[RelationshipOptions]): Relationship options
  - `direction` (Optional[Literal["in", "out"]]): Relationship direction
  - `type` (Optional[str]): Relationship type
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Create relationship between records
options = RelationshipOptions(
    type="HAS_EMPLOYEE",
    direction="out"
)

response = db.records.attach(
    source="company-123",
    target=["employee-456", "employee-789"],
    options=options
)
```

### detach()

Removes relationships between records.

**Signature:**

```python
def detach(
    self,
    source: Union[str, Dict[str, Any]],
    target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]],
    options: Optional[RelationshipDetachOptions] = None,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `source` (Union[str, Dict[str, Any]]): Source record ID or data
- `target` (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]): Target record(s)
- `options` (Optional[RelationshipDetachOptions]): Detach options
  - `direction` (Optional[Literal["in", "out"]]): Relationship direction
  - `typeOrTypes` (Optional[Union[str, List[str]]]): Relationship type(s)
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Remove relationships between records
options = RelationshipDetachOptions(
    typeOrTypes=["HAS_EMPLOYEE", "MANAGES"],
    direction="out"
)

response = db.records.detach(
    source="company-123",
    target="employee-456",
    options=options
)
```

### import_csv()

Imports records from CSV data.

**Signature:**

```python
def import_csv(
    self,
    label: str,
    data: str,
    options: Optional[Dict[str, bool]] = None,
    transaction: Optional[Transaction] = None
) -> List[Dict[str, Any]]
```

**Arguments:**

- `label` (str): Label for imported records
- `data` (Union[str, bytes]): CSV data to import
- `options` (Optional[Dict[str, bool]]): Import options
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `List[Dict[str, Any]]`: Imported records data

**Example:**

```python
# Import records from CSV
data = """name,age,department,role
John Doe,30,Engineering,Senior Engineer
Jane Smith,28,Product,Product Manager
Bob Wilson,35,Engineering,Tech Lead"""

records = db.records.import_csv(
    label="EMPLOYEE",
    data=data,
    options={"returnResult": True, "suggestTypes": True}
)
```

---

# Record Class Documentation

The `Record` class represents a record in RushDB and provides methods for manipulating individual records, including updates, relationships, and deletions.

## Class Definition

```python
class Record:
    def __init__(self, client: "RushDB", data: Union[Dict[str, Any], None] = None)
```

## Properties

### id

Gets the record's unique identifier.

**Type:** `str`

**Example:**

```python
record = db.records.create("USER", {"name": "John"})
print(record.id)  # e.g., "1234abcd-5678-..."
```

### proptypes

Gets the record's property types.

**Type:** `str`

**Example:**

```python
record = db.records.create("USER", {"name": "John", "age": 25})
print(record.proptypes)  # Returns property type definitions
```

### label

Gets the record's label.

**Type:** `str`

**Example:**

```python
record = db.records.create("USER", {"name": "John"})
print(record.label)  # "USER"
```

### timestamp

Gets the record's creation timestamp from its ID.

**Type:** `int`

**Example:**

```python
record = db.records.create("USER", {"name": "John"})
print(record.timestamp)  # Unix timestamp in milliseconds
```

### date

Gets the record's creation date.

**Type:** `datetime`

**Example:**

```python
record = db.records.create("USER", {"name": "John"})
print(record.date)  # datetime object
```

## Methods

### set()

Updates all data for the record.

**Signature:**

```python
def set(
    self,
    data: Dict[str, Any],
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `data` (Dict[str, Any]): New record data
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
record = db.records.create("USER", {"name": "John"})
response = record.set({
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
})
```

### update()

Updates specific fields of the record.

**Signature:**

```python
def update(
    self,
    data: Dict[str, Any],
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `data` (Dict[str, Any]): Partial record data to update
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
record = db.records.create("USER", {
    "name": "John",
    "email": "john@example.com"
})
response = record.update({
    "email": "john.doe@example.com"
})
```

### attach()

Creates relationships with other records.

**Signature:**

```python
def attach(
    self,
    target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], "Record", List["Record"]],
    options: Optional[RelationshipOptions] = None,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `target` (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]): Target record(s)
- `options` (Optional[RelationshipOptions]): Relationship options
  - `direction` (Optional[Literal["in", "out"]]): Relationship direction
  - `type` (Optional[str]): Relationship type
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Create two records
user = db.records.create("USER", {"name": "John"})
group = db.records.create("GROUP", {"name": "Admins"})

# Attach user to group
response = user.attach(
    target=group,
    options=RelationshipOptions(
        type="BELONGS_TO",
        direction="out"
    )
)
```

### detach()

Removes relationships with other records.

**Signature:**

```python
def detach(
    self,
    target: Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], "Record", List["Record"]],
    options: Optional[RelationshipDetachOptions] = None,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `target` (Union[str, List[str], Dict[str, Any], List[Dict[str, Any]], Record, List[Record]]): Target record(s)
- `options` (Optional[RelationshipDetachOptions]): Detach options
  - `direction` (Optional[Literal["in", "out"]]): Relationship direction
  - `typeOrTypes` (Optional[Union[str, List[str]]]): Relationship type(s)
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
# Detach user from group
response = user.detach(
    target=group,
    options=RelationshipDetachOptions(
        typeOrTypes="BELONGS_TO",
        direction="out"
    )
)
```

### delete()

Deletes the record.

**Signature:**

```python
def delete(
    self,
    transaction: Optional[Transaction] = None
) -> Dict[str, str]
```

**Arguments:**

- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Dict[str, str]`: Response data

**Example:**

```python
user = db.records.create("USER", {"name": "John"})
response = user.delete()
```

## Complete Usage Example

Here's a comprehensive example demonstrating various Record operations:

```python
# Create a new record
user = db.records.create("USER", {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
})

# Access properties
print(f"Record ID: {user.id}")
print(f"Label: {user.label}")
print(f"Created at: {user.date}")

# Update record data
user.update({
    "age": 31,
    "title": "Senior Developer"
})

# Create related records
department = db.records.create("DEPARTMENT", {
    "name": "Engineering"
})

project = db.records.create("PROJECT", {
    "name": "Secret Project"
})

# Create relationships
user.attach(
    target=department,
    options=RelationshipOptions(
        type="BELONGS_TO",
        direction="out"
    )
)

user.attach(
    target=project,
    options=RelationshipOptions(
        type="WORKS_ON",
        direction="out"
    )
)

# Remove relationship
user.detach(
    target=project,
    options=RelationshipDetachOptions(
        typeOrTypes="WORKS_ON",
        direction="out"
    )
)

# Delete record
user.delete()
```

## Working with Transactions

Records can be manipulated within transactions for atomic operations:

```python
# Start a transaction
with db.transactions.begin() as transaction:
    # Create user
    user = db.records.create(
        "USER",
        {"name": "John Doe"},
        transaction=transaction
    )

    # Update user
    user.update(
        {"status": "active"},
        transaction=transaction
    )

    # Create and attach department
    dept = db.records.create(
        "DEPARTMENT",
        {"name": "Engineering"},
        transaction=transaction
    )

    user.attach(
        target=dept,
        options=RelationshipOptions(type="BELONGS_TO"),
        transaction=transaction
    )

    # Transaction will automatically commit if no errors occur
    # If an error occurs, it will automatically rollback
```

---

# PropertiesAPI Documentation

The `PropertiesAPI` class provides methods for managing and querying properties in RushDB.

## Class Definition

```python
class PropertiesAPI(BaseAPI):
```

## Methods

### find()

Retrieves a list of properties based on optional search criteria.

**Signature:**

```python
def find(
    self,
    search_query: Optional[SearchQuery] = None,
    transaction: Optional[Transaction] = None
) -> List[Property]
```

**Arguments:**

- `query` (Optional[SearchQuery]): Search query parameters for filtering properties
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `List[Property]`: List of properties matching the search criteria

**Example:**

```python
# Find all properties
properties = db.properties.find()

# Find properties with specific criteria
query = {
    "where": {
        "name": {"$startsWith": "user_"},  # Properties starting with 'user_'
        "type": "string"  # Only string type properties
    },
    "limit": 10  # Limit to 10 results
}
filtered_properties = db.properties.find(query)
```

### find_by_id()

Retrieves a specific property by its ID.

**Signature:**

```python
def find_by_id(
    self,
    property_id: str,
    transaction: Optional[Transaction] = None
) -> Property
```

**Arguments:**

- `property_id` (str): Unique identifier of the property
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `Property`: Property details

**Example:**

```python
# Retrieve a specific property by ID
property_details = db.properties.find_by_id("prop_123456")
```

### delete()

Deletes a property by its ID.

**Signature:**

```python
def delete(
    self,
    property_id: str,
    transaction: Optional[Transaction] = None
) -> None
```

**Arguments:**

- `property_id` (str): Unique identifier of the property to delete
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `None`

**Example:**

```python
# Delete a property
db.properties.delete("prop_123456")
```

### values()

Retrieves values for a specific property with optional sorting and pagination.

**Signature:**

```python
def values(
    self,
    property_id: str,
    sort: Optional[Literal["asc", "desc"]] = None,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    transaction: Optional[Transaction] = None
) -> PropertyValuesData
```

**Arguments:**

- `property_id` (str): Unique identifier of the property
- `sort` (Optional[Literal["asc", "desc"]]): Sort order of values
- `skip` (Optional[int]): Number of values to skip (for pagination)
- `limit` (Optional[int]): Maximum number of values to return
- `transaction` (Optional[Transaction]): Optional transaction object

**Returns:**

- `PropertyValuesData`: Property values data, including optional min/max and list of values

**Example:**

```python
# Get property values
values_data = db.properties.values(
    property_id="prop_age",
    sort="desc",  # Sort values in descending order
    skip=0,       # Start from the first value
    limit=100     # Return up to 100 values
)

# Access values
print(values_data.get('values', []))  # List of property values
print(values_data.get('min'))         # Minimum value (for numeric properties)
print(values_data.get('max'))         # Maximum value (for numeric properties)
```

## Comprehensive Usage Example

```python
# Find all properties
all_properties = db.properties.find()
for prop in all_properties:
    print(f"Property ID: {prop['id']}")
    print(f"Name: {prop['name']}")
    print(f"Type: {prop['type']}")
    print(f"Metadata: {prop.get('metadata', 'No metadata')}")
    print("---")

# Detailed property search
query = {
    "where": {
        "type": "number",             # Only numeric properties
        "name": {"$contains": "score"}  # Properties with 'score' in name
    },
    "limit": 5  # Limit to 5 results
}
numeric_score_properties = db.properties.find(query)

# Get values for a specific property
if numeric_score_properties:
    first_prop = numeric_score_properties[0]
    prop_values = db.properties.values(
        property_id=first_prop['id'],
        sort="desc",
        limit=50
    )
    print(f"Values for {first_prop['name']}:")
    print(f"Min: {prop_values.get('min')}")
    print(f"Max: {prop_values.get('max')}")

    # Detailed property examination
    detailed_prop = db.properties.find_by_id(first_prop['id'])
    print("Detailed Property Info:", detailed_prop)
```

## Property Types and Structures

RushDB supports the following property types:

- `"boolean"`: True/False values
- `"datetime"`: Date and time values
- `"null"`: Null/empty values
- `"number"`: Numeric values
- `"string"`: Text values

### Property Structure Example

```python
property = {
    "id": "prop_unique_id",
    "name": "user_score",
    "type": "number",
    "metadata": Optional[str]  # Optional additional information
}

property_with_value = {
    "id": "prop_unique_id",
    "name": "user_score",
    "type": "number",
    "value": 95.5  # Actual property value
}
```

## Transactions

Properties API methods support optional transactions for atomic operations:

```python
# Using a transaction
with db.transactions.begin() as transaction:
    # Perform multiple property-related operations
    property_to_delete = db.properties.find(
        {"where": {"name": "temp_property"}},
        transaction=transaction
    )[0]

    db.properties.delete(
        property_id=property_to_delete['id'],
        transaction=transaction
    )
    # Transaction will automatically commit if no errors occur
```

## Error Handling

When working with the PropertiesAPI, be prepared to handle potential errors:

```python
try:
    # Attempt to find or delete a property
    property_details = db.properties.find_by_id("non_existent_prop")
except RushDBError as e:
    print(f"Error: {e}")
    print(f"Error Details: {e.details}")
```
