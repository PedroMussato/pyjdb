import json
import hashlib
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Any

# =========================================================
# CONFIGURATION
# =========================================================

# Root folder for all JSON documents
ROOT = "data"

# File containing allowed authentication tokens (SHA256 hashes)
KEYS_FILE = Path("config/keys.txt")

# FastAPI application instance
app = FastAPI()

# =========================================================
# GLOBAL STATE
# =========================================================

_lock_registry = {}   # <- HERE

# =========================================================
# AUTHENTICATION LAYER (SIMPLE FILE-BASED ALLOWLIST FOR READ WRITE AND DELETE)
# =========================================================

def _hash_token(token: str) -> str: 
    """ 
    Convert raw Bearer token (UUID) into SHA256 hash. 
    
    This is what is stored in keys.txt. 
    
    """ 
    
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    auth = request.headers.get("authorization")

    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth.split(" ", 1)[1].strip()
    path = _path("config", "auth")

    with _lock(path):
        data = _load(path)
    
    token_hashed = _hash_token(token)    
    token_data = data.get(token_hashed)

    if token_data is None:
        raise HTTPException(status_code=403, detail="Invalid token")

    method = request.method

    if method == "GET":
        required = "r"
    elif method in ("POST", "PUT", "PATCH"):
        required = "w"
    elif method == "DELETE":
        required = "d"
    else:
        raise HTTPException(status_code=405, detail="Method not allowed")

    parts = request.url.path.strip("/").split("/")

    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Missing namespace")

    namespace = parts[1]

    if required not in token_data.get("permissions", ""):
        raise HTTPException(status_code=403, detail="Insufficient permission")

    namespaces = token_data.get("namespaces", [])

    if namespace not in namespaces and "__all__" not in namespaces:
        raise HTTPException(status_code=403, detail="Namespace forbidden")

    request.state.token = token
    request.state.namespaces = namespaces

    return await call_next(request)

# =========================================================
# INTERNAL STORAGE LAYER (FILE-BASED JSON DATABASE)
# =========================================================


def _path(namespace: str, document: str) -> Path:
    """
    Build file path for a document.

    Example:
    data/users/profile.json
    """
    return Path(ROOT) / namespace / f"{document}.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def _save(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    tmp.replace(path)

def _lock(path: Path):
    key = str(path) + ".lock"

    if key not in _lock_registry:
        _lock_registry[key] = FileLock(key)

    return _lock_registry[key]

# =========================================================
# CORE DATABASE OPERATIONS
# =========================================================


def write_item(namespace: str, document: str, key: str, value):
    """
    Write a single key-value into a JSON document.

    Flow:
    1. Acquire file lock
    2. Load full JSON file
    3. Modify in memory
    4. Rewrite entire file
    """
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _load(path)
        data[key] = value
        _save(path, data)


def read_item(namespace: str, document: str, key: str):
    """
    Read a single key from a JSON document.

    Flow:
    1. Acquire file lock
    2. Load full JSON file
    3. Return key value
    """
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _load(path)
        return data.get(key)


def delete_item(namespace: str, document: str, key: str):
    """
    Delete a key from a document.

    IMPORTANT:
    - This is a full-file rewrite operation (same as write_item)
    - There is no partial delete in JSON file storage
    """
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _load(path)

        # remove key if exists
        if key in data:
            del data[key]

        _save(path, data)


# =========================================================
# API MODELS
# =========================================================


class ItemRequest(BaseModel):
    """
    Request body for writing a value.
    """

    value: object


# =========================================================
# API ENDPOINTS
# =========================================================


@app.post("/item/{namespace}/{document}/{key}")
def api_write_item(namespace: str, document: str, key: str, body: ItemRequest):
    """
    Write value to a key inside a document.
    """
    write_item(namespace, document, key, body.value)
    return {"status": "ok", "action": "write"}


@app.get("/item/{namespace}/{document}/{key}")
def api_read_item(namespace: str, document: str, key: str):
    """
    Read value from a key inside a document.
    """
    value = read_item(namespace, document, key)
    return {"key": key, "value": value}


@app.delete("/item/{namespace}/{document}/{key}")
def api_delete_item(namespace: str, document: str, key: str):
    """
    Delete value from a key inside a document.
    """
    delete_item(namespace, document, key)
    return {"status": "ok", "action": "delete"}
