# Release Checklist

- [ ] `python -m compileall app tests evals`
- [ ] `python -m pytest`
- [ ] `alembic upgrade head` on staging
- [ ] Eval runner passes configured gates
- [ ] API readiness passes: `GET /api/v1/health/ready`
- [ ] Worker is running: `python -m app.workers.ingestion_worker`
- [ ] Redis rate limiter configured for production
- [ ] `SECURITY.md` reviewed
- [ ] Production env vars verified
- [ ] Backup/export tested with `python -m app.scripts.export_metadata`
- [ ] Health check passes
- [ ] Rollback plan confirmed
