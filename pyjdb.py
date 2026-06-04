from pathlib import Path
from filelock import FileLock


def create_namespace(root_dir, namespace):
    # Ensure the namespace directory exists
    path = Path(root_dir) / namespace
    path.mkdir(parents=True, exist_ok=True)


def delete_namespace(root_dir, namespace):
    # Remove a namespace directory and its files (non-recursive safety)
    path = Path(root_dir) / namespace

    if path.exists() and path.is_dir():
        # Delete all files inside the directory first
        for file in path.iterdir():
            if file.is_file():
                file.unlink()

        # Remove the empty directory
        path.rmdir()


def create_document(root_dir, namespace, document):
    # Ensure namespace exists before creating document
    dir_path = Path(root_dir) / namespace
    dir_path.mkdir(parents=True, exist_ok=True)

    # Create an empty file if it does not exist
    file_path = dir_path / document
    file_path.touch(exist_ok=True)


def delete_document(root_dir, namespace, document):
    file_path = Path(root_dir) / namespace / document

    # File-level lock to avoid race conditions during deletion
    lock = FileLock(str(file_path) + ".lock")
    with lock:
        if file_path.exists():
            file_path.unlink()


def read_document(root_dir, namespace, document):
    file_path = Path(root_dir) / namespace / document

    # Lock ensures no concurrent write during read
    lock = FileLock(str(file_path) + ".lock")
    with lock:
        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")


def write_document(root_dir, namespace, document, content):
    file_path = Path(root_dir) / namespace / document

    # Ensure directory exists before writing file
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Lock prevents concurrent read/write corruption
    lock = FileLock(str(file_path) + ".lock")
    with lock:
        # Atomic overwrite of file content
        file_path.write_text(content, encoding="utf-8")