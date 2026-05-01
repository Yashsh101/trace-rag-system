# Deployment

TraceRAG is designed as a split deployment:

- `frontend/`: deploy to Vercel as a Next.js app.
- Backend root: deploy as a Dockerized FastAPI service on Render, Railway, or Cloud Run.
- Database: managed Postgres with pgvector.
- Cache: Redis for production rate limiting.
- Storage: S3-compatible object storage for uploaded/parsed documents.

## Local

```powershell
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload
```

## Production Compose

```powershell
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

Production compose runs:

- `api`: FastAPI request serving.
- `worker`: durable DB-polling ingestion worker using `python -m app.workers.ingestion_worker`.

## Frontend on Vercel

1. Import the repository in Vercel.
2. Set the project root to `frontend`.
3. Use the default Next.js build command.
4. Add:
   - `NEXT_PUBLIC_API_BASE_URL=https://<backend-host>/api/v1`
   - any additional frontend-only settings from `frontend/.env.example`
5. Redeploy after the backend production URL is stable.

## Backend on Render or Railway

Use the root `Dockerfile`.

Required start behavior:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Run the ingestion worker as a separate background worker service:

```bash
python -m app.workers.ingestion_worker
```

If the host does not support a separate worker process, use a platform that does. Running the API without the worker means uploaded documents may stay queued.

## Required Production Settings

- `APP_ENV=production`
- `OPENAI_API_KEY`
- `ADMIN_API_KEYS`
- `USER_API_KEYS`
- `STORAGE_BACKEND=s3`
- `S3_BUCKET`
- `CORS_ALLOWED_ORIGINS`
- `RATE_LIMIT_BACKEND=redis`
- `REDIS_URL`

Recommended managed services:

- Postgres/pgvector: Neon, Supabase, or Cloud SQL.
- Redis: Upstash or Railway Redis.
- Object storage: AWS S3, Cloudflare R2, or Backblaze B2 with S3 compatibility.

## Health Check

```text
GET /api/v1/health
```

Readiness:

```text
GET /api/v1/health/ready
```

Readiness checks DB connectivity, pgvector, Alembic head revision, storage write/read/delete, and config validity.

## Backup / Restore

- Back up Postgres with `pg_dump`.
- Back up object storage artifacts under `raw/` and `parsed/`.
- Export metadata with `python -m app.scripts.export_metadata --out-dir exports`.

## Rollback

1. Stop API and worker.
2. Restore the previous image tag.
3. Restore database backup if migrations are not backward-compatible.
4. Restore object storage snapshot if artifact writes must be rolled back.
5. Start worker only after API readiness passes.
