"""
backend/knowledge/retriever.py — Clean Knowledge Retrieval API.

Provides strict, ranked retrieval with comprehensive source attribution,
citation tracing, and robust fail-safe error handling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.knowledge.models import (
    Citation,
    DocumentChunk,
    RetrievalResult,
    RetrievalStatus,
    RetrievedChunk,
)
from backend.knowledge.vector_index import LocalVectorIndex, VectorIndex
from backend.memory.embeddings import embed_text

logger = logging.getLogger("nova.knowledge.retriever")


_UNSET = object()


class KnowledgeRetriever:
    """
    High-level retrieval service for NOVA Knowledge Base.
    Ensures every returned chunk is fully attributed with citations and provenance.
    """

    def __init__(
        self,
        index: Any = _UNSET,
        min_score_threshold: float = 0.0,
    ) -> None:
        self.index = LocalVectorIndex() if index is _UNSET else index
        self.min_score_threshold = min_score_threshold

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Execute semantic similarity retrieval against the indexed engineering knowledge.

        Args:
            query: Natural language search string or operator query
            top_k: Maximum number of ranked results to return
            filters: Optional metadata filters (document_type, equipment_id, etc.)

        Returns:
            RetrievalResult containing ranked, attributed chunks and status.
        """
        # 1. Validate query
        if not query or not query.strip():
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.INVALID_QUERY,
                results=[],
                total_found=0,
                message="Query string is empty or invalid.",
                applied_filters=filters or {},
            )

        # 2. Check index availability and content
        if self.index is None:
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.KNOWLEDGE_BASE_UNAVAILABLE,
                results=[],
                total_found=0,
                message="Knowledge base index is unavailable.",
                applied_filters=filters or {},
            )

        if self.index.count() == 0:
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.NO_KNOWLEDGE_AVAILABLE,
                results=[],
                total_found=0,
                message="Knowledge base contains no indexed documents.",
                applied_filters=filters or {},
            )

        # 3. Vector embedding of query
        try:
            query_vector = embed_text(query.strip())
        except Exception as exc:
            logger.error("Failed to embed query '%s': %s", query, exc)
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.KNOWLEDGE_BASE_UNAVAILABLE,
                results=[],
                total_found=0,
                message=f"Embedding generation failed: {exc}",
                applied_filters=filters or {},
            )

        # 4. Search vector index with filters
        try:
            scored_candidates = self.index.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters,
            )
        except Exception as exc:
            logger.error("Vector search failed for query '%s': %s", query, exc)
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.KNOWLEDGE_BASE_UNAVAILABLE,
                results=[],
                total_found=0,
                message=f"Index search error: {exc}",
                applied_filters=filters or {},
            )

        # 5. Filter by threshold and build attributed results
        retrieved_items: List[RetrievedChunk] = []
        rank = 1

        for chunk, score in scored_candidates:
            if score < self.min_score_threshold:
                continue

            meta = chunk.metadata or {}
            source = meta.get("source") or "Unknown Authority"
            doc_title = meta.get("document_title") or f"Document {chunk.document_id}"
            section = chunk.section or meta.get("section", "")
            version = meta.get("version")
            page_ref = chunk.page_reference

            citation = Citation(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                source=source,
                document_title=doc_title,
                section=section,
                page_reference=page_ref,
                content_hash=chunk.content_hash,
                version=version,
            )

            retrieved_items.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    score=round(score, 4),
                    rank=rank,
                    source=source,
                    document_title=doc_title,
                    section=section,
                    metadata=meta,
                    content_hash=chunk.content_hash,
                    citation=citation,
                )
            )
            rank += 1

        # 6. Return outcome
        if not retrieved_items:
            return RetrievalResult(
                query=query,
                status=RetrievalStatus.NO_RELEVANT_EVIDENCE,
                results=[],
                total_found=0,
                message="No relevant knowledge matches the query criteria.",
                applied_filters=filters or {},
            )

        return RetrievalResult(
            query=query,
            status=RetrievalStatus.OK,
            results=retrieved_items,
            total_found=len(retrieved_items),
            message=f"Retrieved {len(retrieved_items)} relevant knowledge chunks.",
            applied_filters=filters or {},
        )
