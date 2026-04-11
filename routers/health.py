import asyncio
import httpx
import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from core.config import settings
from memory.redis_memory import health_check as redis_health

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Health"])


class DependencyStatus(BaseModel):
    status: str       
    degraded: bool = False
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str                             
    version: str
    environment: str
    dependencies: dict[str, DependencyStatus]


async def _check_groq() -> DependencyStatus:
    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)
        await asyncio.to_thread(client.models.list)
        return DependencyStatus(status="ok")
    except Exception as e:
        return DependencyStatus(
            status="unavailable",
            degraded=True,
            detail=str(e)[:100],
        )


async def _check_tavily() -> DependencyStatus:
    if not settings.search_enabled:
        return DependencyStatus(
            status="disabled",
            detail="TAVILY_API_KEY not configured — web search disabled",
        )
    return DependencyStatus(status="ok")


async def _check_fallback() -> DependencyStatus:
    if not settings.fallback_enabled:
        return DependencyStatus(
            status="disabled",
            detail="OPENROUTER_API_KEY not configured — no LLM fallback",
        )
    return DependencyStatus(status="ok")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    
    redis_status_raw, groq_status, tavily_status, fallback_status = (
        await asyncio.gather(
            redis_health(),
            _check_groq(),
            _check_tavily(),
            _check_fallback(),
            return_exceptions=True,
        )
    )

    redis_status = DependencyStatus(
        status=redis_status_raw.get("status", "error"),
        degraded=redis_status_raw.get("degraded", True),
    ) if isinstance(redis_status_raw, dict) else DependencyStatus(
        status="error", degraded=True
    )

    dependencies = {
        "groq":     groq_status    if isinstance(groq_status, DependencyStatus)    else DependencyStatus(status="error", degraded=True),
        "redis":    redis_status,
        "tavily":   tavily_status  if isinstance(tavily_status, DependencyStatus)  else DependencyStatus(status="error", degraded=True),
        "fallback": fallback_status if isinstance(fallback_status, DependencyStatus) else DependencyStatus(status="error", degraded=True),
    }

    groq_ok = dependencies["groq"].status == "ok"
    fallback_ok = dependencies["fallback"].status == "ok"
    any_degraded = any(d.degraded for d in dependencies.values())

    if not groq_ok and not fallback_ok:
        overall_status = "unhealthy"
    elif any_degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    logger.info("health_check", status=overall_status)

    from fastapi.responses import JSONResponse
    response_body = HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.app_env,
        dependencies=dependencies,
    )

    status_code = 503 if overall_status == "unhealthy" else 200
    return JSONResponse(
        content=response_body.model_dump(),
        status_code=status_code,
    )


@router.get("/health/ping")
async def ping():
    return {"status": "ok", "version": settings.app_version}