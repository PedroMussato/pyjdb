# PyJDB

A lightweight file-based NoSQL database exposed via HTTP API.

It implements a minimal document store where each document is a JSON file and each document contains key-value pairs (items). Access is protected by a simple SHA256-based allowlist authentication mechanism.

---

## Core Concept

The system follows a simple hierarchy:

```
namespace → document → JSON key-value store
```

### Mapping

* Namespace → directory
* Document → JSON file
* Item → key inside JSON object

---

## Features

* File-based document storage (JSON per document)
* Write key-value pairs into documents (upsert behavior)
* Read individual keys from documents
* Delete keys from documents
* Automatic document creation on first write (lazy creation)
* File-level locking per document for write safety
* Simple Bearer token authentication via SHA256 allowlist
* Minimal FastAPI HTTP interface
* No external database dependencies

---

## Tech Stack

* Python 3.10+
* FastAPI
* Uvicorn
* Filelock
* Pydantic

---

## Installation

```bash
pip3 install -r requirements.txt
```

---

## Running the API

```bash
uvicorn pyjdb:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

---

## Authentication Model

All requests (except optional health endpoints) require authentication.

### Flow

* Client sends a Bearer token (UUID)
* Server computes SHA256(token)
* Server checks if hash exists in `config/keys.txt`
* If found → request allowed
* If not found → request rejected

### Example header

```http
Authorization: Bearer <uuid-token>
```

### keys.txt format

Each line contains one SHA256 hash:

```
9b74c9897bac770ffc029102a200c5de...
2c26b46b68ffc68ff99b453c1d304134...
```

---

## Data Model

Each document is stored as a JSON file:

```json
{
  "key1": "value1",
  "key2": "value2"
}
```

---

## API Endpoints

---

### Write Item (Upsert)

Creates or updates a key inside a document.

```
POST /item/{namespace}/{document}/{key}
```

Request body:

```json
{
  "value": "any JSON serializable value"
}
```

Behavior:

* If key exists → overwrite value
* If key does not exist → create key
* If document does not exist → created implicitly

---

### Read Item

Reads a key from a document.

```
GET /item/{namespace}/{document}/{key}
```

Response:

```json
{
  "key": "key1",
  "value": "value1"
}
```

If key does not exist:

```json
{
  "key": "missing",
  "value": null
}
```

---

### Delete Item

Removes a key from a document.

```
DELETE /item/{namespace}/{document}/{key}
```

Behavior:

* If key exists → removed
* If key does not exist → no-op

---

## Example Usage

---

### Write item

```bash
curl -X POST http://127.0.0.1:8000/item/ns1/doc1/user \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"value": {"name": "Pedro"}}'
```

---

### Read item

```bash
curl http://127.0.0.1:8000/item/ns1/doc1/user \
  -H "Authorization: Bearer <token>"
```

---

### Delete item

```bash
curl -X DELETE http://127.0.0.1:8000/item/ns1/doc1/user \
  -H "Authorization: Bearer <token>"
```

---

## Concurrency Model

* File-level locking per document
* Prevents concurrent write corruption
* Reads are also locked to avoid reading inconsistent write states
* Lock granularity: per document file

---

## Security Model

* Stateless authentication
* SHA256-based token validation
* Allowlist stored in `keys.txt`
* No token generation endpoint exposed
* No dynamic key issuance via API
