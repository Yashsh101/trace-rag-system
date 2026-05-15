import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import configure_logging
from app.core.rate_limit import rate_limiter

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")
allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "X-Trace-ID", "Content-Type"],
)
app.include_router(router, prefix="/api/v1")
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id", uuid.uuid4().hex)
    request.state.trace_id = trace_id
    started = time.perf_counter()
    try:
        if request.method != "OPTIONS" and request.url.path not in {"/api/v1/health", "/api/v1/health/ready"}:
            client_key = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
            rate_limiter.check(client_key)
        response = await call_next(request)
    except AppError as exc:
        logger.warning(
            "request_rejected",
            extra={
                "event": "request_rejected",
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "trace_id": trace_id}},
            headers={"x-trace-id": trace_id},
        )
    except Exception:
        logger.exception("request_failed", extra={"trace_id": trace_id, "method": request.method, "path": request.url.path})
        raise
    response.headers["x-trace-id"] = trace_id
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "request_completed method=%s path=%s status=%s latency_ms=%s trace_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        trace_id,
        extra={
            "event": "request_completed",
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
        },
    )
    return response
