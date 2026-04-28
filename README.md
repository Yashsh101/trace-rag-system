# TraceRAG 🔍

**AI you can trace, verify, and trust.**

A production-grade **Retrieval-Augmented Generation (RAG)** system designed for **grounded responses, full traceability, and real-world AI reliability**.

---

## 🚀 Overview

TraceRAG is a full-stack RAG platform built like a real AI system — not a demo.

It delivers:
- Hybrid retrieval (vector + keyword)
- Citation-grounded answers
- End-to-end ingestion pipeline
- Traceable model outputs
- Evaluation-driven quality

---

## ✨ Key Features

- **Hybrid Search** — pgvector + full-text search  
- **Citations** — every answer backed by sources  
- **Traceability** — inspect retrieval + reasoning path  
- **Ingestion Pipeline** — async worker, durable processing  
- **ACL Security** — document-level access control  
- **Eval System** — faithfulness, relevance, correctness  
- **Dual Mode** — local deterministic + production LLM  

---

## 🏗️ Architecture


Next.js → FastAPI → Retrieval (Vector + Keyword)
→ LLM → Citations → Trace → Eval


---

## ⚙️ Stack

- **Backend:** FastAPI, Python  
- **Frontend:** Next.js, TypeScript, Tailwind  
- **DB:** Postgres + pgvector (prod), SQLite (local)  
- **LLM:** OpenAI / Local mode  
- **Infra:** Docker-ready  

---

## 🚀 Run

```bash
python -m scripts.init_local_db
uvicorn app.main:app --reload
python -m app.workers.ingestion_worker
cd frontend && npm install && npm run dev
🔌 API
/api/v1/documents/ingest
/api/v1/query
/api/v1/ingestion-jobs/{id}
/api/v1/health/ready
/api/v1/query/{id}/trace
📊 Why TraceRAG

Most RAG systems lack:

observability
grounding
evaluation

TraceRAG solves all three.

⚠️ Notes
SQLite is for local dev only
Use Postgres + pgvector + OpenAI for production
⭐️

If this project helped you, consider giving it a star.
