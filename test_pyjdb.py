from fastapi.testclient import TestClient
from pyjdb import app
from pathlib import Path
import pytest


client = TestClient(app)

ROOT = "data"


@pytest.fixture(autouse=True)
def cleanup():
    path = Path(ROOT)

    if path.exists():
        for p in sorted(path.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        path.rmdir()

    yield

    if path.exists():
        for p in sorted(path.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        path.rmdir()


def test_create_document_and_write_read():
    client.post("/document/ns1/doc1")

    r = client.post("/item/ns1/doc1/key1", json={"value": "hello"})
    assert r.status_code == 200

    r = client.get("/item/ns1/doc1/key1")
    assert r.json()["value"] == "hello"


def test_overwrite_item():
    client.post("/document/ns1/doc1")

    client.post("/item/ns1/doc1/key1", json={"value": "a"})
    client.post("/item/ns1/doc1/key1", json={"value": "b"})

    assert client.get("/item/ns1/doc1/key1").json()["value"] == "b"


def test_missing_key():
    client.post("/document/ns1/doc1")

    r = client.get("/item/ns1/doc1/does_not_exist")
    assert r.json()["value"] is None
