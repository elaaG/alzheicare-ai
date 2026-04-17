from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from core.security import get_current_user, TokenPayload, verify_internal_key
from core.prompt import build_messages
from core.exceptions import EmptyMessageError
from services.llm import stream_completion, get_completion
from services.search import needs_web_search, search_alzheimer_research
from services.rag import rag_service
from memory.redis_memory import get_history, append_exchange
from utils.validators import validate_message

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code ('fr', 'ar', 'en'). Auto-detected if null."
    )


class ChatResponse(BaseModel):
    reply: str
    used_search: bool = False


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
    _: None = Depends(verify_internal_key),
):

    message = validate_message(req.message)

    logger.info(
        "chat_stream_request",
        user_id=user.sub,
        patient_id=user.patient_id,
        patient_stage=user.patient_stage,
        user_role=user.role,
        message_length=len(message),
    )

    history = await get_history(user.sub)

    search_context = ""
    rag_context = rag_service.retrieve_context(message)
    if needs_web_search(message):
        logger.info("chat_triggering_search", query=message[:80])
        search_context = await search_alzheimer_research(message)

    messages = build_messages(
        user_message=message,
        user=user,
        history=history,
        search_context=search_context,
        rag_context=rag_context,
    )

    async def event_generator():
        complete_response = ""

        async for chunk in stream_completion(messages):
            yield chunk
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                token = chunk[6:].strip()
                complete_response += token + " "

        if complete_response.strip():
            await append_exchange(
                user_id=user.sub,
                user_message=message,
                assistant_reply=complete_response.strip(),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no", 
        },
    )


@router.post("", response_model=ChatResponse)
async def chat_sync(
    req: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
    _: None = Depends(verify_internal_key),
):
   
    message = validate_message(req.message)

    history = await get_history(user.sub)

    used_search = False
    search_context = ""
    rag_context = rag_service.retrieve_context(message)
    if needs_web_search(message):
        search_context = await search_alzheimer_research(message)
        used_search = bool(search_context)

    messages = build_messages(
        user_message=message,
        user=user,
        history=history,
        search_context=search_context,
        rag_context=rag_context,
    )

    reply = await get_completion(messages)

    await append_exchange(
        user_id=user.sub,
        user_message=message,
        assistant_reply=reply,
    )

    logger.info("chat_sync_complete", reply_length=len(reply))

    return ChatResponse(reply=reply, used_search=used_search)


@router.delete("/history")
async def clear_chat_history(
    user: TokenPayload = Depends(get_current_user),
    _: None = Depends(verify_internal_key),
):
    from memory.redis_memory import clear_history
    await clear_history(user.sub)
    logger.info("chat_history_cleared", user_id=user.sub)
    return {"message": "Historique effacé."}