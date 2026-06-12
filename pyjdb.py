import json
import hashlib
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

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
# AUTHENTICATION LAYER (SIMPLE FILE-BASED ALLOWLIST)
# =========================================================


def _hash_token(token: str) -> str:
    """
    Convert raw Bearer token (UUID) into SHA256 hash.
    This is what is stored in keys.txt.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_valid_token(token: str) -> bool:
    """
    Validate token against allowlist stored in keys.txt.

    - Reads file on every request (no cache)
    - Compares SHA256(token) against each line in file
    """
    if not KEYS_FILE.exists():
        return False

    hashed = _hash_token(token)

    # Linear scan of file (simple, but O(n))
    with KEYS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip() == hashed:
                return True

    return False


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Global authentication middleware.

    Blocks all requests except explicitly allowed ones.
    """

    # Allow public endpoints (optional)
    if request.url.path in ["/health"]:
        return await call_next(request)

    # Extract Authorization header
    auth = request.headers.get("authorization")

    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    # Extract raw token from header
    token = auth.split(" ", 1)[1]

    # Validate token against keys file
    if not is_valid_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")

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
    """
    Load JSON file into Python dict.

    If file does not exist → return empty dict.
    If file is corrupted → return empty dict (fail-safe behavior).
    """
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(path: Path, data: dict):
    """
    Save Python dict to JSON file.

    WARNING:
    - This overwrites the entire file.
    - No partial updates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _lock(path: Path):
    """
    File lock to prevent concurrent writes corruption.

    Note:
    - Only protects write operations
    - Does NOT protect read performance
    """
    return FileLock(str(path) + ".lock")


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
