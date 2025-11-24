# main.py
"""
FastAPI app: /health, /pubsub
Optional pull-subscriber worker (pull mode) which is safe for container startup:
 - PROJECT_ID
 - SUBSCRIPTION_ID  (just the name)
 - SUBSCRIPTION_PATH (optional full "projects/<proj>/subscriptions/<sub>")
 - RUN_PULL_SUBSCRIBER (set "true" to start the pull worker inside the container)

Behaviors:
 - Google auth initialized lazily at startup (service account file or ADC)
 - Pub/Sub Subscriber client is created only when starting the pull subscriber
 - Proper startup/shutdown hooks (no clients created at import time)
"""

import os
import json
import time
import base64
import logging
import threading
import signal
import uuid
from functools import wraps
from typing import Optional, List, Any

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google.cloud import storage, pubsub_v1
import google.auth
from google.auth.transport.requests import AuthorizedSession

# ----- logging -----
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

# Subscriber config (pull mode)
SUBSCRIPTION_ID = os.environ.get("SUBSCRIPTION_ID")          # short name (e.g. "event-subscription")
SUBSCRIPTION_PATH = os.environ.get("SUBSCRIPTION_PATH")      # full path (projects/<proj>/subscriptions/<sub>)
RUN_PULL_SUBSCRIBER = os.environ.get("RUN_PULL_SUBSCRIBER", "false").lower() in ("1", "true", "yes")

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
                                   attempt, max_retries, getattr(fn, "__name__", str(fn)), e, wait)
                    time.sleep(wait)
            logger.exception("Function %s failed after %s attempts", getattr(fn, "__name__", str(fn)), max_retries)
            raise last_exc
        return wrapper
    return decorator

# ---------- Google Authorized session ----------
authed_session: Optional[AuthorizedSession] = None

def init_google_auth():
    """
    Initialize AuthorizedSession with priority:
      1) GOOGLE_APPLICATION_CREDENTIALS service account JSON
      2) Application Default Credentials (ADC)
    """
    global authed_session
    try:
        sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]

        if sa_path and os.path.exists(sa_path):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
            authed_session = AuthorizedSession(creds)
            logger.info("Google auth initialized from service account file.")
            return

        creds, _ = google.auth.default(scopes=scopes)
        authed_session = AuthorizedSession(creds)
        logger.info("Google auth initialized via ADC.")
    except Exception as e:
        authed_session = None
        logger.warning("Google auth init failed: %s", e)

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

# In-memory job store (simple)
job_store = {}  # job_id -> {"status":..., "details":...}

def job_update(job_id: str, status: str, details: dict | None = None):
    job_store[job_id] = {"status": status, "details": details or {}}

# background processing function (same as you had)
def process_file_job(job_id: str, local_path: str):
    job_update(job_id, "running")
    errors = []
    try:
        chunks = call_chunk_service(local_path)
        if not chunks:
            raise RuntimeError("Chunk service returned empty")
        embeddings = get_embeddings(chunks)
        if not embeddings:
            raise RuntimeError("No embeddings returned")
        store_resp = store_embeddings(embeddings)
        job_update(job_id, "done", {"acknowledged": True, "errors": errors, "stored": len(embeddings), "store_resp": store_resp})
    except Exception as exc:
        errors.append({"stage": "process", "error": str(exc)})
        job_update(job_id, "failed", {"errors": errors, "exception": str(exc)})

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

    # process synchronously for push (but you can switch to background)
    try:
        chunks = call_chunk_service(local_file)
        if not chunks:
            raise RuntimeError("Chunk service returned empty")
        embeddings = get_embeddings(chunks)
        if not embeddings:
            raise RuntimeError("No embeddings returned")
        store_resp = store_embeddings(embeddings)
    except Exception as e:
        errors.append({"stage": "pipeline", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"Pipeline error: {str(e)}")

    ack = True
    return {"acknowledged": ack, "errors": errors, "stored": len(embeddings)}

# Submit text endpoint and status (kept from your original code)
@app.post("/submit_text")
async def submit_text(payload: dict, background_tasks: BackgroundTasks):
    text = payload.get("text", "")
    filename = payload.get("filename", f"doc_{str(uuid.uuid4())[:8]}.txt")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")

    job_id = str(uuid.uuid4())
    local_path = f"/tmp/{job_id}_{filename.replace('/', '_')}"
    try:
        with open(local_path, "wb") as f:
            f.write(text.encode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save text: {e}")

    job_update(job_id, "accepted", {"local_path": local_path})
    background_tasks.add_task(process_file_job, job_id, local_path)
    return {"job_id": job_id, "status": "accepted"}

@app.get("/status/{job_id}")
async def job_status(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job["status"], "details": job["details"]}

# ---------- Optional pull-subscriber worker (lazy client creation) ----------
subscriber_client: Optional[pubsub_v1.SubscriberClient] = None
streaming_future = None
subscriber_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

def build_subscription_name(client: Optional[pubsub_v1.SubscriberClient] = None) -> str:
    """
    Build a fully-qualified subscription name WITHOUT creating a client unless caller passed one.
    This prevents early client creation at module import time which can fail when credentials aren't ready.
    """
    if SUBSCRIPTION_PATH:
        logger.info("Using SUBSCRIPTION_PATH from env: %s", SUBSCRIPTION_PATH)
        return SUBSCRIPTION_PATH
    if SUBSCRIPTION_ID and SUBSCRIPTION_ID.startswith("projects/"):
        logger.info("SUBSCRIPTION_ID contains full path, using as-is.")
        return SUBSCRIPTION_ID
    if not PROJECT_ID or not SUBSCRIPTION_ID:
        raise RuntimeError("PROJECT_ID and SUBSCRIPTION_ID must be set if SUBSCRIPTION_PATH not provided")
    if client:
        return client.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)
    # fallback to manual path build (safe string, avoids client creation)
    return f"projects/{PROJECT_ID}/subscriptions/{SUBSCRIPTION_ID}"

def pull_callback(message: pubsub_v1.subscriber.message.Message):
    try:
        logger.info("Pull received message: %s", message.data)
        # decode payload
        try:
            payload = json.loads(base64.b64decode(message.data).decode("utf-8"))
        except Exception as e:
            logger.exception("Decode error: %s", e)
            message.nack()
            return

        bucket = payload.get("bucket")
        name = payload.get("name")

        if not bucket or not name:
            logger.error("Invalid message: missing bucket or name")
            message.nack()
            return

        # download file
        try:
            local_file = f"/tmp/{name.replace('/', '_')}"
            download_from_gcs(bucket, name, local_file)
        except Exception as e:
            logger.exception("Download error: %s", e)
            message.nack()
            return

        # chunk
        try:
            chunks = call_chunk_service(local_file)
            if not chunks:
                raise RuntimeError("Chunk service returned empty")
        except Exception as e:
            logger.exception("Chunking error: %s", e)
            message.nack()
            return

        # embeddings
        try:
            embeddings = get_embeddings(chunks)
            if not embeddings:
                raise RuntimeError("No embeddings returned")
        except Exception as e:
            logger.exception("Embedding error: %s", e)
            message.nack()
            return

        # store
        try:
            store_embeddings(embeddings)
        except Exception as e:
            logger.exception("Store embeddings error: %s", e)
            message.nack()
            return

        # success → ACK
        message.ack()
        logger.info("Message processed successfully: %s", name)

    except Exception as e:
        logger.exception("Unexpected error in pull_callback: %s", e)
        try:
            message.nack()
        except Exception:
            pass

def _subscriber_runner(client: pubsub_v1.SubscriberClient, sub_name: str):
    """
    Runs the streaming future in the thread to keep it alive.
    """
    global streaming_future
    try:
        streaming_future = client.subscribe(sub_name, callback=pull_callback)
        logger.info("Streaming future started for %s", sub_name)
        # block until cancelled or exception
        streaming_future.result()
    except Exception as exc:
        logger.exception("Subscriber terminated with exception: %s", exc)
    finally:
        logger.info("Subscriber runner exiting")

def start_pull_subscriber():
    """
    Create client lazily and start subscriber in a daemon thread.
    """
    global subscriber_client, subscriber_thread, streaming_future

    if subscriber_thread and subscriber_thread.is_alive():
        logger.info("Subscriber already running")
        return

    try:
        # initialize google auth if needed (best-effort)
        if not authed_session:
            init_google_auth()

        subscriber_client = pubsub_v1.SubscriberClient()
        sub_name = build_subscription_name(subscriber_client)
        logger.info("Starting pull subscriber for: %s", sub_name)

        subscriber_thread = threading.Thread(target=_subscriber_runner, args=(subscriber_client, sub_name), name="pubsub-subscriber", daemon=True)
        subscriber_thread.start()
    except Exception:
        logger.exception("Failed to start pull subscriber")
        # cleanup on failure
        try:
            if streaming_future:
                streaming_future.cancel()
        except Exception:
            pass

def stop_pull_subscriber():
    """
    Cancel streaming future and close client. Called on shutdown.
    """
    global streaming_future, subscriber_client, subscriber_thread
    logger.info("Stopping pull subscriber...")
    try:
        if streaming_future:
            try:
                streaming_future.cancel()
            except Exception:
                logger.exception("Error cancelling streaming_future")
            streaming_future = None
        if subscriber_client:
            try:
                subscriber_client.close()
            except Exception:
                logger.exception("Error closing subscriber_client")
            subscriber_client = None
        if subscriber_thread and subscriber_thread.is_alive():
            # give it a moment to exit
            subscriber_thread.join(timeout=5.0)
    except Exception:
        logger.exception("Error while stopping subscriber")
    _stop_event.set()
    logger.info("Pull subscriber stopped")

# Hook into FastAPI lifecycle
@app.on_event("startup")
def on_startup():
    logger.info("App startup: initializing google auth and optionally starting pull subscriber")
    # initialize auth (best-effort)
    init_google_auth()

    if RUN_PULL_SUBSCRIBER:
        logger.info("RUN_PULL_SUBSCRIBER enabled, launching pull subscriber")
        start_pull_subscriber()
    else:
        logger.info("RUN_PULL_SUBSCRIBER not enabled; pull subscriber will not be started")

@app.on_event("shutdown")
def on_shutdown():
    logger.info("App shutdown: stopping pull subscriber if running")
    stop_pull_subscriber()

# Support sigterm/interrupt when run directly (uvicorn may handle signals itself)
def _signal_handler(sig, frame):
    logger.info("Signal received: %s, stopping subscriber...", sig)
    stop_pull_subscriber()

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

# local debug entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
