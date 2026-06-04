import pytest
from pathlib import Path
from pyjdb import (
    create_namespace,
    delete_namespace,
    create_document,
    delete_document,
    read_document,
    write_document,
)


@pytest.fixture
def tmp_root(tmp_path):
    # Temporary isolated filesystem root for each test
    return tmp_path


def test_create_namespace(tmp_root):
    create_namespace(tmp_root, "ns1")

    assert (tmp_root / "ns1").exists()
    assert (tmp_root / "ns1").is_dir()


def test_create_document(tmp_root):
    create_document(tmp_root, "ns1", "doc1.txt")

    path = tmp_root / "ns1" / "doc1.txt"
    assert path.exists()
    assert path.is_file()


def test_write_and_read_document(tmp_root):
    write_document(tmp_root, "ns1", "doc1.txt", "hello")

    content = read_document(tmp_root, "ns1", "doc1.txt")
    assert content == "hello"


def test_overwrite_document(tmp_root):
    write_document(tmp_root, "ns1", "doc1.txt", "a")
    write_document(tmp_root, "ns1", "doc1.txt", "b")

    assert read_document(tmp_root, "ns1", "doc1.txt") == "b"


def test_delete_document(tmp_root):
    write_document(tmp_root, "ns1", "doc1.txt", "data")

    delete_document(tmp_root, "ns1", "doc1.txt")

    assert not (tmp_root / "ns1" / "doc1.txt").exists()


def test_delete_namespace(tmp_root):
    write_document(tmp_root, "ns1", "doc1.txt", "data")
    write_document(tmp_root, "ns1", "doc2.txt", "data")

    delete_namespace(tmp_root, "ns1")

    assert not (tmp_root / "ns1").exists()


def test_read_missing_document(tmp_root):
    result = read_document(tmp_root, "ns1", "missing.txt")

    assert result is None