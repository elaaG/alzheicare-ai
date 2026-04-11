from dotenv import load_dotenv
load_dotenv()

from core.config import settings
from core.exceptions import AlzheiCareException

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.logging import configure_logging, RequestLoggingMiddleware
from middleware.error_handler import register_error_handlers
from middleware.rate_limiter import RateLimitMiddleware

from routers import chat, transcribe, speak, health

import structlog

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "alzheicare_ai_is_starting",
        version=settings.app_version,
        environment=settings.app_env,
        groq_model=settings.groq_chat_model,
        stt_model=settings.groq_stt_model,
        tts_model=settings.groq_tts_model,
        search_enabled=settings.search_enabled,
        fallback_enabled=settings.fallback_enabled,
    )

    try:
        from memory.redis_memory import get_redis
        redis = await get_redis()
        if redis:
            logger.info("startup_redis_connected")
        else:
            logger.warning("startup_redis_unavailable_degraded_mode")
    except Exception as e:
        logger.warning("startup_redis_error", error=str(e))

    logger.info("alzheicare_ai_ready", docs_url="/docs")

    yield

    logger.info("alzheicare_ai_shutting_down")
    from memory.redis_memory import _redis_client
    if _redis_client:
        await _redis_client.aclose()
    logger.info("alzheicare_ai_stopped")


app = FastAPI(
    title="AlzheiCare AI Assistant",
    lifespan=lifespan,
    description="""
    Intelligent AI assistant for Alzheimer's disease caregiving support.
    """,
    version=settings.app_version,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)


app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if not settings.is_production
        else [
            "http://localhost:5173",        
            "http://localhost:3000",        
            "https://alzheicare.tn",       
        ]
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(transcribe.router)
app.include_router(speak.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
        access_log=False,   
    )