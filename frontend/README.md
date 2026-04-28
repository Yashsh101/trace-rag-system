# Mini RAG Console

Next.js operations console for the FastAPI Mini RAG backend.

## Stack

- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn-style local UI primitives
- Framer Motion
- Lucide icons

## Configuration

Create `.env.local`:

```powershell
Copy-Item .env.example .env.local
```

Defaults:

```text
NEXT_PUBLIC_RAG_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_RAG_API_KEY=dev-user-key
```

The settings page can override both values in browser local storage.

## Run

```powershell
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

Backend expected:

```powershell
python -m scripts.init_local_db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m app.workers.ingestion_worker
```

## Pages

- Dashboard: readiness, indexed document/session counts, ingestion jobs, recent queries, eval cards.
- Upload: drag-and-drop PDF upload with job polling.
- RAG Chat: source-grounded answers with clickable citations and trace metadata.
- Trace: retrieved chunks, scores, validation, model usage, latency, cost.
- Settings: API URL, API key, mode, theme, session controls.

## Notes

The current backend does not expose list endpoints for documents, jobs, recent queries, or eval history. The console therefore tracks those views from browser-session actions while still using live backend calls for readiness, ingestion, query, and trace.
