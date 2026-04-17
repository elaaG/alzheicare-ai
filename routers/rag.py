from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.config import settings
from core.security import get_current_user, verify_internal_key, TokenPayload
from services.rag import rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])


class RagStatusResponse(BaseModel):
    enabled: bool
    ready: bool
    docs_path: str
    source_count: int
    chunk_count: int
    top_k: int
    chunk_size: int
    chunk_overlap: int


class RagDebugRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class RagDebugChunk(BaseModel):
    source: str
    chunk_id: int
    score: float
    text: str


class RagDebugResponse(BaseModel):
    query: str
    top_k: int
    retrieved: list[RagDebugChunk]


@router.get("/status", response_model=RagStatusResponse)
async def rag_status(
    _: TokenPayload = Depends(get_current_user),
    __: None = Depends(verify_internal_key),
):
    return RagStatusResponse(
        enabled=settings.rag_enabled,
        ready=rag_service.is_ready,
        docs_path=settings.rag_docs_path,
        source_count=rag_service.source_count,
        chunk_count=rag_service.chunk_count,
        top_k=settings.rag_top_k,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )


@router.post("/debug-retrieve", response_model=RagDebugResponse)
async def rag_debug_retrieve(
    req: RagDebugRequest,
    _: TokenPayload = Depends(get_current_user),
    __: None = Depends(verify_internal_key),
):
    top_k = req.top_k or settings.rag_top_k
    results = rag_service.debug_retrieve(req.query, top_k=top_k)
    return RagDebugResponse(
        query=req.query,
        top_k=top_k,
        retrieved=[RagDebugChunk(**item) for item in results],
    )


@router.post("/reload", response_model=RagStatusResponse)
async def rag_reload(
    _: TokenPayload = Depends(get_current_user),
    __: None = Depends(verify_internal_key),
):
    await rag_service.initialize()
    return RagStatusResponse(
        enabled=settings.rag_enabled,
        ready=rag_service.is_ready,
        docs_path=settings.rag_docs_path,
        source_count=rag_service.source_count,
        chunk_count=rag_service.chunk_count,
        top_k=settings.rag_top_k,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
