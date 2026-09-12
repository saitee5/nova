"""
backend/knowledge/knowledge_base.py — Unified NOVA Knowledge Base Manager.

Coordinates ingestion, normalization, chunking, indexing, and retrieval.
Provides a deterministic, reproducible lifecycle for engineering knowledge.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.knowledge.chunking import SectionAwareChunker
from backend.knowledge.ingestion import DocumentIngestor
from backend.knowledge.models import (
    DocumentChunk,
    DocumentType,
    KnowledgeDocument,
    RetrievalResult,
)
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_index import LocalVectorIndex, VectorIndex

logger = logging.getLogger("nova.knowledge.knowledge_base")


class KnowledgeBase:
    """
    Unified entry point for NOVA Knowledge Base & RAG subsystem.
    """

    def __init__(
        self,
        index: Optional[VectorIndex] = None,
        chunker: Optional[SectionAwareChunker] = None,
    ) -> None:
        self.ingestor = DocumentIngestor()
        self.chunker = chunker or SectionAwareChunker()
        self.index = index if index is not None else LocalVectorIndex()
        self.retriever = KnowledgeRetriever(index=self.index)
        self._all_chunks: Dict[str, DocumentChunk] = {}

    @property
    def document_count(self) -> int:
        return self.ingestor.document_count

    @property
    def chunk_count(self) -> int:
        return len(self._all_chunks)

    def ingest_document(
        self,
        raw_content: str,
        document_id: str,
        title: str,
        source: str,
        document_type: Union[DocumentType, str] = DocumentType.OTHER,
        version: str = "v1.0.0",
        revision: str = "0",
        effective_date: Optional[str] = None,
        equipment_id: Optional[str] = None,
        equipment_type: Optional[str] = None,
        unit_area: Optional[str] = None,
        language: str = "en",
        authority: str = "Plant Engineering",
        source_uri: Optional[str] = None,
        source_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        """
        Ingest a document, chunk it, and update the vector index.
        """
        # 1. Ingest document
        doc = self.ingestor.ingest_document(
            raw_content=raw_content,
            document_id=document_id,
            title=title,
            source=source,
            document_type=document_type,
            version=version,
            revision=revision,
            effective_date=effective_date,
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            unit_area=unit_area,
            language=language,
            authority=authority,
            source_uri=source_uri,
            source_path=source_path,
            metadata=metadata,
        )

        # 2. Extract semantic chunks
        chunks = self.chunker.chunk_document(doc)

        # 3. Add to chunk registry and vector index
        for c in chunks:
            self._all_chunks[c.chunk_id] = c
        self.index.add_chunks(chunks)

        logger.info("Ingested and indexed document '%s' (%d chunks)", doc.document_id, len(chunks))
        return doc

    def ingest_file(
        self,
        file_path: Union[str, Path],
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        """
        Ingest a document from a file path, chunk it, and index it.
        """
        doc = self.ingestor.ingest_file(file_path, metadata_override=metadata_override)
        chunks = self.chunker.chunk_document(doc)

        for c in chunks:
            self._all_chunks[c.chunk_id] = c
        self.index.add_chunks(chunks)

        return doc

    def ingest_directory(
        self,
        directory_path: Union[str, Path],
        glob_pattern: str = "*.*",
    ) -> List[KnowledgeDocument]:
        """
        Batch ingest all matching files in a directory.
        """
        dir_p = Path(directory_path)
        if not dir_p.exists() or not dir_p.is_dir():
            logger.warning("Directory not found: %s", dir_p)
            return []

        ingested: List[KnowledgeDocument] = []
        for file_p in sorted(dir_p.glob(glob_pattern)):
            if file_p.is_file() and file_p.suffix.lower() in (".md", ".txt", ".json", ".yaml", ".yml"):
                try:
                    doc = self.ingest_file(file_p)
                    ingested.append(doc)
                except Exception as exc:
                    logger.warning("Failed to ingest %s: %s", file_p, exc)

        logger.info("Batch ingested %d documents from %s", len(ingested), dir_p)
        return ingested

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Query the knowledge base with optional metadata filtering.
        """
        return self.retriever.retrieve(query=query, top_k=top_k, filters=filters)

    def rebuild_index(self) -> int:
        """
        Deterministically rebuild the vector index from all ingested documents.
        """
        self._all_chunks.clear()
        all_chunks: List[DocumentChunk] = []

        for doc in self.ingestor.list_documents():
            chunks = self.chunker.chunk_document(doc)
            for c in chunks:
                self._all_chunks[c.chunk_id] = c
            all_chunks.extend(chunks)

        self.index.clear()
        count = self.index.add_chunks(all_chunks)
        logger.info("Deterministically rebuilt knowledge base: %d chunks across %d documents", count, self.ingestor.document_count)
        return count

    def get_document(self, document_id: str) -> Optional[KnowledgeDocument]:
        return self.ingestor.get_document(document_id)

    def list_documents(self) -> List[KnowledgeDocument]:
        return self.ingestor.list_documents()

    def clear(self) -> None:
        """Clear all documents and chunks from the knowledge base."""
        self.ingestor.clear()
        self._all_chunks.clear()
        self.index.clear()
