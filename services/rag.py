from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import structlog

from core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class Chunk:
    source: str
    chunk_id: int
    text: str


class RAGService:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._vectorizer = None
        self._matrix = None
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready and bool(self._chunks) and self._vectorizer is not None

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def source_count(self) -> int:
        return len({c.source for c in self._chunks})

    async def initialize(self) -> None:
        if not settings.rag_enabled:
            logger.info("rag_disabled")
            return

        docs_path = Path(settings.rag_docs_path)
        if not docs_path.exists():
            logger.warning("rag_docs_path_not_found", path=str(docs_path))
            return

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            logger.warning("rag_missing_dependency", dependency="scikit-learn")
            return

        chunks = self._build_chunks_from_dir(docs_path)
        if not chunks:
            logger.warning("rag_no_chunks_built", path=str(docs_path))
            return

        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([c.text for c in chunks])

        self._chunks = chunks
        self._vectorizer = vectorizer
        self._matrix = matrix
        self._ready = True

        logger.info(
            "rag_initialized",
            docs_path=str(docs_path),
            chunks=len(self._chunks),
        )

    def retrieve_context(self, query: str, top_k: int | None = None) -> str:
        if not self.is_ready:
            return ""

        k = max(1, top_k or settings.rag_top_k)
        query_clean = query.strip()
        if not query_clean:
            return ""

        from sklearn.metrics.pairwise import cosine_similarity
        query_vec = self._vectorizer.transform([query_clean])
        similarities = cosine_similarity(query_vec, self._matrix).flatten()
        if similarities.size == 0:
            return ""

        ranked_idx = similarities.argsort()[::-1][:k]
        lines: list[str] = []
        for rank, idx in enumerate(ranked_idx, start=1):
            score = float(similarities[idx])
            if score <= 0:
                continue
            chunk = self._chunks[int(idx)]
            excerpt = re.sub(r"\s+", " ", chunk.text).strip()
            lines.append(
                f"[{rank}] Source: {chunk.source} | Chunk: {chunk.chunk_id} | Score: {score:.3f}\n{excerpt}"
            )

        return "\n\n".join(lines)

    def debug_retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        if not self.is_ready:
            return []

        k = max(1, top_k or settings.rag_top_k)
        query_clean = query.strip()
        if not query_clean:
            return []

        from sklearn.metrics.pairwise import cosine_similarity

        query_vec = self._vectorizer.transform([query_clean])
        similarities = cosine_similarity(query_vec, self._matrix).flatten()
        ranked_idx = similarities.argsort()[::-1][:k]

        items: list[dict] = []
        for idx in ranked_idx:
            score = float(similarities[idx])
            if score <= 0:
                continue
            chunk = self._chunks[int(idx)]
            items.append(
                {
                    "source": chunk.source,
                    "chunk_id": chunk.chunk_id,
                    "score": round(score, 6),
                    "text": chunk.text,
                }
            )
        return items

    def _build_chunks_from_dir(self, docs_path: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        for file_path in sorted(docs_path.rglob("*")):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            if suffix not in {".pdf", ".txt", ".md"}:
                continue

            text = self._extract_text(file_path)
            if not text:
                continue

            for chunk_id, chunk_text in enumerate(self._chunk_text(text), start=1):
                chunks.append(
                    Chunk(
                        source=file_path.name,
                        chunk_id=chunk_id,
                        text=chunk_text,
                    )
                )
        return chunks

    def _extract_text(self, file_path: Path) -> str:
        try:
            if file_path.suffix.lower() == ".pdf":
                try:
                    from pypdf import PdfReader
                except ImportError:
                    logger.warning("rag_missing_dependency", dependency="pypdf")
                    return ""
                reader = PdfReader(str(file_path))
                pages = [p.extract_text() or "" for p in reader.pages]
                return "\n".join(pages).strip()
            return file_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as exc:
            logger.warning("rag_extract_failed", file=str(file_path), error=str(exc))
            return ""

    def _chunk_text(self, text: str) -> Iterable[str]:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned:
            return []

        chunk_size = max(200, settings.rag_chunk_size)
        overlap = max(0, min(settings.rag_chunk_overlap, chunk_size - 1))

        chunks: list[str] = []
        start = 0
        length = len(cleaned)
        while start < length:
            end = min(length, start + chunk_size)
            chunks.append(cleaned[start:end])
            if end >= length:
                break
            start = max(0, end - overlap)

        return chunks


rag_service = RAGService()
