# Deployment

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
