# TraceRAG 🔍

**AI you can trace, verify, and trust.**

Production-grade **Retrieval-Augmented Generation (RAG)** system with full-stack architecture, citation-grounded responses, evaluation pipeline, and traceable AI outputs.

---

## 🚀 Overview

TraceRAG is a full-stack RAG platform designed like a real-world AI system — not a demo.

It enables:
- 📄 Document ingestion (PDFs)
- 🔍 Hybrid retrieval (vector + keyword)
- 🧠 Grounded AI responses
- 📌 Source citations
- 🔎 Full traceability of outputs
- 📊 Evaluation-driven quality checks

---

## 🧠 Key Features

- ✅ Hybrid search (pgvector + keyword)
- ✅ Citation-grounded answers (no hallucination)
- ✅ Ingestion pipeline with background worker
- ✅ Document-level ACL (secure access)
- ✅ Trace panel (retrieval + reasoning visibility)
- ✅ Eval pipeline (faithfulness, relevance, correctness)
- ✅ Local + production-ready architecture
- ✅ FastAPI backend + Next.js frontend

---

## 🏗️ Architecture

```text
Frontend (Next.js)
        ↓
FastAPI API Layer
        ↓
Retrieval System (Hybrid Search)
        ↓
Vector DB (pgvector) + Metadata DB
        ↓
LLM (OpenAI / Local Mode)
        ↓
Trace + Eval + Logging
🖥️ Demo Flow
Upload a PDF
Wait for ingestion
Ask a question
Get:
grounded answer
citations [S1]
traceable reasoning
⚙️ Tech Stack
Backend: FastAPI, Python
Frontend: Next.js, TypeScript, Tailwind
Database: Postgres + pgvector (prod), SQLite (local)
LLM: OpenAI / Local deterministic mode
Infra: Docker-ready
Testing: Pytest + eval pipeline
🧪 Evaluation

TraceRAG includes a built-in eval pipeline:

Retrieval relevance
Faithfulness
Citation correctness
No-answer handling

All metrics validated during development.

🚀 Run Locally
Backend
python -m scripts.init_local_db
uvicorn app.main:app --reload
Worker
python -m app.workers.ingestion_worker
Frontend
cd frontend
npm install
npm run dev
🔍 API
/api/v1/documents/ingest
/api/v1/query
/api/v1/ingestion-jobs/{id}
/api/v1/health/ready
/api/v1/query/{id}/trace
🔐 Security
API key authentication
Document-level ACL
Rate limiting
Input validation
Prompt injection protection
📦 Production Setup
docker compose -f docker-compose.prod.yml up -d
alembic upgrade head
📊 What Makes This Different

Most RAG demos:

❌ no evals
❌ no citations
❌ no traceability

TraceRAG:

✅ grounded answers
✅ observable system
✅ production-oriented design
⚠️ Limitations
SQLite used in local mode (not production scale)
Requires OpenAI key for real LLM quality
No OCR/table extraction yet
🎯 Future Improvements
OCR + table parsing
Advanced reranker
Multi-tenant support
SSO authentication
Cloud deployment
👨‍💻 Author

Built as a production-grade AI system project.

⭐️ Star this repo

If you found this useful, consider starring ⭐️
