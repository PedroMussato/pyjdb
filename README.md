# PyJDB

A lightweight file-based key-value database built with FastAPI.

PyJDB stores data as JSON files on disk, provides REST endpoints for CRUD operations, supports token-based authentication, document caching, and safe concurrent access through file locking.

## Features

* File-based storage
* REST API
* Token authentication
* Namespace-level authorization
* Document-level LRU cache
* Authentication cache
* Atomic file writes
* Cross-process file locking
* No external database required
* Human-readable JSON persistence

---

## Performance (local test on baseline Macbook Air M3)

```text
============================================================
LOAD TEST RESULTS
============================================================
Duration:              62.44s
Concurrent Workers:    150
Namespaces:            10
Documents/Namespace:   10
Total Documents:       100
Total Requests:        170400
Requests/sec:          2729.14
Error Rate:            0.00%

Operations:
  POST       56800
  GET        56800
  DELETE     56800

Latency (ms)
  Min:      1.02
  Avg:      54.60
  Median:   59.73
  P90:      71.37
  P95:      74.05
  P99:      126.76
  Max:      314.50

Status Codes:
  200: 170400
============================================================
```

---
## Architecture

```text
HTTP Request
     ↓
Authentication Middleware
     ↓
API Endpoint
     ↓
Storage Layer
     ↓
JSON Document
```

Storage layout:

```text
data/
├── config/
│   ├── settings.json
│   └── auth.json
├── users/
│   └── profile.json
└── inventory/
    └── products.json
```

Each document is a JSON file.

Example:

```json
{
  "name": "Pedro",
  "email": "pedro@example.com"
}
```

---

## Installation

### Requirements

* Python 3.10+
* FastAPI
* Uvicorn
* FileLock

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start server

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Docker alternative
This will build and run the server
```bash
docker compose up -d
```

---

## Configuration

### settings.json

```json
{
    "auth":{
        "cache":true,
        "cache_token_ttl":60
    },
    "data":{
        "cache":true,
        "cache_max_size":10000
    }
}
```

Options:

| Setting              | Description                                |
| -------------------- | ------------------------------------------ |
| auth.cache           | Enables authentication cache               |
| data.cache           | Enables document cache                     |
| auth.cache_token_ttl | how long will live the auth token in cache |
| data.cache_max_size  | maximum size of the LRU cache              |

---

## Authentication

Authentication uses SHA-256 hashed tokens.

Clients send:

```http
Authorization: Bearer YOUR_TOKEN
```

The server hashes the token and compares it against entries stored in:

```text
data/config/auth.json
```

Example:

```json
{
  "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918": {
    "permissions": "rwd",
    "namespaces": ["users"]
  }
}
```

### Permissions

| Permission | Description |
| ---------- | ----------- |
| r          | Read        |
| w          | Write       |
| d          | Delete      |

### Namespace Restrictions

Example:

```json
{
  "permissions": "rw",
  "namespaces": ["users"]
}
```

Allows access only to:

```text
/item/users/*
```

Global access:

```json
{
  "permissions": "rwd",
  "namespaces": ["__all__"]
}
```

---

## API

### Write Value

```http
POST /item/{namespace}/{document}/{key}
```

Request:

```json
{
  "value": "Pedro"
}
```

Example:

```bash
curl -X POST \
  http://localhost:8000/item/users/profile/name \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"Pedro"}'
```

Response:

```json
{
  "status": "ok",
  "action": "write"
}
```

---

### Read Value

```http
GET /item/{namespace}/{document}/{key}
```

Example:

```bash
curl \
  http://localhost:8000/item/users/profile/name \
  -H "Authorization: Bearer TOKEN"
```

Response:

```json
{
  "key": "name",
  "value": "Pedro"
}
```

---

### Delete Value

```http
DELETE /item/{namespace}/{document}/{key}
```

Example:

```bash
curl -X DELETE \
  http://localhost:8000/item/users/profile/name \
  -H "Authorization: Bearer TOKEN"
```

Response:

```json
{
  "status": "ok",
  "action": "delete"
}
```

---

## Caching

### Authentication Cache

Authentication data is cached in memory to reduce disk reads.

Default TTL:

```python
TOKEN_TTL = 60
```

Behavior:

```text
Request
  ↓
Valid cache?
 ├─ Yes → Use memory
 └─ No  → Reload auth.json
```

---

### Document Cache

Documents are cached using an LRU (Least Recently Used) policy.

Default size:

```python
CACHE_MAX_SIZE = 10000
```

Cache key:

```python
(namespace, document)
```

When the cache reaches its limit, the least recently used document is evicted.

---

## Concurrency

### File Locking

Every document uses a dedicated lock file.

Example:

```text
data/users/profile.json.lock
```

This prevents:

* Concurrent writes
* Partial updates
* Data corruption

The implementation uses FileLock, allowing synchronization across multiple processes.

---

## Atomic Writes

Writes are performed atomically.

Instead of overwriting directly:

```text
profile.json
```

The system writes:

```text
profile.tmp
```

Then atomically replaces:

```text
profile.json
```

This reduces corruption risks during crashes or unexpected shutdowns.

---

## Data Model

The database follows a simple hierarchy:

```text
namespace
    ↓
document
    ↓
key
    ↓
value
```

Example:

```text
users
 └── profile
      └── name = Pedro
```

Stored as:

```json
{
  "name": "Pedro"
}
```

---

## Performance Characteristics

### Read

Cache hit:

```text
O(1)
```

Cache miss:

```text
O(document_size)
```

### Write

```text
O(document_size)
```

Entire documents are loaded and rewritten on each modification.

This design works well for:

* Multiple namespaces
* Multiple documents
* Each document having up to 5 MB < 5 million characters

It is not intended:

* large-scale datasets
* high-write workloads
