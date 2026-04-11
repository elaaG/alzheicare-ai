import asyncio
import random
import structlog
from functools import wraps
from typing import Callable, TypeVar, Any

logger = structlog.get_logger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> Any:
    
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except exceptions as e:
            last_exception = e
            error_name = type(e).__name__

            if attempt == max_retries:
                logger.error(
                    "retry_exhausted",
                    func=func.__name__,
                    attempts=attempt + 1,
                    error=error_name,
                    detail=str(e),
                )
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.2 * random.uniform(-1, 1)
            wait = max(0.1, delay + jitter)

            logger.warning(
                "retry_attempt",
                func=func.__name__,
                attempt=attempt + 1,
                max_retries=max_retries,
                wait_seconds=round(wait, 2),
                error=error_name,
            )

            await asyncio.sleep(wait)

    raise last_exception  

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,),
):
   
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func, *args,
                max_retries=max_retries,
                base_delay=base_delay,
                exceptions=exceptions,
                **kwargs,
            )
        return wrapper
    return decorator