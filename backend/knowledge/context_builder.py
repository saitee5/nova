"""
backend/knowledge/context_builder.py — RAG Context Builder for Reasoning Layers.

Assembles retrieved engineering evidence and ML model evidence into structured,
grounded context packages for future NOVA reasoning layers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from backend.knowledge.evidence_bridge import ModelEvidenceBridge
from backend.knowledge.models import (
    CanonicalEvidence,
    Citation,
    EvidenceType,
    RAGContext,
    RetrievalResult,
    RetrievalStatus,
    RetrievedChunk,
)

logger = logging.getLogger("nova.knowledge.context_builder")


class RAGContextBuilder:
    """
    Constructs structured, traceable context containers from retrieved evidence.
    """

    @staticmethod
    def build_context(
        query: str,
        retrieval_result: Optional[RetrievalResult] = None,
        model_evidence: Optional[List[CanonicalEvidence]] = None,
        additional_evidence: Optional[List[CanonicalEvidence]] = None,
        max_context_chars: int = 4000,
    ) -> RAGContext:
        """
        Assemble a complete RAGContext containing document evidence, citations, and model evidence.
        """
        all_evidence: List[CanonicalEvidence] = []
        all_citations: List[Citation] = []
        status = RetrievalStatus.OK

        # 1. Process document retrieval results
        if retrieval_result is not None:
            status = retrieval_result.status
            for chunk in retrieval_result.results:
                ev = ModelEvidenceBridge.from_retrieved_chunk(chunk)
                all_evidence.append(ev)
                if ev.citation is not None:
                    all_citations.append(ev.citation)

        # 2. Attach ML model evidence
        if model_evidence:
            all_evidence.extend(model_evidence)

        # 3. Attach additional evidence
        if additional_evidence:
            all_evidence.extend(additional_evidence)

        # 4. Format structured prompt-friendly context text
        formatted_lines: List[str] = [
            f"=== NOVA ENGINEERING CONTEXT (Query: '{query}') ===",
        ]

        if not all_evidence:
            formatted_lines.append("[No relevant authoritative knowledge or model evidence available]")
        else:
            doc_evs = [e for e in all_evidence if e.evidence_type == EvidenceType.DOCUMENT_EVIDENCE]
            mod_evs = [e for e in all_evidence if e.evidence_type == EvidenceType.MODEL_EVIDENCE]

            if doc_evs:
                formatted_lines.append("\n--- Authoritative Documentation Evidence ---")
                for idx, ev in enumerate(doc_evs, 1):
                    cite_info = ""
                    if ev.citation:
                        sec_str = f", Section: {ev.citation.section}" if ev.citation.section else ""
                        cite_info = f" [Doc: {ev.citation.document_id}{sec_str}]"
                    formatted_lines.append(f"[{idx}] {ev.source_title}{cite_info} (Score: {ev.relevance_score:.2f}):\n{ev.excerpt}\n")

            if mod_evs:
                formatted_lines.append("\n--- Machine Learning Model Evidence ---")
                for idx, ev in enumerate(mod_evs, 1):
                    target_note = ""
                    if ev.provenance.get("target_type") == "physics_informed_synthetic_surrogate":
                        target_note = " (SYNTHETIC SURROGATE - NOT MEASURED TELEMETRY)"
                    formatted_lines.append(f"[{idx}] {ev.source_title}{target_note}:\n{ev.excerpt}\n")

        formatted_context = "\n".join(formatted_lines)
        if len(formatted_context) > max_context_chars:
            formatted_context = formatted_context[:max_context_chars] + "\n... [Context truncated to maximum length]"

        return RAGContext(
            query=query,
            status=status,
            evidence_items=all_evidence,
            citations=all_citations,
            formatted_context=formatted_context,
            metadata={
                "total_evidence_items": len(all_evidence),
                "document_evidence_count": len([e for e in all_evidence if e.evidence_type == EvidenceType.DOCUMENT_EVIDENCE]),
                "model_evidence_count": len([e for e in all_evidence if e.evidence_type == EvidenceType.MODEL_EVIDENCE]),
                "total_citations": len(all_citations),
            },
        )
