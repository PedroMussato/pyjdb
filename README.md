
# PyJDB

A lightweight file-based NoSQL database exposed via HTTP API.

It implements a minimal document store where each document is a JSON file and each document contains key-value pairs (items).

---

## Core Concept

The system follows a simple hierarchy:

namespace → document → JSON key-value store

### Mapping

- Namespace → directory
- Document → JSON file
- Item → key inside JSON

---

## Features

- Create document automatically via API
- Write key-value pairs into JSON documents
- Read individual keys from documents
- Automatic file creation if missing
- File-level locking for safe concurrent access
- Minimal FastAPI HTTP interface

---

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- Filelock
- Pytest (testing)

---

## Installation

```bash
pip install fastapi uvicorn filelock pytest
````

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

### Create Document

Creates an empty JSON document if it does not exist.

```
POST /document/{namespace}/{document}
```

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

* If key exists → overwrite
* If key does not exist → create

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

## Example Usage

### Create document

```bash
curl -X POST http://127.0.0.1:8000/document/ns1/doc1
```

---

### Write item

```bash
curl -X POST http://127.0.0.1:8000/item/ns1/doc1/user \
  -H "Content-Type: application/json" \
  -d '{"value": {"name": "Pedro"}}'
```

---

### Read item

```bash
curl http://127.0.0.1:8000/item/ns1/doc1/user
```

---

## Concurrency Model

* Uses file-level locking (`filelock`)
* Prevents simultaneous read/write corruption
* Lock granularity: per document file

Isso muda completamente performance e confiabilidade.
```
