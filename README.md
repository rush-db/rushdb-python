<div align="center">

![RushDB Logo](https://raw.githubusercontent.com/rush-db/rushdb/main/rushdb-logo.svg)

# RushDB Python SDK
### The Instant Database for Modern Apps and DS/ML Ops

RushDB is an open-source database built on Neo4j, designed to simplify application development.

It automates data normalization, manages relationships, and infers data types, enabling developers to focus on building features rather than wrestling with data.

[🌐 Homepage](https://rushdb.com) — [📢 Blog](https://rushdb.com/blog) — [☁️ Platform ](https://app.rushdb.com) — [📚 Docs](https://docs.rushdb.com) — [🧑‍💻 Examples](https://github.com/rush-db/rushdb/examples)
</div>

## 🚀 Feature Highlights

### 1. **Data modeling is optional**
Push data of any shape—RushDB handles relationships, data types, and more automatically.

### 2. **Automatic type inference**
Minimizes overhead while optimizing performance for high-speed searches.

### 3. **Powerful search API**
Query data with accuracy using the graph-powered search API.

### 4. **Flexible data import**
Easily import data in `JSON`, `CSV`, or `JSONB`, creating data-rich applications fast.

### 5. **Developer-Centric Design**
RushDB prioritizes DX with an intuitive and consistent API.

### 6. **REST API Readiness**
A REST API with SDK-like DX for every operation: manage relationships, create, delete, and search effortlessly. Same DTO everywhere.

---

## Installation

Install the RushDB Python SDK via pip:

```sh
pip install rushdb
```

---

## Usage

### **1. Setup SDK**

```python
from rushdb import RushDB

db = RushDB("API_TOKEN", url="https://api.rushdb.com")
```

---

### **2. Push any JSON data**

```python
company_data = {
    "label": "COMPANY",
    "payload": {
        "name": "Google LLC",
        "address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA",
        "foundedAt": "1998-09-04T00:00:00.000Z",
        "rating": 4.9,
        "DEPARTMENT": [{
            "name": "Research & Development",
            "description": "Innovating and creating advanced technologies for AI, cloud computing, and consumer devices.",
            "PROJECT": [{
                "name": "Bard AI",
                "description": "A state-of-the-art generative AI model for natural language understanding and creation.",
                "active": True,
                "budget": 1200000000,
                "EMPLOYEE": [{
                    "name": "Jeff Dean",
                    "position": "Head of AI Research",
                    "email": "jeff@google.com",
                    "dob": "1968-07-16T00:00:00.000Z",
                    "salary": 3000000
                }]
            }]
        }]
    }
}

db.records.create_many(company_data)
```

---

### **3. Find Records by specific criteria**

```python
query = {
    "labels": ["EMPLOYEE"],
    "where": {
        "position": {"$contains": "AI"},
        "PROJECT": {
            "DEPARTMENT": {
                "COMPANY": {
                    "rating": {"$gte": 4}
                }
            }
        }
    }
}

matched_employees = db.records.find(query)

company = db.records.find_uniq("COMPANY", {"where": {"name": "Google LLC"}})
```

---

### **4. Use REST API with cURL**

```sh
curl -X POST https://api.rushdb.com/api/v1/records/search \
-H "Authorization: Bearer API_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "labels": ["EMPLOYEE"],
  "where": {
    "position": { "$contains": "AI" },
    "PROJECT": {
      "DEPARTMENT": {
        "COMPANY": {
          "rating": { "$gte": 4 }
        }
      }
    }
  }
}'
```

<div align="center">
<b>You Rock</b>  🚀
</div>

---

<div align="center" style="margin-top: 20px">

> Check the [Documentation](https://docs.rushdb.com) and [Examples](https://github.com/rush-db/rushdb/examples) to learn more 🧐

</div>

