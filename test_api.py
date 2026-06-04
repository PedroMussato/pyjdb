import pytest
from fastapi.testclient import TestClient
from api import app
from pathlib import Path


client = TestClient(app)


# -------------------------
# Helpers
# -------------------------

ROOT = "test_data"


def cleanup():
    # Remove test directory after tests
    path = Path(ROOT)
    if path.exists():
        for item in path.rglob("*"):
            if item.is_file():
                item.unlink()
        for item in sorted(path.rglob("*"), reverse=True):
            if item.is_dir():
                item.rmdir()
        path.rmdir()


@pytest.fixture(autouse=True)
def run_around_tests():
    cleanup()
    yield
    cleanup()


# -------------------------
# Namespace tests
# -------------------------

def test_create_namespace():
    res = client.post(f"/namespace/{ROOT}/ns1")
    assert res.status_code == 200

    assert Path(ROOT, "ns1").exists()


def test_delete_namespace():
    client.post(f"/namespace/{ROOT}/ns1")
    res = client.delete(f"/namespace/{ROOT}/ns1")

    assert res.status_code == 200
    assert not Path(ROOT, "ns1").exists()


# -------------------------
# Document tests
# -------------------------

def test_create_document():
    client.post(f"/namespace/{ROOT}/ns1")

    res = client.post(f"/document/{ROOT}/ns1/file.txt")
    assert res.status_code == 200

    assert Path(ROOT, "ns1", "file.txt").exists()


def test_write_and_read_document():
    client.post(f"/namespace/{ROOT}/ns1")

    res = client.put(
        f"/document/{ROOT}/ns1/file.txt",
        json={"content": "hello"},
    )
    assert res.status_code == 200

    res = client.get(f"/document/{ROOT}/ns1/file.txt")
    assert res.status_code == 200
    assert res.json()["content"] == "hello"


def test_overwrite_document():
    client.post(f"/namespace/{ROOT}/ns1")

    client.put(f"/document/{ROOT}/ns1/file.txt", json={"content": "a"})
    client.put(f"/document/{ROOT}/ns1/file.txt", json={"content": "b"})

    res = client.get(f"/document/{ROOT}/ns1/file.txt")
    assert res.json()["content"] == "b"


def test_delete_document():
    client.post(f"/namespace/{ROOT}/ns1")

    client.put(f"/document/{ROOT}/ns1/file.txt", json={"content": "x"})
    res = client.delete(f"/document/{ROOT}/ns1/file.txt")

    assert res.status_code == 200
    assert not Path(ROOT, "ns1", "file.txt").exists()


def test_read_missing_document():
    client.post(f"/namespace/{ROOT}/ns1")

    res = client.get(f"/document/{ROOT}/ns1/missing.txt")
    assert res.status_code == 200
    assert res.json()["content"] is None