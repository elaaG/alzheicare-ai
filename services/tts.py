import asyncio
import re
import structlog
from groq import Groq, RateLimitError, APIConnectionError
import httpx

from core.config import settings
from core.exceptions import TTSError, LLMRateLimitError
from utils.retry import retry_with_backoff

logger = structlog.get_logger(__name__)
logger.info("tts_config", voice=settings.groq_tts_voice, model=settings.groq_tts_model)
_groq_client: Groq | None = None


_CLEAN_PATTERN = re.compile(r"[⚠️*#`_~\[\]]+|(\*\*|__)(.*?)(\*\*|__)")


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


def _clean_for_speech(text: str) -> str:
   
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.*?)\*",   r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__",   r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_",     r"\1", cleaned)

    cleaned = re.sub(r"⚠️|[#`~\[\]]", "", cleaned)

    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)

    return cleaned.strip()




def _synthesise_sync(text: str) -> bytes:
    client = _get_groq()
    response = client.audio.speech.create(
        model=settings.groq_tts_model,
        voice=settings.groq_tts_voice,
        input=text[:4096],
        response_format="wav",
    )
    return response.read()    

async def synthesise_speech(text: str) -> bytes:
   
    cleaned = _clean_for_speech(text)

    if not cleaned:
        raise TTSError(internal="Empty text after cleaning")

    logger.info("tts_start", char_count=len(cleaned))

    try:
        audio_bytes = await retry_with_backoff(
            asyncio.to_thread,
            _synthesise_sync,
            cleaned,
            max_retries=2,
            base_delay=1.0,
            exceptions=(APIConnectionError, Exception),
        )

        logger.info("tts_success", size_kb=round(len(audio_bytes) / 1024, 1))
        return audio_bytes

    except RateLimitError as e:
        logger.warning("tts_rate_limited", error=str(e))
        raise LLMRateLimitError(internal=str(e))

    except TTSError:
        raise

    except Exception as e:
        logger.error("tts_failed", error=str(e))
        raise TTSError(internal=str(e))