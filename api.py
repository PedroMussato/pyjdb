from fastapi import FastAPI
from pydantic import BaseModel
from pyjdb import (
    create_namespace,
    delete_namespace,
    create_document,
    delete_document,
    read_document,
    write_document,
)

app = FastAPI()


# -------------------------
# Request models
# -------------------------

class DocumentPayload(BaseModel):
    content: str


# -------------------------
# Namespace endpoints
# -------------------------

@app.post("/namespace/{root_dir}/{namespace}")
def api_create_namespace(root_dir: str, namespace: str):
    create_namespace(root_dir, namespace)
    return {"status": "created"}


@app.delete("/namespace/{root_dir}/{namespace}")
def api_delete_namespace(root_dir: str, namespace: str):
    delete_namespace(root_dir, namespace)
    return {"status": "deleted"}


# -------------------------
# Document endpoints
# -------------------------

@app.post("/document/{root_dir}/{namespace}/{document}")
def api_create_document(root_dir: str, namespace: str, document: str):
    create_document(root_dir, namespace, document)
    return {"status": "created"}


@app.delete("/document/{root_dir}/{namespace}/{document}")
def api_delete_document(root_dir: str, namespace: str, document: str):
    delete_document(root_dir, namespace, document)
    return {"status": "deleted"}


@app.get("/document/{root_dir}/{namespace}/{document}")
def api_read_document(root_dir: str, namespace: str, document: str):
    content = read_document(root_dir, namespace, document)
    return {"content": content}


@app.put("/document/{root_dir}/{namespace}/{document}")
def api_write_document(
    root_dir: str,
    namespace: str,
    document: str,
    payload: DocumentPayload,
):
    write_document(root_dir, namespace, document, payload.content)
    return {"status": "written"}