import json
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI
from pydantic import BaseModel


# -------------------------
# CONFIG
# -------------------------

ROOT = "data"

app = FastAPI()


# -------------------------
# INTERNAL STORAGE LAYER
# -------------------------

def _path(namespace: str, document: str):
    return Path(ROOT) / namespace / f"{document}.json"


def _load(path: Path):
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _lock(path: Path):
    return FileLock(str(path) + ".lock")


# -------------------------
# CORE DB FUNCTIONS
# -------------------------

def write_item(namespace: str, document: str, key: str, value):
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _load(path)
        data[key] = value
        _save(path, data)


def read_item(namespace: str, document: str, key: str):
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _load(path)
        return data.get(key)


# -------------------------
# API MODELS
# -------------------------

class ItemRequest(BaseModel):
    value: object


# -------------------------
# API ENDPOINTS
# -------------------------

@app.post("/item/{namespace}/{document}/{key}")
def api_write_item(namespace: str, document: str, key: str, body: ItemRequest):
    write_item(namespace, document, key, body.value)
    return {"status": "ok", "action": "write"}


@app.get("/item/{namespace}/{document}/{key}")
def api_read_item(namespace: str, document: str, key: str):
    value = read_item(namespace, document, key)
    return {"key": key, "value": value}


# -------------------------
# OPTIONAL: document init endpoint
# -------------------------

@app.post("/document/{namespace}/{document}")
def create_document(namespace: str, document: str):
    path = _path(namespace, document)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        _save(path, {})

    return {"status": "created"}
