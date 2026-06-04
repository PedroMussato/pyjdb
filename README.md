# PyJDB

Lightweight file-based document storage with a minimal HTTP API.

The system exposes a simple namespace/document abstraction over the local filesystem with concurrency protection via file locks.

---

## Architecture

- Namespace = directory
- Document = file
- Content = raw text
- Concurrency control = file-level lock (`filelock`)

---

## Features

- Create / delete namespaces
- Create / delete documents
- Read / write document content
- File locking to prevent concurrent write corruption
- Minimal FastAPI HTTP layer
- Local filesystem persistence

---

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- Filelock
- Pytest

---

## Installation

```bash
pip3 install -r requirements.txt
```

---

## Run API Server

```bash
uvicorn api:app --reload
```

Server runs on:

```
http://127.0.0.1:8000
```

---

## API Endpoints

### Namespace

Create namespace:

```
POST /namespace/{root_dir}/{namespace}
```

Delete namespace:

```
DELETE /namespace/{root_dir}/{namespace}
```

---

### Document

Create document:

```
POST /document/{root_dir}/{namespace}/{document}
```

Read document:

```
GET /document/{root_dir}/{namespace}/{document}
```

Write document:

```
PUT /document/{root_dir}/{namespace}/{document}
Body:
{
  "content": "string"
}
```

Delete document:

```
DELETE /document/{root_dir}/{namespace}/{document}
```

---

## Example Usage (curl)

### Create namespace

```bash
curl -X POST http://127.0.0.1:8000/namespace/data/ns1
```

### Write document

```bash
curl -X PUT http://127.0.0.1:8000/document/data/ns1/file.txt \
  -H "Content-Type: application/json" \
  -d '{"content":"hello world"}'
```

### Read document

```bash
curl http://127.0.0.1:8000/document/data/ns1/file.txt
```

### Delete document

```bash
curl -X DELETE http://127.0.0.1:8000/document/data/ns1/file.txt
```

---

## Running Tests

### API + storage tests

```bash
pytest -vv
```
