import time
import uuid
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.config import settings
from core.constants import REDIS_RATE_PREFIX, REDIS_RATE_TTL

logger = structlog.get_logger(__name__)


async def _get_redis_client():
    from memory.redis_memory import get_redis
    return await get_redis()


class RateLimitMiddleware(BaseHTTPMiddleware):
    RATE_LIMITED_PATHS = {"/chat/stream", "/transcribe", "/speak"}

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path
        if not any(path.endswith(p) for p in self.RATE_LIMITED_PATHS):
            return await call_next(request)

        redis = await _get_redis_client()
        if redis is None:
            logger.warning("rate_limit_skipped_no_redis")
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"{REDIS_RATE_PREFIX}{user_id or client_ip}:{path}"

        try:
            now = int(time.time())
            window_start = now - REDIS_RATE_TTL  
            pipe = redis.pipeline()
            pipe.zremrangebyscore(rate_key, 0, window_start)   
            pipe.zadd(rate_key, {f"{now}-{uuid.uuid4().hex[:8]}": now})               
            pipe.zcard(rate_key)                               
            pipe.expire(rate_key, REDIS_RATE_TTL + 10)        
            results = await pipe.execute()

            request_count = results[2]

            if request_count > settings.rate_limit_per_minute:
                logger.warning(
                    "rate_limit_exceeded",
                    key=rate_key,
                    count=request_count,
                    limit=settings.rate_limit_per_minute,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "message": "Trop de requêtes. Veuillez patienter avant de réessayer.",
                        "retry_after_seconds": REDIS_RATE_TTL,
                    },
                    headers={"Retry-After": str(REDIS_RATE_TTL)},
                )

        except Exception as e:
            logger.error("rate_limit_check_failed", error=str(e))

        return await call_next(request)