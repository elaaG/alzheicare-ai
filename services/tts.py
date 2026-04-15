import asyncio
import re
import structlog
import edge_tts
from langdetect import detect

from core.exceptions import TTSError

logger = structlog.get_logger(__name__)


VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "fr": "fr-FR-DeniseNeural",
    "ar": "ar-SA-HamedNeural",
    "es": "es-ES-AlvaroNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-AntonioNeural",
}


def _clean_for_speech(text: str) -> str:
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)
    cleaned = re.sub(r"⚠️|[#`~\[\]]", "", cleaned)
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


def _detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return lang
    except Exception:
        return "en"  # fallback


def _get_voice(lang: str) -> str:
    return VOICE_MAP.get(lang, VOICE_MAP["en"])


async def synthesise_speech(text: str) -> bytes:
    cleaned = _clean_for_speech(text)

    if not cleaned:
        raise TTSError(internal="Empty text after cleaning")

    cleaned = cleaned[:4096]

    # detect language
    lang = _detect_language(cleaned)
    voice = _get_voice(lang)

    logger.info("tts_start", language=lang, voice=voice)

    try:
        communicate = edge_tts.Communicate(cleaned, voice)

        audio_chunks = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        audio_bytes = b"".join(audio_chunks)

        logger.info(
            "tts_success",
            language=lang,
            size_kb=round(len(audio_bytes) / 1024, 1),
        )

        return audio_bytes

    except Exception as e:
        logger.error("tts_failed", error=str(e))
        raise TTSError(internal=str(e))