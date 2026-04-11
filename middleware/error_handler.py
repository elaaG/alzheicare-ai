import traceback
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from core.exceptions import AlzheiCareException

logger = structlog.get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(AlzheiCareException)
    async def alzheicare_exception_handler(
        request: Request,
        exc: AlzheiCareException,
    ) -> JSONResponse:
        correlation_id = request.headers.get("X-Correlation-ID", "unknown")

        logger.warning(
            "alzheicare_error",
            status_code=exc.status_code,
            detail=exc.detail,
            internal=getattr(exc, "internal", ""),
            path=request.url.path,
            method=request.method,
            correlation_id=correlation_id,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "correlation_id": correlation_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        correlation_id = request.headers.get("X-Correlation-ID", "unknown")

        errors = []
        for error in exc.errors():
            field = " → ".join(str(loc) for loc in error["loc"])
            errors.append(f"{field}: {error['msg']}")

        logger.warning(
            "validation_error",
            errors=errors,
            path=request.url.path,
            correlation_id=correlation_id,
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "message": "Données invalides",
                "details": errors,
                "correlation_id": correlation_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        
        correlation_id = request.headers.get("X-Correlation-ID", "unknown")

        logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            error=str(exc),
            traceback=traceback.format_exc(),
            path=request.url.path,
            method=request.method,
            correlation_id=correlation_id,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Une erreur interne s'est produite",
                "correlation_id": correlation_id,
            },
        )