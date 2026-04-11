import asyncio
import structlog
from typing import AsyncGenerator
from groq import Groq, RateLimitError, APIStatusError, APIConnectionError

from core.config import settings
from core.exceptions import LLMUnavailableError, LLMRateLimitError, LLMTimeoutError
from core.constants import SSE_DONE_SIGNAL, SSE_ERROR_SIGNAL
from utils.retry import retry_with_backoff

logger = structlog.get_logger(__name__)

_groq_client: Groq | None = None


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


def _stream_groq_sync(messages: list[dict]) -> str:
    
    client = _get_groq()
    full_text = ""

    stream = client.chat.completions.create(
        model=settings.groq_chat_model,
        messages=messages,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            full_text += delta

    return full_text


async def _call_groq_with_retry(messages: list[dict]) -> str:
   
    try:
        return await retry_with_backoff(
            asyncio.to_thread,
            _stream_groq_sync,
            messages,
            max_retries=3,
            base_delay=2.0,
            exceptions=(APIConnectionError,),
        )
    except RateLimitError as e:
        logger.warning("groq_rate_limited", error=str(e))
        raise LLMRateLimitError(internal=str(e))
    except APIConnectionError as e:
        logger.error("groq_connection_error", error=str(e))
        raise LLMUnavailableError(internal=str(e))
    except asyncio.TimeoutError:
        raise LLMTimeoutError(internal="Groq call timed out")


async def _call_fallback(messages: list[dict]) -> str:
    
    if not settings.fallback_enabled:
        raise LLMUnavailableError(internal="Fallback not configured")

    import httpx

    logger.warning("llm_using_fallback_openrouter")

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://alzheicare.tn",
                    "X-Title": "AlzheiCare AI Assistant",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    except Exception as e:
        logger.error("fallback_failed", error=str(e))
        raise LLMUnavailableError(internal=f"Both Groq and fallback failed: {e}")


async def get_completion(messages: list[dict]) -> str:
    
    try:
        return await asyncio.wait_for(
            _call_groq_with_retry(messages),
            timeout=settings.request_timeout_seconds,
        )
    except (LLMUnavailableError, LLMRateLimitError, LLMTimeoutError):
        if settings.fallback_enabled:
            return await _call_fallback(messages)
        raise


async def stream_completion(messages: list[dict]) -> AsyncGenerator[str, None]:
    
    logger.info("llm_stream_start")

    try:
        full_response = await asyncio.wait_for(
            _call_groq_with_retry(messages),
            timeout=settings.request_timeout_seconds,
        )

        
        words = full_response.split(" ")
        for i, word in enumerate(words):
            token = word if i == len(words) - 1 else word + " "
            yield f"data: {token}\n\n"
            await asyncio.sleep(0)  

        yield f"data: {SSE_DONE_SIGNAL}\n\n"
        logger.info("llm_stream_complete", tokens=len(words))

    except (LLMRateLimitError, LLMUnavailableError, LLMTimeoutError) as e:
        
        if settings.fallback_enabled:
            logger.warning("llm_stream_switching_to_fallback")
            try:
                fallback_text = await _call_fallback(messages)
                words = fallback_text.split(" ")
                for i, word in enumerate(words):
                    token = word if i == len(words) - 1 else word + " "
                    yield f"data: {token}\n\n"
                    await asyncio.sleep(0)
                yield f"data: {SSE_DONE_SIGNAL}\n\n"
                return
            except Exception as fe:
                logger.error("llm_fallback_also_failed", error=str(fe))

        logger.error("llm_stream_failed", error=str(e))
        yield f"data: {SSE_ERROR_SIGNAL}\n\n"

    except Exception as e:
        logger.error("llm_stream_unexpected_error", error=str(e))
        yield f"data: {SSE_ERROR_SIGNAL}\n\n"