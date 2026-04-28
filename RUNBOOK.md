# Runbook

## Failed Ingestion

1. Check `GET /api/v1/ingestion-jobs/{job_id}`.
2. Inspect `error_message`.
3. Check logs by `trace_id`.
4. Re-upload after correcting file type, OCR gap, or provider failure.
5. If jobs are stuck in `processing`, restart `python -m app.workers.ingestion_worker`; stale jobs are recovered to `queued`.

## Empty Retrieval Spike

1. Check query logs for `empty_retrieval=true`.
2. Confirm documents completed ingestion.
3. Confirm API key user has ACL access.
4. Run evals against a known dataset.

## Citation Failures

1. Check `citation_failure=true`.
2. Inspect `/api/v1/query/{query_log_id}/trace`.
3. Review retrieved chunks and citation scores.
4. Tune retrieval/reranking thresholds only with evals.

## Rate Limits

Increase `RATE_LIMIT_REQUESTS` or `RATE_LIMIT_WINDOW_SECONDS` only after checking traffic source and cost impact.

## Readiness Failure

1. Call `GET /api/v1/health/ready`.
2. If DB fails, check Postgres and `DATABASE_URL`.
3. If pgvector fails, run migrations and confirm extension creation.
4. If Alembic fails, run `alembic upgrade head`.
5. If storage fails, verify S3 credentials/bucket or local volume permissions.
