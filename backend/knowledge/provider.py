"""
backend/knowledge/provider.py — RAG Knowledge Provider Implementation.

Implements the KnowledgeProvider abstract interface defined in
backend/services/providers/interfaces.py using the NOVA KnowledgeBase.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import DocumentType, RetrievalStatus
from backend.services.providers.interfaces import KnowledgeProvider

logger = logging.getLogger("nova.knowledge.provider")


class RAGKnowledgeProvider(KnowledgeProvider):
    """
    RAG-backed knowledge provider using the NOVA KnowledgeBase.
    Connects knowledge retrieval to the service and context engine layer.
    """

    def __init__(self, knowledge_base: Optional[KnowledgeBase] = None) -> None:
        self.kb = knowledge_base or KnowledgeBase()

    def search_knowledge(
        self,
        query: str,
        asset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search the KnowledgeBase and return formatted reference dicts.
        """
        filters: Dict[str, Any] = {}
        if asset_id:
            filters["equipment_id"] = asset_id

        result = self.kb.retrieve(query=query, top_k=top_k, filters=filters if filters else None)

        if result.status != RetrievalStatus.OK or not result.results:
            return []

        formatted: List[Dict[str, Any]] = []
        for chunk in result.results:
            doc_type = chunk.metadata.get("document_type", "OTHER")
            formatted.append({
                "source": chunk.citation.document_title or chunk.source,
                "document_id": chunk.document_id,
                "chunk_id": chunk.chunk_id,
                "section": chunk.section,
                "content": chunk.text,
                "relevance_score": chunk.score,
                "asset_id": chunk.metadata.get("equipment_id") or asset_id,
                "equipment_type": chunk.metadata.get("equipment_type"),
                "knowledge_type": doc_type,
                "content_hash": chunk.content_hash,
            })

        return formatted

    def get_operating_limits(
        self,
        asset_id: str,
        parameter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query operating limits from indexed manuals or equipment datasheets for asset_id.
        """
        query = f"Operating limits thresholds {parameter or ''} {asset_id}"
        results = self.search_knowledge(
            query=query,
            asset_id=asset_id,
            top_k=3,
        )

        if not results:
            return {}

        # Look for explicit limits metadata or return top matching excerpt
        top_match = results[0]
        return {
            "asset_id": asset_id,
            "parameter": parameter,
            "source": top_match["source"],
            "section": top_match["section"],
            "reference_text": top_match["content"][:200],
            "retrieved": True,
        }
