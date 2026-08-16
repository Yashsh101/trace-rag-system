# TraceRAG

A citation-gated retrieval-augmented generation (RAG) platform with full query traceability. Upload a PDF, ask a grounded question, and see exactly which chunks were retrieved, how the answer was validated, and why the model answered or declined to answer.

**Live demo:** [https://trace-rag-system-yashsh101s-projects.vercel.app](https://trace-rag-system-yashsh101s-projects.vercel.app)
**GitHub:** [github.com/Yashsh101/trace-rag-system](https://github.com/Yashsh101/trace-rag-system)

---

## Key Features

- **Citation-gated answers.** Every answer is tied to retrieved source chunks with inline `[S1]`-style citations. If no relevant evidence exists, the system returns an explicit `no_answer` state instead of hallucinating.
- **Full query traces.** Each query is logged with retrieval results, reranked chunks, validation gates, latency breakdown, model metadata, and cost estimates, retrievable via the trace endpoint.
- **Hybrid retrieval.** Combines BM25 keyword search with vector similarity search, merged with reciprocal rank fusion, plus an optional reranking step.
- **Document-level access control.** API keys carry a `user_id` and group memberships; ACL checks filter which documents a key can retrieve from.
- **Durable ingestion jobs.** PDF uploads become tracked jobs with queued → processing → completed/failed lifecycle and a status endpoint.
- **Evaluation gates.** A golden-QA eval runner (`evals/run_eval.py`) checks retrieval quality, faithfulness, and citation coverage.
- **Graceful degradation.** A deterministic local mode (text hashing for embeddings, template-based answers) allows offline smoke tests and CI without API keys; production uses OpenAI embeddings and chat.
- **Operator console.** A Next.js App Router dashboard for ingestion, chat with citation inspection, trace review, and settings.

## Architecture and End-to-End Workflow

```mermaid
flowchart LR
    U[User / Next.js Console] --> AUTH[API Key Auth + ACL]
    AUTH --> INGEST[PDF Parse + Chunk + Embed + Store]
    AUTH --> RETRIEVE[Hybrid Retrieval BM25 + Vector + RRF]
    RETRIEVE --> RERANK[Reranker]
    RERANK --> ACL2[ACL Filter on Retrieved Chunks]
    ACL2 --> LLM[LLM + Citation Formatter]
    LLM --> TRACE[Query Log + Trace]
    TRACE --> UI[Console: answer, citations, trace panel]
```

The end-to-end flow on a query:

1. `POST /api/v1/query` authenticates the API key and records a trace ID.
2. `retrieval_service` runs hybrid (BM25 + vector, RRF-fused) or vector-only retrieval from the chunk store.
3. The reranker re-scores candidates when `RERANKING_ENABLED=true`.
4. ACL filters drop chunks from documents the key cannot access.
5. If candidates survive, the LLM generates an answer with citations; otherwise a `no_answer` response is returned.
6. The full trace (chunks, scores, validation, latency, cost) is persisted and exposed via `GET /api/v1/query/{query_log_id}/trace`.

## Supported Input Sources

PDF documents (text-extractable, via `pypdf`). The parser reports `No extractable text found in PDF` when a scanned PDF requires OCR; OCR support is a planned future phase. Each page keeps page numbers, and chunks carry `page_start` / `page_end` metadata.

## Tech Stack

| Layer | Actual tools (as implemented) |
| --- | --- |
| Backend API | FastAPI, Pydantic v2, SQLAlchemy, uvicorn |
| Database | SQLite (local/demo mode) or Postgres + pgvector (production); migrations via Alembic |
| Retrieval | Local paragraph-aware token-window chunker, BM25, local vector search (SQLite), reranker |
| LLM / embeddings | OpenAI (`OPENAI_API_KEY` required in production); deterministic local fallback when the key is unset/replaced |
| Storage | Local filesystem (`LOCAL_STORAGE_PATH`) or S3-compatible (`S3_BUCKET` + endpoint) |
| Reliability | In-memory/Redis rate limiting, structured JSON logging, request trace IDs, readiness checks |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn-style primitives |
| CI | GitHub Actions (Postgres service + full pytest suite) |

## Project Structure

```text
trace-rag-system/
├── app/
│   ├── api/            routes.py        # /api/v1: health, documents, ingestion-jobs, query, trace
│   ├── core/           auth, config, errors, logging, rate_limit
│   ├── db/             base, session, engine
│   ├── models/         document, chunk, citation, query_log, ingestion_job, ...
│   ├── schemas/        request/response models
│   ├── services/       ingestion, retrieval, reranker, llm, embedding, storage,
│   │                   pdf_parser, chunker, citation_formatter, access_control, readiness, ...
│   └── workers/        ingestion_worker.py   # background job processor
├── alembic/            Postgres migrations
├── evals/              run_eval.py + golden_qa.example.jsonl
├── frontend/           Next.js operator console (app/, components/, lib/)
├── scripts/            init_local_db.py
├── tests/              17 test modules (auth, retrieval, citations, traces, red-team, ...)
├── serverless.py       Vercel serverless entry point
├── vercel.json         combined frontend + backend deployment config
├── Dockerfile / docker-compose*.yml / railway.json
└── .github/workflows/  CI
```

## Local Setup

### Backend

```bash
git clone https://github.com/Yashsh101/trace-rag-system.git
cd trace-rag-system
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # fill in APP_ENV, API keys, DATABASE_URL
```

SQLite mode (default for `APP_ENV=local` or `demo` — no Docker needed):

```bash
python scripts/init_local_db.py
uvicorn app.main:app --reload
```

Postgres + pgvector mode:

```bash
docker compose up -d postgres redis
export DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, run the background ingestion worker (only needed for async ingestion; in `INGESTION_MODE=sync` jobs process inline inside the request):

```bash
python -m app.workers.ingestion_worker
```

### Frontend

```bash
cd frontend
cp .env.example .env.local         # set NEXT_PUBLIC_RAG_API_BASE_URL and NEXT_PUBLIC_RAG_API_KEY
npm install
npm run dev
```

Open `http://localhost:3000`. The `/settings` page can override the API base URL and key in browser local storage (they default to the `.env.local` values).

## Environment Variables

`.env.example` is the source of truth; copy it to `.env` (backend) or `frontend/.env.example` → `.env.local` (frontend) and fill in only what your mode needs. Never commit real secrets.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `local`, `demo`, `test`, or `production` |
| `DATABASE_URL` | `sqlite:///...` for local/demo, `postgresql+psycopg://...` for Postgres + pgvector |
| `ADMIN_API_KEYS` / `USER_API_KEYS` | Auth keys; user keys use `key:user_id:group1,group2` format |
| `OPENAI_API_KEY` | Required in production for embeddings and answers |
| `OPENAI_EMBEDDING_MODEL` / `OPENAI_CHAT_MODEL` | Model selection |
| `STORAGE_BACKEND` | `local` or `s3` (with `S3_*` vars) |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT_BACKEND` | `memory` locally, `redis` + `REDIS_URL` in production |
| `INGESTION_MODE` | `sync` (inline processing, serverless-friendly) or unset (background worker via `python -m app.workers.ingestion_worker`) |
| `RETRIEVAL_MODE` / `RERANKING_ENABLED` | `hybrid` (default) or `vector`; reranker toggle |
| `NEXT_PUBLIC_RAG_API_BASE_URL` | Frontend API base URL; empty → same-origin relative URLs |
| `NEXT_PUBLIC_RAG_API_KEY` | Optional default key for private internal demos (browser-exposed) |

## API Usage

All endpoints are under `/api/v1` and require `X-API-Key` (except health). Local API docs: `http://localhost:8000/docs`.

```bash
# Health + readiness
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/ready

# Ingest a PDF (admin key)
curl -X POST http://localhost:8000/api/v1/documents/ingest \
  -H "X-API-Key: dev-admin-key" \
  -F "file=@sample.pdf"
# → {"job_id":"...","document_id":1,"status":"completed","chunk_count":3}

# Check ingestion job status
curl http://localhost:8000/api/v1/ingestion-jobs/<job_id> \
  -H "X-API-Key: dev-admin-key"

# Ask a grounded question (user key)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-user-key" \
  -d '{"question":"What are the key policy constraints?","top_k":6}'

# Inspect the full trace for a query
curl http://localhost:8000/api/v1/query/<query_log_id>/trace \
  -H "X-API-Key: dev-user-key"
```

**Streaming (SSE).** Streaming support is available for server-side event streams in the static console assets (`app/static/app.js` parses `text/event-stream` responses); the API routes in this release deliver JSON responses with full trace payloads. See `app/api/routes.py` for the query flow.

## Example Input and Output

Request:

```json
POST /api/v1/query
{"question": "What does this document say about retrieval traces?", "top_k": 6}
```

Response:

```json
{
  "trace_id": "5353bc9b11a04d42...",
  "query_log_id": 1,
  "answer": "The TraceRAG system provides citation-grounded answers with retrieval traces [S1].",
  "citations": [
    {
      "label": "S1",
      "chunk_id": 1,
      "document_id": 1,
      "filename": "smoke-test.pdf",
      "page_start": 1,
      "page_end": 1,
      "score": 0.85,
      "snippet": "TraceRAG Production Test Document ..."
    }
  ],
  "no_answer": false
}
```

## Testing

```bash
# Full backend suite (pytest, APP_ENV=test)
python -m pytest

# Frontend lint + typecheck
cd frontend && npm run lint && npm run typecheck && npm run build
```

The suite covers auth/ACL, chunking, embeddings, BM25/vector/hybrid retrieval, reranking, citation formatting, ingestion jobs, query/trace endpoints, observability, security red-teaming, and production-readiness checks. CI (`.github/workflows/ci.yml`) runs the suite against a Postgres service container.

## Deployment

**Vercel (single project, frontend + backend).** Push to `main` triggers a production build; `vercel.json` builds `frontend/` with `@vercel/next` and the root `serverless.py` with `@vercel/python`, routing `/api/v1/*` to the Python function.

Required production env vars on the Vercel project (see `.env.example`): `APP_ENV=demo`, `DATABASE_URL=sqlite:////tmp/trace-storage/trace.db`, `STORAGE_BACKEND=local`, `INGESTION_MODE=sync`, `CORS_ALLOWED_ORIGINS` set to your Vercel URL, and formatted `ADMIN_API_KEYS` / `USER_API_KEYS`.

**Production-grade (your own infra).** `Dockerfile` + `docker-compose.prod.yml` for the backend with Postgres + pgvector and Redis; see `DEPLOYMENT.md` and `RUNBOOK.md`. The frontend deploys anywhere Next.js runs.

## Known Limitations

- Ephemeral storage in the Vercel demo (`/tmp/trace-storage`): indexed documents and query logs reset when serverless containers recycle. For persistence, use `DATABASE_URL` (Postgres) + `STORAGE_BACKEND=s3`.
- PDF input only, with text extraction — scanned PDFs (OCR) are a planned improvement.
- No list endpoints for documents, jobs, queries, or eval history; the console tracks session views from browser state.
- No user login system; access control is key-and-group-based.
- SSE streaming exists in the static console assets but is not exposed by the current JSON API routes.

## Roadmap

- Persistent hosted demo with seeded documents (Postgres + object storage).
- OCR for scanned PDFs.
- Admin dashboard for eval history and failed-query review.
- Langfuse/OpenTelemetry trace export (`LANGFUSE_*` config already scaffolded).
- Multi-tenant document collections.
- Expose SSE streaming on the query endpoint.

## License and Author

MIT License. Built by [Yash Sharma](https://github.com/Yashsh101) — MCA (AI/ML) student focused on production-grade RAG, NLP, and backend AI systems.
