# Mini RAG System

Production-grade MVP for a FastAPI + Postgres/pgvector RAG backend.

## 1. Final Production Architecture

```text
Client
  -> FastAPI API layer
      -> Ingestion service
          -> PDF parser
          -> Chunker
          -> Embedding service
          -> Postgres metadata + pgvector chunk storage
      -> Query service
          -> Embedding service
          -> Retrieval service
          -> LLM gateway
          -> Citation formatter
          -> Query logs + citations
      -> Evaluation module
      -> Logging/monitoring layer
```

Core components:

- `app/api`: HTTP endpoints.
- `app/services/ingestion_service.py`: PDF -> parse -> chunk -> embed -> store.
- `app/services/retrieval_service.py`: pgvector cosine similarity search.
- `app/services/llm_service.py`: OpenAI answer generation.
- `app/services/citation_formatter.py`: source context and citation payloads.
- `app/models`: metadata, chunks, query logs, citations.
- `evals`: simple offline evaluation harness and dataset format.

Included hardening: API-key auth, ACL-aware retrieval, durable DB-polled ingestion jobs, hybrid search, local reranking, local/S3 storage adapters, readiness checks, structured logs, and eval gates.

## 2. Exact MVP Scope

Implemented v0 vertical slice:

```text
PDF upload -> pypdf parse -> page-aware chunking -> OpenAI embeddings
-> Postgres/pgvector storage -> similarity search -> GPT answer
-> citations -> query logging
```

Explicitly not included:

- Kubernetes
- multi-tenancy
- OCR for scanned PDFs
- managed auth provider integration
- fully managed queue service
- hosted tracing dashboard

These are extension points, not required for the local setup.

## 3. Repository Structure

```text
app/
  api/routes.py
  core/config.py
  core/errors.py
  core/logging.py
  db/base.py
  db/session.py
  models/
  schemas/
  services/
  utils/
alembic/
  versions/
evals/
tests/
docker-compose.yml
requirements.txt
requirements-dev.txt
.env.example
```

## 4. Database Schema

The schema is implemented in SQLAlchemy models and Alembic migration:

- `documents`: uploaded document identity and content hash.
- `document_versions`: immutable processing version metadata.
- `chunks`: chunk text, page provenance, metadata, and pgvector embedding.
- `query_logs`: traceable question, answer, latency, token usage, retrieved chunks.
- `citations`: answer citation records linked to query logs and chunks.

Migration file: `alembic/versions/0001_initial_schema.py`

## 5. Environment Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`.

Start Postgres + pgvector when Docker is available:

```powershell
docker compose up -d
```

Run migrations:

```powershell
alembic upgrade head
```

Docker-free local fallback:

```powershell
# In .env:
# DATABASE_URL=sqlite:///./storage/local-rag.db
# OPENAI_API_KEY=replace-me
python -m scripts.init_local_db
```

In `APP_ENV=local`, `OPENAI_API_KEY=replace-me` enables deterministic local embeddings and extractive answers for offline smoke tests. Set a real OpenAI key and Postgres/pgvector for production-quality retrieval and generation.

For container startup, run migrations before serving traffic:

```powershell
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

Local storage is the default and writes artifacts under `LOCAL_STORAGE_PATH`. For production, set `APP_ENV=production` and configure `STORAGE_BACKEND=s3` with the S3-compatible bucket settings.

Start API:

```powershell
uvicorn app.main:app --reload
```

Start ingestion worker in a second terminal:

```powershell
python -m app.workers.ingestion_worker
```

Open:

```text
http://localhost:8000/docs
```

Readiness:

```powershell
curl http://localhost:8000/api/v1/health/ready
```

## 6. Core API

Ingest a PDF:

```bash
curl -X POST "http://localhost:8000/api/v1/documents/ingest" \
  -H "X-API-Key: dev-user-key" \
  -F "file=@sample.pdf"
```

Ask a question:

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "X-API-Key: dev-user-key" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What does the document say about revenue?\"}"
```

## 7. Implementation Steps

1. `UploadFile` accepts PDFs with size validation.
2. `PDFParser` extracts page-level text using `pypdf`.
3. `Chunker` creates overlapping page-aware chunks.
4. `EmbeddingService` batches embeddings using OpenAI.
5. `IngestionService` stores document metadata, active version, chunks, and vectors.
6. `RetrievalService` embeds the query and runs pgvector cosine search.
7. `citation_formatter` builds `[S1]` source context and citation metadata.
8. `LLMService` calls the chat model with source-grounded instructions.
9. `/query` writes query logs and citation rows.
10. FastAPI middleware emits request logs and trace IDs.

## 8. Testing Plan

Test coverage targets:

- document ingestion with fake parser/embedder
- chunk creation boundaries and page metadata
- embedding storage shape
- retrieval ordering with mocked embeddings or integration DB
- answer generation with citations
- no-answer behavior when retrieval returns nothing

Run:

```powershell
pytest
```

## 9. Evaluation Plan

Use `evals/golden_qa.example.jsonl` as the 50-question dataset template.

Metrics for v0:

- retrieval precision@k: expected source appears in retrieved chunks
- faithfulness: answer claims are supported by retrieved context, initially human/LLM judged
- citation correctness: cited chunk contains the answer evidence
- no-answer correctness: unsupported questions return the no-answer response

Run the scaffold:

```powershell
python evals/run_eval.py --dataset evals/golden_qa.example.jsonl
```

Live evals against a running API:

```powershell
python evals/run_eval.py --dataset evals/golden_qa.example.jsonl --api-url http://localhost:8000 --api-key dev-user-key
```

## 10. Production Hardening Checklist

- Add request rate limits per API key/IP.
- Add upload MIME sniffing, not only extension checks.
- Add OCR path for scanned PDFs.
- Add background ingestion queue for large files.
- Add OpenAI request budgets and per-request token caps.
- Add structured JSON logging.
- Add Langfuse/Phoenix traces.
- Add retry/dead-letter handling for ingestion failures.
- Add API authentication.
- Add secrets manager instead of local `.env`.
- Add full-text/hybrid search and reranking after baseline evals.
- Add backup/restore verification for Postgres.
- Add CI eval gates for retrieval and answer regressions.

## 11. Upgrade Roadmap

Phase 1:

- Hybrid search using Postgres full-text search + pgvector fusion.
- Reranking with Cohere/BGE/Jina.
- Langfuse traces for retrieval, prompts, tokens, and costs.

Phase 2:

- Queue-based ingestion with Celery/RQ/Temporal.
- S3-compatible raw document storage.
- OCR via Azure Document Intelligence, Textract, or Docling.
- Better table extraction and table-aware retrieval.

Phase 3:

- ACL-aware retrieval.
- Multi-tenancy.
- Per-tenant cost controls.
- Admin UI for failed ingestions and eval review.

Phase 4:

- Kubernetes deployment.
- Autoscaling ingestion workers.
- Blue/green index rollouts.
- Enterprise audit logs and compliance reporting.

## 12. Metadata Export

Export metadata tables to JSONL:

```powershell
python -m app.scripts.export_metadata --out-dir exports
```

This writes documents, chunk metadata, ingestion jobs, and query logs. Raw PDF bytes and embeddings are not exported.
