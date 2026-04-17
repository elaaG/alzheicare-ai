from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
import structlog

from core.security import get_current_user, TokenPayload, verify_internal_key
from services.tts import synthesise_speech

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/speak", tags=["Text-to-Speech"])


class SpeakRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Text to synthesise. Markdown is automatically cleaned",
    )


@router.post(
    "",
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "MPEG audio stream (edge-tts output)",
        }
    },
)
async def speak(
    req: SpeakRequest,
    user: TokenPayload = Depends(get_current_user),
    _: None = Depends(verify_internal_key),
):
    logger.info(
        "speak_request",
        user_id=user.sub,
        text_length=len(req.text),
    )

    audio_bytes = await synthesise_speech(req.text)

    logger.info(
        "speak_success",
        user_id=user.sub,
        audio_size_kb=round(len(audio_bytes) / 1024, 1),
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=response.mp3",
            "Cache-Control": "no-store",  
        },
    )