import os
from fastapi import UploadFile
from core.config import settings
from core.constants import (
    SUPPORTED_AUDIO_TYPES,
    SUPPORTED_AUDIO_EXTENSIONS,
    VALID_ROLES,
    VALID_STAGES,
)
from core.exceptions import (
    AudioTooLargeError,
    InvalidAudioFormatError,
    EmptyMessageError,
    InvalidStageError,
    InvalidRoleError,
)


def validate_message(message: str) -> str:
    
    if not message or not message.strip():
        raise EmptyMessageError()

    cleaned = message.strip()

    max_length = 2000
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


def validate_stage(stage: int) -> int:
    if stage not in VALID_STAGES:
        raise InvalidStageError(stage)
    return stage


def validate_role(role: str) -> str:
    if role not in VALID_ROLES:
        raise InvalidRoleError(role)
    return role


async def validate_audio_file(audio: UploadFile) -> bytes:
    
    content_type = (audio.content_type or "").lower()
    filename = audio.filename or ""
    extension = os.path.splitext(filename)[1].lower()

    type_ok = content_type in SUPPORTED_AUDIO_TYPES
    ext_ok  = extension in SUPPORTED_AUDIO_EXTENSIONS

    if not type_ok and not ext_ok:
        raise InvalidAudioFormatError(received=content_type)

    # Read and check size
    audio_bytes = await audio.read()
    size_mb = len(audio_bytes) / (1024 * 1024)

    if size_mb > settings.max_audio_size_mb:
        raise AudioTooLargeError(max_mb=settings.max_audio_size_mb)

    if len(audio_bytes) < 100:
        raise InvalidAudioFormatError(received="empty file")

    return audio_bytes