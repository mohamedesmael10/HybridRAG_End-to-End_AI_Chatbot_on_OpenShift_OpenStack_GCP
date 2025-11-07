# main.py
"""
FastAPI app: /health, /pubsub
Flow:
 - /pubsub receives Pub/Sub message (base64 encoded)
 - decode, download file from GCS
 - call chunk service (CHUNK_URL)
 - get embeddings (EMBEDDING_ENDPOINT)
 - store embeddings in VECTOR_DB_ENDPOINT
 - acknowledge Pub/Sub message
Error handling: collects/errors per stage and returns full details.
Designed to run inside Cloud Run.
"""

import os
import json
import time
import base64
import logging
from functools import wraps
from typing import Optional, List, Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import storage
import google.auth
from google.auth.transport.requests import AuthorizedSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pubsub-backend")

# ---------- Config ----------
CHUNK_ENDPOINT = os.environ.get("CHUNK_URL")
if CHUNK_ENDPOINT and not CHUNK_ENDPOINT.endswith("/chunk"):
    CHUNK_ENDPOINT = CHUNK_ENDPOINT.rstrip("/") + "/chunk"

VECTOR_ENDPOINT = os.environ.get("VECTOR_DB_ENDPOINT")
DEPLOYED_INDEX_ID = os.environ.get("DEPLOYED_INDEX_ID")
EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT")
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
BACKOFF_BASE = float(os.environ.get("BACKOFF_BASE", 0.2))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 30))

# ---------- Helpers ----------
def retry_on_exception(max_retries=3, backoff_base=0.2):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    wait = backoff_base * (2 ** (attempt - 1))
                    logger.warning("Retry %s/%s for %s after error: %s (sleep %.2fs)",
                                   attempt, max_retries, fn.__name__, e, wait)
                    time.sleep(wait)
            logger.exception("Function %s failed after %s attempts", fn.__name__, max_retries)
            raise last_exc
        return wrapper
    return decorator

# ---------- Google Authorized session ----------
authed_session = None
try:
    credentials, _ = google.auth.default()
    authed_session = AuthorizedSession(credentials)
    logger.info("Authorized session initialized.")
except Exception as e:
    logger.warning("Google auth init failed: %s", e)
    authed_session = None

# ---------- Core functions ----------
@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def call_chunk_service(file_path: str) -> List[str]:
    if not CHUNK_ENDPOINT:
        raise RuntimeError("CHUNK_ENDPOINT not configured")
    logger.info("Calling chunk service for file: %s", file_path)
    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"chunk_size": 500}
        resp = requests.post(CHUNK_ENDPOINT, files=files, data=data, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    chunks = data.get("chunks") or [json.dumps(data)]
    return [str(c.get("text") or c) if isinstance(c, dict) else str(c) for c in chunks]

@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def get_embeddings(chunks: List[str]) -> List[List[float]]:
    if not EMBEDDING_ENDPOINT:
        raise RuntimeError("EMBEDDING_ENDPOINT not configured")
    if not authed_session:
        raise RuntimeError("Google auth not available for embeddings call")
    payload = {"instances": [{"task_type": "RETRIEVAL_DOCUMENT", "title": "doc", "content": c} for c in chunks]}
    headers = {"Content-Type": "application/json"}
    resp = authed_session.post(EMBEDDING_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    try:
        return [pred["embeddings"]["values"] for pred in data["predictions"]]
    except Exception:
        logger.error("Unexpected embedding response: %s", json.dumps(data, indent=2))
        raise RuntimeError("Unexpected embedding response format")

@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def store_embeddings(embedding_list: List[List[float]]) -> Any:
    if not VECTOR_ENDPOINT:
        raise RuntimeError("VECTOR_DB_ENDPOINT not configured")
    if not authed_session:
        raise RuntimeError("Google auth not available for vector DB call")
    payload = {"deployedIndexId": DEPLOYED_INDEX_ID,
               "datapoints": [{"featureVector": emb} for emb in embedding_list]}
    resp = authed_session.post(VECTOR_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

def download_from_gcs(bucket_name: str, object_name: str, dest_path: str):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.download_to_filename(dest_path)
    logger.info("Downloaded gs://%s/%s -> %s", bucket_name, object_name, dest_path)

# ---------- FastAPI ----------
app = FastAPI(title="Pub/Sub RAG Backend")

class PubSubMessage(BaseModel):
    message: dict
    subscription: Optional[str] = None

@app.get("/health")
async def health():
    problems = []
    if not authed_session:
        problems.append("google_auth_not_initialized")
    status = "ok" if not problems else "degraded"
    return {"status": status, "problems": problems}

@app.post("/")
async def pubsub_endpoint(req: PubSubMessage):
    errors = []
    ack = False
    try:
        msg_data = req.message.get("data")
        if not msg_data:
            raise ValueError("No data in Pub/Sub message")
        decoded = base64.b64decode(msg_data).decode("utf-8")
        payload = json.loads(decoded)
        bucket_name = payload["bucket"]
        object_name = payload["name"]
    except Exception as e:
        errors.append({"stage": "decode", "error": str(e)})
        raise HTTPException(status_code=400, detail=f"Decode error: {str(e)}")

    local_file = f"/tmp/{object_name.replace('/', '_')}"
    try:
        download_from_gcs(bucket_name, object_name, local_file)
    except Exception as e:
        errors.append({"stage": "download", "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

    # Chunk
    try:
        chunks = call_chunk_service(local_file)
        if not chunks:
            raise RuntimeError("Chunk service returned empty")
    except Exception as e:
        errors.append({"stage": "chunk", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"Chunk error: {str(e)}")

    # Embeddings
    try:
        embeddings = get_embeddings(chunks)
        if not embeddings:
            raise RuntimeError("No embeddings returned")
    except Exception as e:
        errors.append({"stage": "embedding", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"Embedding error: {str(e)}")

    # Store embeddings
    try:
        store_resp = store_embeddings(embeddings)
    except Exception as e:
        errors.append({"stage": "store_embeddings", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"Store embeddings error: {str(e)}")

    ack = True
    return {"acknowledged": ack, "errors": errors, "stored": len(embeddings)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# add these imports at top of main.py
import uuid
from fastapi import BackgroundTasks

# add near top-level after app = FastAPI(...)
job_store = {}  # simple in-memory job store: job_id -> {"status": "pending|running|done|failed", "details": {...}}

# Helper to update job status
def job_update(job_id: str, status: str, details: dict | None = None):
    job_store[job_id] = {"status": status, "details": details or {}}

# Background worker that processes a local file path
def process_file_job(job_id: str, local_path: str):
    """Runs the pipeline for a file already saved on disk and updates job_store."""
    job_update(job_id, "running")
    errors = []
    try:
        # 1) Chunk
        try:
            chunks = call_chunk_service(local_path)
            if not chunks:
                raise RuntimeError("Chunk service returned empty")
        except Exception as e:
            errors.append({"stage": "chunk", "error": str(e)})
            raise

        # 2) Embeddings
        try:
            embeddings = get_embeddings(chunks)
            if not embeddings:
                raise RuntimeError("No embeddings returned")
        except Exception as e:
            errors.append({"stage": "embedding", "error": str(e)})
            raise

        # 3) Store embeddings
        try:
            store_resp = store_embeddings(embeddings)
        except Exception as e:
            errors.append({"stage": "store_embeddings", "error": str(e)})
            raise

        # success
        job_update(job_id, "done", {"acknowledged": True, "errors": errors, "stored": len(embeddings), "store_resp": store_resp})
    except Exception as exc:
        # record failure
        job_update(job_id, "failed", {"errors": errors, "exception": str(exc)})

# New endpoint: accept plain text, create temp file and start background job
@app.post("/submit_text")
async def submit_text(payload: dict, background_tasks: BackgroundTasks):
    """
    Accepts JSON: { "text": "...", "filename": "optional_name.txt" }
    Returns: { "job_id": "<uuid>", "status": "accepted" }
    """
    text = payload.get("text", "")
    filename = payload.get("filename", f"doc_{str(uuid.uuid4())[:8]}.txt")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    job_id = str(uuid.uuid4())
    local_path = f"/tmp/{job_id}_{filename.replace('/', '_')}"
    try:
        with open(local_path, "wb") as f:
            # write bytes so pipeline can open as file
            f.write(text.encode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save text: {e}")

    # initialize job store and start background task
    job_update(job_id, "accepted", {"local_path": local_path})
    background_tasks.add_task(process_file_job, job_id, local_path)

    return {"job_id": job_id, "status": "accepted"}

# New endpoint: check job status
@app.get("/status/{job_id}")
async def job_status(job_id: str):
    """
    Returns job state and any details.
    Example: { "job_id": "...", "status": "done", "details": {...} }
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job["status"], "details": job["details"]}
