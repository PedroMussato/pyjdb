import json
import hashlib
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Any
from datetime import datetime
from collections import OrderedDict
from threading import RLock

# =========================================================
# CONFIGURATION
# =========================================================

# Root folder for all JSON documents
ROOT = "data"

# File containing allowed authentication tokens (SHA256 hashes)
KEYS_FILE = Path("config/keys.txt")

# FastAPI application instance
app = FastAPI()

_CACHE = OrderedDict()
_CACHE_LOCK = RLock()
CACHE_MAX_SIZE = 10_000


# =========================================================
# GLOBAL STATE
# =========================================================

_lock_registry = {}  
_token_registry = {}  

# =========================================================
# AUTHENTICATION LAYER (SIMPLE FILE-BASED ALLOWLIST FOR READ WRITE AND DELETE)
# =========================================================


def _hash_token(token: str) -> str:
    """
    Convert raw Bearer token (UUID) into SHA256 hash.

    This is what is stored in keys.txt.

    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()

_TOKEN_CACHE = None
_TOKEN_CACHE_TS = 0
_TOKEN_CACHE_LOCK = RLock()
TOKEN_TTL = 60


def return_token(token: str):
    global _TOKEN_CACHE, _TOKEN_CACHE_TS

    now = int(datetime.now().timestamp())
    token_hashed = _hash_token(token)

    use_cache = settings["auth"]["cache"]

    if use_cache:
        with _TOKEN_CACHE_LOCK:
            if (
                _TOKEN_CACHE is not None
                and (now - _TOKEN_CACHE_TS) < TOKEN_TTL
            ):
                data = _TOKEN_CACHE
            else:
                path = _path("config", "auth")

                with _lock(path):
                    data = _load(path)

                _TOKEN_CACHE = data
                _TOKEN_CACHE_TS = now
    else:
        path = _path("config", "auth")

        with _lock(path):
            data = _load(path)

    return data.get(token_hashed)

async def auth_middleware(request: Request, call_next):
    auth = request.headers.get("authorization")

    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth.split(" ", 1)[1].strip()
    token_data = data.get(token)

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


def _cache_get(cache_key):
    if not settings["data"]["cache"]:
        return None

    with _CACHE_LOCK:
        if cache_key not in _CACHE:
            return None
        _CACHE.move_to_end(cache_key)
        return _CACHE[cache_key]


def _cache_set(cache_key, value):
    if not settings["data"]["cache"]:
        return

    with _CACHE_LOCK:
        _CACHE[cache_key] = value
        _CACHE.move_to_end(cache_key)

        if len(_CACHE) > CACHE_MAX_SIZE:
            _CACHE.popitem(last=False)

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
# LOADING SETTINGS
# =========================================================

settings_path = _path("config", "settings")
settings = _load(settings_path)

# =========================================================
# CORE DATABASE OPERATIONS
# =========================================================


def write_item(namespace: str, document: str, key: str, value):
    cache_key = (namespace, document)
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _cache_get(cache_key)

        if data is None:
            data = _load(path)

        data[key] = value
        _save(path, data)

    # atualiza cache sem invalidar
    _cache_set(cache_key, data)

def read_item(namespace: str, document: str, key: str):
    cache_key = (namespace, document)

    data = _cache_get(cache_key)

    if data is None:
        path = _path(namespace, document)
        lock = _lock(path)

        with lock:
            data = _load(path)

        _cache_set(cache_key, data)

    return data.get(key)

def delete_item(namespace: str, document: str, key: str):
    cache_key = (namespace, document)
    path = _path(namespace, document)
    lock = _lock(path)

    with lock:
        data = _cache_get(cache_key)

        if data is None:
            data = _load(path)

        data.pop(key, None)
        _save(path, data)

    _cache_set(cache_key, data)

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
