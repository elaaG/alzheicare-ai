import uuid
import time
import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.constants import CORRELATION_ID_HEADER
from core.config import settings


def configure_logging() -> None:
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
    processors=processors,
    wrapper_class=structlog.make_filtering_bound_logger(20), 
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(), 
    cache_logger_on_first_use=True,
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or propagate correlation ID
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER) or
            str(uuid.uuid4())
        )

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            app_version=settings.app_version,
        )

        logger = structlog.get_logger(__name__)
        start_time = time.perf_counter()

        logger.info(
            "request_started",
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", ""),
        )

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response