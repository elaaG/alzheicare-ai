import json
import structlog
import redis.asyncio as aioredis
from typing import Optional

from core.config import settings
from core.constants import REDIS_HISTORY_PREFIX, REDIS_HISTORY_TTL

logger = structlog.get_logger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,   
            socket_timeout=2,
        )
        await client.ping()
        _redis_client = client
        logger.info("redis_connected", url=settings.redis_url)
        return _redis_client
    except Exception as e:
        logger.warning("redis_unavailable", error=str(e))
        return None


async def get_history(user_id: str) -> list[dict]:
    redis = await get_redis()
    if redis is None:
        logger.warning("memory_degraded_no_redis", user_id=user_id)
        return []

    key = f"{REDIS_HISTORY_PREFIX}{user_id}"
    try:
        raw = await redis.get(key)
        if not raw:
            return []

        history = json.loads(raw)
        return history[-settings.max_history_messages:]

    except Exception as e:
        logger.error("redis_get_failed", user_id=user_id, error=str(e))
        return []  


async def save_history(user_id: str, history: list[dict]) -> None:
    redis = await get_redis()
    if redis is None:
        return

    key = f"{REDIS_HISTORY_PREFIX}{user_id}"
    # Keep only the last N messages to control memory usage
    trimmed = history[-settings.max_history_messages:]

    try:
        await redis.setex(key, REDIS_HISTORY_TTL, json.dumps(trimmed))
    except Exception as e:
        logger.error("redis_save_failed", user_id=user_id, error=str(e))


async def append_exchange(
    user_id: str,
    user_message: str,
    assistant_reply: str,
) -> None:
    
    history = await get_history(user_id)
    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})
    await save_history(user_id, history)


async def clear_history(user_id: str) -> None:
    redis = await get_redis()
    if redis is None:
        return

    key = f"{REDIS_HISTORY_PREFIX}{user_id}"
    try:
        await redis.delete(key)
        logger.info("history_cleared", user_id=user_id)
    except Exception as e:
        logger.error("redis_delete_failed", user_id=user_id, error=str(e))


async def health_check() -> dict:
    redis = await get_redis()
    if redis is None:
        return {"status": "unavailable", "degraded": True}
    try:
        await redis.ping()
        return {"status": "connected", "degraded": False}
    except Exception as e:
        return {"status": "error", "detail": str(e), "degraded": True}