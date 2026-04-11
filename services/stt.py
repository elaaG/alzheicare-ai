import asyncio
import structlog
from groq import Groq, RateLimitError, APIConnectionError

from core.config import settings
from core.exceptions import TranscriptionError, LLMRateLimitError
from utils.retry import retry_with_backoff

logger = structlog.get_logger(__name__)

_groq_client: Groq | None = None


def _get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


def _transcribe_sync(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    language: str | None,
) -> str:
    
    client = _get_groq()

    transcription = client.audio.transcriptions.create(
        model=settings.groq_stt_model,
        file=(filename, audio_bytes, content_type),
        language=language,          
        response_format="text",
    )

    return transcription


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    content_type: str = "audio/webm",
    language: str | None = None,    
) -> str:
    
    logger.info(
        "stt_start",
        filename=filename,
        size_kb=round(len(audio_bytes) / 1024, 1),
        language=language or "auto",
    )

    try:
        text = await retry_with_backoff(
            asyncio.to_thread,
            _transcribe_sync,
            audio_bytes,
            filename,
            content_type,
            language,
            max_retries=2,
            base_delay=1.5,
            exceptions=(APIConnectionError, Exception),
        )

        text = text.strip() if isinstance(text, str) else str(text).strip()

        if not text:
            logger.warning("stt_empty_result")
            raise TranscriptionError(internal="Whisper returned empty transcription")

        logger.info("stt_success", char_count=len(text))
        return text

    except RateLimitError as e:
        logger.warning("stt_rate_limited", error=str(e))
        raise LLMRateLimitError(internal=str(e))

    except TranscriptionError:
        raise

    except Exception as e:
        logger.error("stt_failed", error=str(e))
        raise TranscriptionError(internal=str(e))