"""
Improved FastAPI RAG service (main.py)
- Sync endpoints to avoid blocking-async anti-patterns
- Redis keys hashed (SHA256)
- JSON payloads for POSTs to external services
- Optionally collect LLM streaming responses fully (LLM_STREAM=true)
- Increased LLM defaults (max tokens + topP) and logs raw responses for debugging
- Cache stored as JSON; read back as JSON
- CORS middleware applied immediately
- Startup init for Redis and Google auth (best-effort)
"""

import os
import json
import time
import logging
import unicodedata
import traceback
import hashlib
from functools import wraps
from typing import Optional, List, Any, Dict
from fastapi.middleware.cors import CORSMiddleware

import requests
import redis
import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ---------------- logging ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("user-backend")

# ---------- Config (env vars) ----------
CHUNK_ENDPOINT = os.environ.get("CHUNK_URL")
VECTOR_ENDPOINT = os.environ.get("VECTOR_DB_ENDPOINT")
DEPLOYED_INDEX_ID = os.environ.get("DEPLOYED_INDEX_ID")
REDIS_HOST = os.environ.get("MEMORY_STORE_HOST")
REDIS_PORT = int(os.environ.get("MEMORY_STORE_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("MEMORY_STORE_PASSWORD")  # optional
REDIS_CONNECT_TIMEOUT = float(os.environ.get("REDIS_CONNECT_TIMEOUT", 5.0))
REDIS_TTL = int(os.environ.get("REDIS_TTL", 3600))  # seconds to cache answers

EMBEDDING_ENDPOINT = os.environ.get("EMBEDDING_ENDPOINT")

PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("REGION")
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-2.0-flash")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT") or (
    f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/{LLM_MODEL_ID}:generateContent"
)

LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", 0.7))
LLM_MAX_OUTPUT_TOKENS = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", 2048))
LLM_TOP_P = float(os.environ.get("LLM_TOP_P", 0.9))
LLM_STREAM = os.environ.get("LLM_STREAM", "false").lower() in ("1", "true", "yes")

VECTOR_NEIGHBOR_COUNT = int(os.environ.get("VECTOR_NEIGHBOR_COUNT", 10))

MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
BACKOFF_BASE = float(os.environ.get("BACKOFF_BASE", 0.2))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 30))

# Globals set at startup
authed_session: Optional[AuthorizedSession] = None
redis_client: Optional[redis.Redis] = None

# ---------- Helpers ----------

def normalize_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return unicodedata.normalize("NFC", s).strip()


def sha256_key(q: str) -> str:
    return "q:" + hashlib.sha256(q.encode("utf-8")).hexdigest()


def safe_json_dumps(v: Any) -> str:
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


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
                    logger.warning("Retry %s/%s for %s after error: %s (sleep %.2fs)", attempt, max_retries, getattr(fn, '__name__', str(fn)), e, wait)
                    time.sleep(wait)
            logger.exception("Function %s failed after %s attempts", getattr(fn, '__name__', str(fn)), max_retries)
            raise last_exc
        return wrapper
    return decorator

# ---------- Startup / init ----------

def create_redis_client():
    if not REDIS_HOST:
        raise ValueError("Missing MEMORY_STORE_HOST")
    pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD or None,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
        decode_responses=True,
    )
    return redis.Redis(connection_pool=pool)


def init_google_auth():
    global authed_session
    SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
    SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    try:
        if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
            credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            authed_session = AuthorizedSession(credentials)
            logger.info("Authorized session initialized using service account file.")
        else:
            credentials, _ = google.auth.default(scopes=SCOPES)
            authed_session = AuthorizedSession(credentials)
            logger.info("Authorized session initialized via ADC.")
    except Exception as e:
        authed_session = None
        logger.warning("Google auth init failed: %s", e)

app = FastAPI(title="Redis+Vector+LLM RAG service (updated)")

# apply CORS immediately
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    global redis_client
    logger.info("Startup: validating configuration")
    init_google_auth()
    try:
        redis_client = create_redis_client()
        redis_client.ping()
        logger.info("Connected to Redis at %s:%s db=%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
    except Exception as e:
        redis_client = None
        logger.warning("Redis init failed at startup: %s", e)

# ---------- Redis wrappers (retry kept) ----------
@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def redis_get(key: str) -> Optional[str]:
    if not redis_client:
        raise RuntimeError("Redis client not initialized")
    return redis_client.get(key)

@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def redis_set(key: str, value: str, ttl: int = REDIS_TTL):
    if not redis_client:
        raise RuntimeError("Redis client not initialized")
    if ttl > 0:
        return redis_client.setex(key, ttl, value)
    else:
        return redis_client.set(key, value)

# ---------- Core service calls (defensive parsing) ----------
@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def call_chunk_service(text: str) -> List[str]:
    if not CHUNK_ENDPOINT:
        raise RuntimeError("CHUNK_ENDPOINT not configured")
    url = CHUNK_ENDPOINT.rstrip("/") + "/chunk"
    logger.info("Calling chunk service %s", url)
    resp = requests.post(url, json={"text": text, "chunk_size": 500}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # normalize to list[str]
    if isinstance(data, dict) and "chunks" in data and isinstance(data["chunks"], list):
        out = []
        for c in data["chunks"]:
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, dict):
                out.append(c.get("text") or c.get("content") or json.dumps(c, ensure_ascii=False))
            else:
                out.append(str(c))
        return out
    elif isinstance(data, list):
        return [c if isinstance(c, str) else (c.get("text") if isinstance(c, dict) and "text" in c else json.dumps(c, ensure_ascii=False)) for c in data]
    elif isinstance(data, dict) and "result" in data:
        return [data["result"]]
    else:
        return [json.dumps(data, ensure_ascii=False)]

@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def get_embeddings(chunks: List[str]) -> List[List[float]]:
    if not EMBEDDING_ENDPOINT:
        raise RuntimeError("EMBEDDING_ENDPOINT not configured")
    if not authed_session:
        raise RuntimeError("Google auth not available for embeddings call")
    payload = {"instances": [{"task_type": "RETRIEVAL_DOCUMENT", "title": "document title", "content": c} for c in chunks]}
    headers = {"Content-Type": "application/json"}
    logger.info("Requesting embeddings for %d chunks", len(chunks))
    resp = authed_session.post(EMBEDDING_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    try:
        preds = data.get("predictions")
        if preds and isinstance(preds, list):
            out = []
            for p in preds:
                ev = p.get("embeddings") or p.get("embedding") or p.get("vector")
                if isinstance(ev, dict) and "values" in ev:
                    out.append(ev["values"])
                elif isinstance(ev, list):
                    out.append(ev)
                else:
                    out.append([])
            return out
        if isinstance(data, list) and all(isinstance(x, list) for x in data):
            return data
    except Exception:
        logger.exception("Unexpected embedding response shape: %s", json.dumps(data, ensure_ascii=False))
        raise RuntimeError("Unexpected embedding response format")
    logger.error("Could not parse embeddings response: %s", json.dumps(data, ensure_ascii=False))
    raise RuntimeError("Unexpected embedding response format")

@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def search_vector_db(embedding: List[float]) -> Any:
    if not VECTOR_ENDPOINT:
        raise RuntimeError("VECTOR_DB_ENDPOINT not configured")
    if not authed_session:
        raise RuntimeError("Google auth not available for vector DB call")
    payload = {
        "deployedIndexId": DEPLOYED_INDEX_ID,
        "queries": [{"datapoint": {"featureVector": embedding}, "neighborCount": VECTOR_NEIGHBOR_COUNT}]
    }
    logger.info("Calling vector DB endpoint")
    resp = authed_session.post(VECTOR_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()

# LLM: supports both non-stream and stream collection
@retry_on_exception(MAX_RETRIES, BACKOFF_BASE)
def call_llm(prompt: str, contexts: Optional[List[str]] = None) -> Any:
    if not LLM_ENDPOINT:
        raise RuntimeError("LLM_ENDPOINT not configured")
    if not authed_session:
        raise RuntimeError("Google auth not available for LLM call")

    text_input = prompt
    if contexts:
        context_str = "\n\n".join(contexts)
        text_input = f"Context:\n{context_str}\n\nQuestion:\n{prompt}"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": text_input}]}
        ],
        "generationConfig": {"temperature": LLM_TEMPERATURE, "maxOutputTokens": LLM_MAX_OUTPUT_TOKENS, "topP": LLM_TOP_P}
    }
    headers = {"Content-Type": "application/json"}

    logger.info("Calling LLM endpoint (stream=%s)", LLM_STREAM)
    if LLM_STREAM:
        # collect the streamed chunks fully then return the assembled text
        resp = authed_session.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        full_text = ""
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            logger.debug("LLM stream chunk: %s", line[:1000])
            try:
                obj = json.loads(line)
                # try to extract text from common shapes
                cand = obj.get("candidates") or obj.get("predictions") or obj.get("responses")
                if isinstance(cand, list) and len(cand) > 0:
                    c0 = cand[0]
                    content = c0.get("content") if isinstance(c0, dict) else None
                    if isinstance(content, dict):
                        parts = content.get("parts") or []
                        for p in parts:
                            if isinstance(p, str):
                                full_text += p
                            elif isinstance(p, dict) and "text" in p:
                                full_text += p["text"]
                            else:
                                full_text += safe_json_dumps(p)
                    else:
                        for k in ("text", "output", "message"):
                            if k in c0:
                                full_text += c0[k] if isinstance(c0[k], str) else safe_json_dumps(c0[k])
                else:
                    # fallback: try top-level text fields
                    for k in ("text", "output", "message"):
                        if k in obj:
                            full_text += obj[k] if isinstance(obj[k], str) else safe_json_dumps(obj[k])
            except json.JSONDecodeError:
                # not JSON: append raw
                full_text += line
        logger.info("LLM stream completed; length=%d", len(full_text))
        logger.debug("LLM full_text (preview): %s", full_text[:2000])
        return full_text
    else:
        resp = authed_session.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("LLM raw response (preview): %s", safe_json_dumps(data)[:2000])
        return data


def parse_llm_response(resp: Any) -> str:
    try:
        # if already a plain string (e.g., collected stream) — return it
        if isinstance(resp, str):
            return resp
        if isinstance(resp, dict):
            candidates = resp.get("candidates") or resp.get("predictions") or resp.get("responses")
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                c0 = candidates[0]
                content = c0.get("content") if isinstance(c0, dict) else None
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if parts and isinstance(parts, list):
                        texts = []
                        for p in parts:
                            if isinstance(p, str):
                                texts.append(p)
                            elif isinstance(p, dict) and "text" in p:
                                texts.append(p["text"])
                            else:
                                texts.append(safe_json_dumps(p))
                        return "\n".join(texts)
                if isinstance(c0, dict):
                    for key in ("output", "message", "text"):
                        if key in c0:
                            val = c0[key]
                            return val if isinstance(val, str) else safe_json_dumps(val)
                return safe_json_dumps(c0)
        return str(resp)
    except Exception as e:
        logger.exception("Failed to parse LLM response: %s", e)
        return safe_json_dumps(resp)

# ---------- FastAPI app & models ----------
class QuestionRequest(BaseModel):
    question: str

@app.get("/health")
def health():
    problems = []
    try:
        if redis_client:
            redis_client.ping()
        else:
            problems.append("redis_client_not_initialized")
    except Exception as e:
        problems.append(f"redis_error: {str(e)}")
    if not authed_session:
        problems.append("google_auth_not_initialized")
    status = "ok" if not problems else "degraded"
    return {"status": status, "problems": problems}

# Use sync handler to avoid blocking-async anti-pattern
@app.post("/ask")
def ask(req: QuestionRequest):
    q_raw = req.question
    q = normalize_text(q_raw)
    if not q:
        raise HTTPException(status_code=400, detail="Empty question")

    errors: List[Dict[str, Any]] = []

    cache_key = sha256_key(q)
    try:
        cached = redis_get(cache_key) if redis_client else None
    except Exception as e:
        tb = traceback.format_exc()
        logger.warning("Redis GET error for key=%s: %s\n%s", cache_key, e, tb)
        errors.append({"stage": "redis_get", "error": str(e), "trace": tb})
        cached = None

    if cached:
        try:
            parsed = json.loads(cached)
            return {"found": True, "question": q, "answer": parsed, "errors": errors}
        except Exception:
            return {"found": True, "question": q, "answer": cached, "errors": errors}

    # 2) Chunk service
    try:
        chunk_texts = call_chunk_service(q)
        if not chunk_texts:
            raise RuntimeError("Chunk service returned empty")
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Chunking failed: %s", e)
        errors.append({"stage": "chunk", "error": str(e), "trace": tb})
        raise HTTPException(status_code=503, detail=f"Chunk stage failed: {str(e)}")

    # 3) Embeddings
    try:
        embeddings = get_embeddings(chunk_texts)
        if not embeddings or len(embeddings) == 0:
            raise RuntimeError("No embeddings returned")
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Embeddings failed: %s", e)
        errors.append({"stage": "embeddings", "error": str(e), "trace": tb})
        raise HTTPException(status_code=503, detail=f"Embeddings stage failed: {str(e)}")

    # 4) Vector search (use first embedding)
    search_resp = None
    try:
        search_resp = search_vector_db(embeddings[0])
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Vector search failed: %s", e)
        errors.append({"stage": "vector_search", "error": str(e), "trace": tb})

    # 5) build contexts list (best-effort)
    contexts: List[str] = []
    try:
        if search_resp:
            neighbors = []
            if isinstance(search_resp, dict):
                for k in ("nearestNeighbors", "nearest_neighbors", "results", "matches", "neighbors"):
                    v = search_resp.get(k)
                    if v:
                        neighbors = v if isinstance(v, list) else [v]
                        break
            elif isinstance(search_resp, list):
                neighbors = search_resp

            for n in neighbors:
                if isinstance(n, dict):
                    dp = n.get("datapoint") or n.get("payload") or n.get("data") or n.get("match")
                    if isinstance(dp, dict):
                        text = dp.get("text") or dp.get("content") or dp.get("data") or dp.get("displayName") or safe_json_dumps(dp)
                        contexts.append(text)
                    elif isinstance(dp, str):
                        contexts.append(dp)
                    else:
                        contexts.append(safe_json_dumps(n))
                else:
                    contexts.append(str(n))
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Parsing vector search response failed: %s", e)
        errors.append({"stage": "parse_vector", "error": str(e), "trace": tb})

    # 6) Call LLM
    try:
        llm_resp = call_llm(q, contexts if contexts else None)
        answer = parse_llm_response(llm_resp)
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("LLM call failed: %s", e)
        errors.append({"stage": "llm", "error": str(e), "trace": tb})
        raise HTTPException(status_code=503, detail=f"LLM call failed: {str(e)}")

    # 7) Cache the Q/A (best-effort)
    try:
        to_store = json.dumps(answer, ensure_ascii=False)
        redis_set(cache_key, to_store)
    except Exception as e:
        tb = traceback.format_exc()
        logger.warning("Redis SET failed for key=%s: %s\n%s", cache_key, e, tb)
        errors.append({"stage": "redis_set", "error": str(e), "trace": tb})

    return {"found": False, "question": q, "answer": answer, "contexts_count": len(contexts), "errors": errors}

# for local debugging
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
