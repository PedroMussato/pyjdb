import json
import hashlib
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime
from collections import OrderedDict
from threading import RLock

# =========================================================
# CONFIGURATION SECTION
# =========================================================

# Root directory where all namespaces/documents are persisted as JSON files
ROOT = "data"

# FastAPI application instance (entrypoint of HTTP API)
app = FastAPI()

# =========================================================
# GLOBAL STATE
# =========================================================

# Registry of file locks per file path to prevent concurrent writes across processes
_lock_registry = {}

# =========================================================
# AUTHENTICATION LAYER
# =========================================================


def _hash_token(token: str) -> str:
    """
    Converts a raw authentication token into an SHA-256 hash.

    This ensures that tokens stored in configuration files are not stored in plaintext.
    The resulting hash is compared against stored values in the auth configuration.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def return_token(token: str):
    """
    Retrieves authentication metadata associated with a given token.

    Flow:
    - Hashes incoming token
    - Optionally uses cached authentication map (based on settings)
    - If cache expired or disabled, reloads auth configuration from disk
    - Returns metadata entry for hashed token (permissions, namespaces, etc.)

    Expected output:
    - dict for valid token
    - None if token not found
    """

    global _TOKEN_CACHE, _TOKEN_CACHE_TS

    # Current timestamp used for TTL validation
    now = int(datetime.now().timestamp())

    # Whether authentication cache is enabled (controlled by runtime settings)
    use_cache = settings["auth"]["cache"]

    if use_cache:
        # Protect cache access under concurrency
        with _TOKEN_CACHE_LOCK:

            # Cache hit: valid and not expired
            if _TOKEN_CACHE is not None and (now - _TOKEN_CACHE_TS) < TOKEN_TTL:
                data = _TOKEN_CACHE
            else:
                # Cache miss or expired: reload authentication configuration from disk
                path = _path("config", "auth")

                # File-level lock ensures consistent read under concurrent writers
                with _lock(path):
                    data = _load(path)

                # Update in-memory cache
                _TOKEN_CACHE = data
                _TOKEN_CACHE_TS = now
    else:
        # Cache disabled: always load from disk with file lock
        path = _path("config", "auth")

        with _lock(path):
            data = _load(path)

    # Return authentication entry mapped to hashed token
    return data.get(_hash_token(token))


async def auth_middleware(request: Request, call_next):
    """
    FastAPI middleware responsible for:
    - Extracting Bearer token
    - Validating token existence
    - Determining required permission based on HTTP method
    - Validating namespace-level access control
    - Attaching auth metadata to request state
    """

    # Extract Authorization header
    auth = request.headers.get("authorization")

    # Validate presence and format of Bearer token
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    # Extract raw token string
    token = auth.split(" ", 1)[1].strip()

    # retrieve token metadata via return_token(token)
    token_data = return_token(token)

    # Reject if token not recognized
    if token_data is None:
        raise HTTPException(status_code=403, detail="Invalid token")

    # Map HTTP method to required permission level
    method = request.method

    if method == "GET":
        required = "r"  # read permission
    elif method in ("POST", "PUT", "PATCH"):
        required = "w"  # write permission
    elif method == "DELETE":
        required = "d"  # delete permission
    else:
        # Any unsupported HTTP method is rejected
        raise HTTPException(status_code=405, detail="Method not allowed")

    # Parse URL path to extract namespace segment
    parts = request.url.path.strip("/").split("/")

    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Missing namespace")

    namespace = parts[1]

    # Validate permission string against token capabilities
    if required not in token_data.get("permissions", ""):
        raise HTTPException(status_code=403, detail="Insufficient permission")

    # Validate namespace-level access restrictions
    namespaces = token_data.get("namespaces", [])

    if namespace not in namespaces and "__all__" not in namespaces:
        raise HTTPException(status_code=403, detail="Namespace forbidden")

    # Attach identity/context to request lifecycle
    request.state.token = token
    request.state.namespaces = namespaces

    # Continue request processing pipeline
    return await call_next(request)


# =========================================================
# INTERNAL STORAGE LAYER (FILE-BASED JSON DATABASE)
# =========================================================


def _cache_get(cache_key):
    """
    Retrieves a document from in-memory LRU cache if enabled.

    Returns:
    - dict if cached
    - None if not cached or caching disabled
    """

    if not settings["data"]["cache"]:
        return None

    with _CACHE_LOCK:
        if cache_key not in _CACHE:
            return None

        # Mark entry as recently used (LRU behavior)
        _CACHE.move_to_end(cache_key)

        return _CACHE[cache_key]


def _cache_set(cache_key, value):
    """
    Inserts or updates a document in LRU cache.

    Maintains maximum cache size by evicting least-recently-used entries.
    """

    if not settings["data"]["cache"]:
        return

    with _CACHE_LOCK:
        _CACHE[cache_key] = value

        # Update usage order
        _CACHE.move_to_end(cache_key)

        # Evict oldest entry if cache exceeds capacity
        if len(_CACHE) > CACHE_MAX_SIZE:
            _CACHE.popitem(last=False)


def _path(namespace: str, document: str) -> Path:
    """
    Constructs absolute filesystem path for a document.

    Example output:
    data/users/profile.json
    """

    return Path(ROOT) / namespace / f"{document}.json"


def _load(path: Path) -> dict:
    """
    Loads JSON file from disk.

    Behavior:
    - Returns empty dict if file does not exist
    - Returns empty dict if file is corrupted (invalid JSON)
    """

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def _save(path: Path, data: dict):
    """
    Persists dictionary to disk using atomic write strategy.

    Strategy:
    - Write to temporary file first
    - Replace original file atomically
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    tmp.replace(path)


def _lock(path: Path):
    """
    Returns a FileLock instance for a given file path.

    Ensures cross-process synchronization for safe concurrent access.

    Lock objects are cached to avoid repeated instantiation overhead.
    """

    key = str(path) + ".lock"

    if key not in _lock_registry:
        _lock_registry[key] = FileLock(key)

    return _lock_registry[key]


# =========================================================
# SETTINGS LOADING
# =========================================================

# Path to system configuration file
settings_path = _path("config", "settings")

# Global runtime configuration loaded at startup
settings = _load(settings_path)

# In-memory LRU cache for document-level data
# Key: (namespace, document)
# Value: dict loaded from JSON file
_CACHE = OrderedDict()

# Mutex protecting _CACHE from concurrent access across threads
_CACHE_LOCK = RLock()

# Maximum number of cached documents before eviction (LRU policy)
CACHE_MAX_SIZE = settings["data"]["cache_max_size"]

# Cached authentication data (in-memory)
# Stores loaded token authorization mapping to reduce disk reads
_TOKEN_CACHE = None

# Timestamp of last authentication cache refresh (unix epoch seconds)
_TOKEN_CACHE_TS = 0

# Lock protecting token cache updates
_TOKEN_CACHE_LOCK = RLock()

# Time-to-live for authentication cache in seconds
TOKEN_TTL = settings["auth"]["cache_token_ttl"]

# =========================================================
# CORE DATABASE OPERATIONS
# =========================================================


def write_item(namespace: str, document: str, key: str, value):
    """
    Writes a key-value pair into a JSON document.

    Flow:
    - Acquire file lock
    - Load cached or disk data
    - Modify in-memory dict
    - Persist to disk atomically
    - Update cache
    """

    cache_key = (namespace, document)
    path = _path(namespace, document)

    with _lock(path):
        data = _cache_get(cache_key)

        if data is None:
            data = _load(path)

        data[key] = value
        _save(path, data)

    _cache_set(cache_key, data)


def read_item(namespace: str, document: str, key: str):
    """
    Reads a value from a JSON document.

    Flow:
    - Check cache first
    - If missed, load from disk under lock
    - Store in cache
    - Return value for given key
    """

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
    """
    Deletes a key from a JSON document.

    Flow:
    - Acquire file lock
    - Load cached or disk data
    - Remove key if present
    - Persist changes
    - Update cache
    """

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
    Schema for write operations.

    Encapsulates a single arbitrary JSON-serializable value.
    """

    value: object


# =========================================================
# API ENDPOINTS
# =========================================================


@app.post("/item/{namespace}/{document}/{key}")
def api_write_item(namespace: str, document: str, key: str, body: ItemRequest):
    """
    API endpoint for writing a value into a document key.
    """

    write_item(namespace, document, key, body.value)

    return {"status": "ok", "action": "write"}


@app.get("/item/{namespace}/{document}/{key}")
def api_read_item(namespace: str, document: str, key: str):
    """
    API endpoint for reading a value from a document key.
    """

    return {"key": key, "value": read_item(namespace, document, key)}


@app.delete("/item/{namespace}/{document}/{key}")
def api_delete_item(namespace: str, document: str, key: str):
    """
    API endpoint for deleting a key from a document.
    """

    delete_item(namespace, document, key)

    return {"status": "ok", "action": "delete"}
