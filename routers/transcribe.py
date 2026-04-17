from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
import structlog
from langdetect import detect

from core.security import get_current_user, TokenPayload, verify_internal_key
from services.stt import transcribe_audio
from utils.validators import validate_audio_file, validate_language_code

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/transcribe", tags=["Speech-to-Text"])


class TranscribeResponse(BaseModel):
    text: str
    language_detected: str | None = None
    duration_hint: str = "Use this text as input to /chat/stream"


@router.post("", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(..., description="Audio file: webm, mp3, wav, m4a, ogg"),
    language: str | None = Form(
        default=None,
        description="ISO 639-1 code ('fr', 'ar', 'en'). Leave null for auto-detect."
    ),
    user: TokenPayload = Depends(get_current_user),
    _: None = Depends(verify_internal_key),
):

    logger.info(
        "transcribe_request",
        user_id=user.sub,
        filename=audio.filename,
        content_type=audio.content_type,
        language=language or "auto",
    )

    language = validate_language_code(language)
    audio_bytes = await validate_audio_file(audio)

    text = await transcribe_audio(
        audio_bytes=audio_bytes,
        filename=audio.filename or "audio.webm",
        content_type=audio.content_type or "audio/webm",
        language=language,
    )

    logger.info(
        "transcribe_success",
        user_id=user.sub,
        char_count=len(text),
    )

    detected_language = language
    if not detected_language:
        try:
            detected_language = detect(text)
        except Exception:
            detected_language = None

    return TranscribeResponse(text=text, language_detected=detected_language)