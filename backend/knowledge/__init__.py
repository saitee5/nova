"""
backend/knowledge — NOVA Knowledge Base & RAG Foundation Package.

Exports canonical document models, chunking, ingestion, vector indexing,
retrieval, evidence modeling, and context assembly.
"""

from backend.knowledge.models import (
    Citation,
    DocumentChunk,
    DocumentType,
    EvidenceType,
    KnowledgeDocument,
    RetrievalResult,
    RetrievalStatus,
    RetrievedChunk,
    CanonicalEvidence,
    RAGContext,
)
from backend.knowledge.normalization import compute_content_hash, normalize_text
from backend.knowledge.chunking import SectionAwareChunker
from backend.knowledge.ingestion import DocumentIngestor, DocumentIngestionError
from backend.knowledge.vector_index import LocalVectorIndex, VectorIndex
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.evidence_bridge import ModelEvidenceBridge
from backend.knowledge.context_builder import RAGContextBuilder
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.provider import RAGKnowledgeProvider

__all__ = [
    "Citation",
    "DocumentChunk",
    "DocumentType",
    "EvidenceType",
    "KnowledgeDocument",
    "RetrievalResult",
    "RetrievalStatus",
    "RetrievedChunk",
    "CanonicalEvidence",
    "RAGContext",
    "compute_content_hash",
    "normalize_text",
    "SectionAwareChunker",
    "DocumentIngestor",
    "DocumentIngestionError",
    "LocalVectorIndex",
    "VectorIndex",
    "KnowledgeRetriever",
    "ModelEvidenceBridge",
    "RAGContextBuilder",
    "KnowledgeBase",
    "RAGKnowledgeProvider",
]
