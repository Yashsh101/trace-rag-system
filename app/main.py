from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import time
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None

try:
    from PyPDF2 import PdfReader
except Exception:  # pragma: no cover
    from pypdf import PdfReader

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None

APP_NAME = "DocuMind AI Copilot"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("DOCUMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_PAGES = 100
CHUNK_SIZE = int(os.getenv("DOCUMIND_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("DOCUMIND_CHUNK_OVERLAP", "180"))
TOP_K = int(os.getenv("DOCUMIND_TOP_K", "5"))
REQUEST_TIMEOUT = float(os.getenv("DOCUMIND_REQUEST_TIMEOUT", "60"))
STORAGE_DIR = Path(os.getenv("DOCUMIND_STORAGE_DIR", "/tmp/documind-ai-copilot"))
RATE_LIMIT = os.getenv("DOCUMIND_RATE_LIMIT", "60/minute")
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "index.html"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for key in ("event", "path", "method", "status_code", "latency_ms", "document_id", "filename"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[handler], force=True)


configure_logging()
logger = logging.getLogger("documind")


@dataclass
class Chunk:
    id: str
    document_id: str
    filename: str
    page: int
    text: str
    embedding: list[float]


@dataclass
class Document:
    id: str
    filename: str
    sha256: str
    page_count: int
    chunk_count: int
    stored_path: str
    uploaded_at: float = field(default_factory=time.time)


class Metrics:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.requests_total = 0
        self.uploads_total = 0
        self.chat_total = 0
        self.errors_total = 0
        self.tokens_streamed_total = 0
        self.documents_total = 0
        self.chunks_total = 0
        self.last_latency_ms = 0

    def prometheus(self) -> str:
        values = {
            "documind_requests_total": self.requests_total,
            "documind_uploads_total": self.uploads_total,
            "documind_chat_total": self.chat_total,
            "documind_errors_total": self.errors_total,
            "documind_tokens_streamed_total": self.tokens_streamed_total,
            "documind_documents_total": self.documents_total,
            "documind_chunks_total": self.chunks_total,
            "documind_last_request_latency_ms": self.last_latency_ms,
            "documind_uptime_seconds": int(time.time() - self.started_at),
        }
        return "\n".join(f"{key} {value}" for key, value in values.items()) + "\n"


metrics = Metrics()


class DocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pdf_dir = root / "pdfs"
        self.state_path = root / "state.json"
        self.documents: dict[str, Document] = {}
        self.chunks: list[Chunk] = []
        self.index: Any | None = None
        self.matrix: np.ndarray | None = None
        self.model: Any | None = None
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.documents = {item["id"]: Document(**item) for item in data.get("documents", [])}
            self.chunks = [Chunk(**item) for item in data.get("chunks", [])]
        self._rebuild_index()
        metrics.documents_total = len(self.documents)
        metrics.chunks_total = len(self.chunks)
        logger.info("store_loaded", extra={"event": "store_loaded"})

    def _save(self) -> None:
        payload = {
            "documents": [asdict(doc) for doc in self.documents.values()],
            "chunks": [asdict(chunk) for chunk in self.chunks],
        }
        tmp_path = self.state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(self.state_path)

    def _load_model(self) -> Any:
        if SentenceTransformer is None:
            return None
        if self.model is None:
            logger.info("embedding_model_loading", extra={"event": "embedding_model_loading"})
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("embedding_model_ready", extra={"event": "embedding_model_ready"})
        return self.model

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self._load_model()
        if model is None:
            vectors = np.asarray([_hash_embedding(text) for text in texts], dtype="float32")
        else:
            vectors = np.asarray(model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype="float32")
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        _normalize(vectors)
        return vectors

    def _rebuild_index(self) -> None:
        if not self.chunks:
            self.matrix = None
            self.index = None
            return
        self.matrix = np.asarray([chunk.embedding for chunk in self.chunks], dtype="float32")
        _normalize(self.matrix)
        if faiss is not None:
            self.index = faiss.IndexFlatIP(int(self.matrix.shape[1]))
            self.index.add(self.matrix)
        else:
            self.index = None

    async def add_pdf(self, filename: str, content: bytes) -> Document:
        async with self._lock:
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
            sha = hashlib.sha256(content).hexdigest()
            existing = next((doc for doc in self.documents.values() if doc.sha256 == sha), None)
            if existing:
                return existing

            document_id = uuid.uuid4().hex
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename).strip("._") or "document.pdf"
            stored_path = self.pdf_dir / f"{document_id}-{safe_name}"
            stored_path.write_bytes(content)

            pages = self._extract_pages(stored_path)
            text_chunks = self._chunk_pages(pages)
            if not text_chunks:
                stored_path.unlink(missing_ok=True)
                raise HTTPException(status_code=422, detail="No readable text found in the PDF")

            embeddings = self._embed([item["text"] for item in text_chunks])
            new_chunks = [
                Chunk(
                    id=uuid.uuid4().hex,
                    document_id=document_id,
                    filename=filename,
                    page=item["page"],
                    text=item["text"],
                    embedding=embeddings[index].astype(float).tolist(),
                )
                for index, item in enumerate(text_chunks)
            ]
            document = Document(
                id=document_id,
                filename=filename,
                sha256=sha,
                page_count=len(pages),
                chunk_count=len(new_chunks),
                stored_path=str(stored_path),
            )
            self.documents[document.id] = document
            self.chunks.extend(new_chunks)
            self._rebuild_index()
            self._save()
            metrics.documents_total = len(self.documents)
            metrics.chunks_total = len(self.chunks)
            logger.info("document_indexed", extra={"event": "document_indexed", "document_id": document.id, "filename": filename})
            return document

    def _extract_pages(self, path: Path) -> list[dict[str, Any]]:
        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid or unreadable PDF") from exc
        if len(reader.pages) > MAX_PAGES:
            raise HTTPException(status_code=413, detail=f"PDF exceeds {MAX_PAGES} page limit")
        pages = []
        for page_index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized:
                pages.append({"page": page_index, "text": normalized})
        return pages

    def _chunk_pages(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunks = []
        for page in pages:
            start = 0
            text = page["text"]
            while start < len(text):
                piece = text[start : start + CHUNK_SIZE].strip()
                if piece:
                    chunks.append({"page": page["page"], "text": piece})
                start += max(1, CHUNK_SIZE - CHUNK_OVERLAP)
        return chunks

    async def retrieve(self, query: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
        if self.matrix is None or not self.chunks:
            return []
        vector = self._embed([query])
        if self.index is not None:
            scores, indices = self.index.search(vector, min(top_k, len(self.chunks)))
        else:
            similarities = self.matrix @ vector[0]
            order = np.argsort(-similarities)[: min(top_k, len(self.chunks))]
            scores = np.asarray([similarities[order]], dtype="float32")
            indices = np.asarray([order], dtype="int64")
        results = []
        for score, index in zip(scores[0], indices[0], strict=False):
            if index >= 0:
                results.append({"chunk": self.chunks[int(index)], "score": float(max(0.0, min(1.0, score)))})
        return results

    async def delete_document(self, document_id: str) -> None:
        async with self._lock:
            document = self.documents.pop(document_id, None)
            if document is None:
                raise HTTPException(status_code=404, detail="Document not found")
            Path(document.stored_path).unlink(missing_ok=True)
            self.chunks = [chunk for chunk in self.chunks if chunk.document_id != document_id]
            self._rebuild_index()
            self._save()
            metrics.documents_total = len(self.documents)
            metrics.chunks_total = len(self.chunks)


store = DocumentStore(STORAGE_DIR)
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])
app = FastAPI(title=APP_NAME, version="1.0.0")
app.state.limiter = limiter
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    metrics.errors_total += 1
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded", "request_id": request.state.request_id})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    metrics.errors_total += 1
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "request_id": request.state.request_id})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    metrics.errors_total += 1
    logger.exception("unhandled_error", extra={"event": "unhandled_error", "path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request.state.request_id})


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    request.state.request_id = request_id
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    metrics.requests_total += 1
    try:
        response = await call_next(request)
        return response
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        metrics.last_latency_ms = latency_ms
        if "response" in locals():
            response.headers["x-request-id"] = request_id
            status_code = response.status_code
        else:
            status_code = 500
        logger.info(
            "request_completed",
            extra={"event": "request_completed", "request_id": request_id, "method": request.method, "path": request.url.path, "status_code": status_code, "latency_ms": latency_ms},
        )
        request_id_var.reset(token)


@app.on_event("startup")
async def startup() -> None:
    await store.load()


@app.get("/", response_class=HTMLResponse)
@limiter.limit(RATE_LIMIT)
async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


@app.get("/api/v1/health")
@limiter.limit(RATE_LIMIT)
async def health(request: Request) -> dict[str, Any]:
    return {
        "status": "ok",
        "app": APP_NAME,
        "model": OPENROUTER_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "documents": len(store.documents),
        "chunks": len(store.chunks),
        "storage_dir": str(STORAGE_DIR),
        "openrouter_configured": bool(OPENROUTER_API_KEY),
        "faiss_available": faiss is not None,
        "sentence_transformers_available": SentenceTransformer is not None,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/api/v1/documents")
@limiter.limit(RATE_LIMIT)
async def documents(request: Request) -> dict[str, Any]:
    ordered = sorted(store.documents.values(), key=lambda item: item.uploaded_at, reverse=True)
    return {"documents": [asdict(doc) for doc in ordered]}


@app.delete("/api/v1/documents/{document_id}")
@limiter.limit(RATE_LIMIT)
async def delete_document(request: Request, document_id: str) -> dict[str, Any]:
    await store.delete_document(document_id)
    return {"ok": True, "document_id": document_id}


@app.post("/api/v1/upload")
@limiter.limit(RATE_LIMIT)
async def upload(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/x-pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    content = await _read_upload(file)
    document = await store.add_pdf(file.filename or "uploaded.pdf", content)
    metrics.uploads_total += 1
    return {"document": asdict(document), "request_id": request.state.request_id}


@app.post("/api/v1/chat/stream")
@limiter.limit(RATE_LIMIT)
async def chat_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    question = str(payload.get("message") or payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message is required")
    metrics.chat_total += 1
    return StreamingResponse(_answer_stream(question, request.state.request_id), media_type="text/event-stream")


async def _read_upload(file: UploadFile) -> bytes:
    with tempfile.SpooledTemporaryFile(max_size=MAX_UPLOAD_BYTES) as tmp:
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
            tmp.write(chunk)
        tmp.seek(0)
        return tmp.read()


async def _answer_stream(question: str, request_id: str) -> AsyncIterator[str]:
    retrieved = await store.retrieve(question)
    citations = _citation_payload(retrieved)
    confidence = _confidence(retrieved)
    yield _sse("metadata", {"citations": citations, "confidence": confidence, "request_id": request_id})
    if not retrieved:
        answer = "I could not find this in the uploaded documents."
        yield _sse("token", {"text": answer})
        yield _sse("done", {"answer": answer, "citations": [], "confidence": 0.0, "request_id": request_id})
        return
    if not OPENROUTER_API_KEY:
        yield _sse("error", {"detail": "OPENROUTER_API_KEY is not configured", "request_id": request_id})
        return

    source_context = _source_context(retrieved)
    answer_parts: list[str] = []
    try:
        async for token in _stream_openrouter(question, source_context):
            answer_parts.append(token)
            metrics.tokens_streamed_total += 1
            yield _sse("token", {"text": token})
    except Exception as exc:
        logger.exception("openrouter_stream_failed", extra={"event": "openrouter_stream_failed"})
        yield _sse("error", {"detail": str(exc), "request_id": request_id})
        return
    answer = "".join(answer_parts).strip() or "I could not find this in the uploaded documents."
    yield _sse("done", {"answer": answer, "citations": citations, "confidence": confidence, "request_id": request_id})


async def _stream_openrouter(question: str, source_context: str) -> AsyncIterator[str]:
    system = (
        "You are DocuMind AI Copilot. Answer only from the provided PDF excerpts. "
        "Cite sources inline using chips like [p. 3]. If unsupported, say "
        "\"I could not find this in the uploaded documents.\""
    )
    payload = {
        "model": OPENROUTER_MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\n\nSources:\n{source_context}"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": APP_NAME,
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                async with client.stream("POST", f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise RuntimeError(f"OpenRouter error {response.status_code}: {body.decode(errors='ignore')[:500]}")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        token = event.get("choices", [{}])[0].get("delta", {}).get("content")
                        if token:
                            yield token
                    return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RuntimeError(str(last_error) if last_error else "OpenRouter request failed")


def _source_context(results: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[Source {index}: {item['chunk'].filename}, page {item['chunk'].page}, score {item['score']:.2f}]\n{item['chunk'].text}"
        for index, item in enumerate(results, start=1)
    )


def _citation_payload(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int]] = set()
    citations = []
    for item in results:
        chunk: Chunk = item["chunk"]
        key = (chunk.document_id, chunk.page)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"document_id": chunk.document_id, "filename": chunk.filename, "page": chunk.page, "score": round(float(item["score"]), 3), "snippet": chunk.text[:220]})
    return citations


def _confidence(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    scores = [float(item["score"]) for item in results[:3]]
    return round(max(0.0, min(1.0, sum(scores) / len(scores))), 2)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = np.zeros(dimensions, dtype="float32")
    for token in re.findall(r"[A-Za-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    if not np.any(vector):
        vector[0] = 1.0
    _normalize(vector.reshape(1, -1))
    return vector.tolist()


def _normalize(vectors: np.ndarray) -> None:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors /= norms
