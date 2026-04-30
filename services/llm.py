import asyncio
import structlog
from typing import AsyncGenerator
from groq import Groq, RateLimitError,  APIConnectionError

from core.config import settings
from core.exceptions import LLMUnavailableError, LLMRateLimitError, LLMTimeoutError
from core.constants import SSE_DONE_SIGNAL, SSE_ERROR_SIGNAL

logger = structlog.get_logger(__name__)

_groq_client: Groq | None = None


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client



async def _stream_groq_chunks(messages: list[dict]) -> AsyncGenerator[str, None]:
    client = _get_groq()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _run_stream():
        try:
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
                    asyncio.run_coroutine_threadsafe(queue.put(delta), loop)
        except RateLimitError as e:
            asyncio.run_coroutine_threadsafe(
                queue.put(f"__RATE_LIMIT__:{e}"), loop
            )
        except APIConnectionError as e:
            asyncio.run_coroutine_threadsafe(
                queue.put(f"__CONN_ERROR__:{e}"), loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                queue.put(f"__ERROR__:{e}"), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop.run_in_executor(executor, _run_stream)

    while True:
        token = await queue.get()
        if token is None:
            break
        if token.startswith("__RATE_LIMIT__:"):
            raise LLMRateLimitError(internal=token)
        if token.startswith("__CONN_ERROR__:"):
            raise LLMUnavailableError(internal=token)
        if token.startswith("__ERROR__:"):
            raise LLMUnavailableError(internal=token)
        yield token 




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
        full_text = ""
        async with asyncio.timeout(settings.request_timeout_seconds):
            async for token in _stream_groq_chunks(messages):
                full_text += token
        return full_text
    except asyncio.TimeoutError:
        if settings.fallback_enabled:
            return await _call_fallback(messages)
        raise LLMTimeoutError(internal="Groq stream timed out")
    except (LLMUnavailableError, LLMRateLimitError, LLMTimeoutError):
        if settings.fallback_enabled:
            return await _call_fallback(messages)
        raise





async def stream_completion(messages: list[dict]) -> AsyncGenerator[str, None]:
    logger.info("llm_stream_start")

    async def _attempt_groq():
        async for token in _stream_groq_chunks(messages):
            yield f"data: {token}\n\n"
        yield f"data: {SSE_DONE_SIGNAL}\n\n"

    try:
        async for chunk in _attempt_groq():
            yield chunk
        logger.info("llm_stream_complete")

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