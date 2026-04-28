import logging
import signal
import time
import uuid

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.ingestion_job_service import IngestionJobService

configure_logging()
logger = logging.getLogger(__name__)


class ShutdownFlag:
    stop = False


def _handle_shutdown(signum, frame) -> None:
    ShutdownFlag.stop = True


def run_worker(poll_interval_seconds: float = 2.0, stale_after_seconds: int = 900) -> None:
    worker_id = f"ingestion-worker-{uuid.uuid4().hex[:8]}"
    service = IngestionJobService()
    logger.info("ingestion_worker_started", extra={"event": "ingestion_worker_started"})

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while not ShutdownFlag.stop:
        db = SessionLocal()
        try:
            service.recover_stale_jobs(db, stale_after_seconds=stale_after_seconds)
            job = service.claim_next_job(db, worker_id=worker_id)
        finally:
            db.close()

        if job is None:
            time.sleep(poll_interval_seconds)
            continue

        service.process_job(job.id, worker_id=worker_id)

    logger.info("ingestion_worker_stopped", extra={"event": "ingestion_worker_stopped"})


if __name__ == "__main__":
    run_worker()

