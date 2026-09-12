"""
backend/knowledge/ingestion.py — Deterministic Document Ingestion Pipeline.

Responsible for ingesting, validating, normalizing, and deduplicating
engineering documents into canonical KnowledgeDocument objects.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml

from backend.knowledge.models import DocumentType, KnowledgeDocument
from backend.knowledge.normalization import compute_content_hash, normalize_text

logger = logging.getLogger("nova.knowledge.ingestion")


class DocumentIngestionError(Exception):
    """Raised when document ingestion fails due to validation or formatting issues."""
    pass


class DocumentIngestor:
    """
    Deterministic ingestion pipeline for NOVA Knowledge Base.
    Enforces validation, normalization, and deduplication by content hash.
    """

    def __init__(self) -> None:
        # Track ingested document IDs and content hashes for deduplication
        self._seen_doc_ids: Set[str] = set()
        self._seen_content_hashes: Set[str] = set()
        self._ingested_documents: Dict[str, KnowledgeDocument] = {}

    @property
    def document_count(self) -> int:
        return len(self._ingested_documents)

    def get_document(self, document_id: str) -> Optional[KnowledgeDocument]:
        return self._ingested_documents.get(document_id)

    def list_documents(self) -> List[KnowledgeDocument]:
        return list(self._ingested_documents.values())

    def clear(self) -> None:
        """Reset the ingestion registry."""
        self._seen_doc_ids.clear()
        self._seen_content_hashes.clear()
        self._ingested_documents.clear()

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
        allow_duplicate_hash: bool = False,
    ) -> KnowledgeDocument:
        """
        Ingest, normalize, validate, and register a document.

        Raises:
            DocumentIngestionError: If the document is empty, missing mandatory fields,
                                   or is a duplicate when allow_duplicate_hash is False.
        """
        # 1. Validation
        if not document_id or not document_id.strip():
            raise DocumentIngestionError("Document ID cannot be empty.")
        if not title or not title.strip():
            raise DocumentIngestionError("Document title cannot be empty.")
        if not source or not source.strip():
            raise DocumentIngestionError("Document source cannot be empty.")
        if not raw_content or not raw_content.strip():
            raise DocumentIngestionError(f"Document '{document_id}' has empty content.")

        clean_doc_id = document_id.strip()

        # 2. Text normalization & content hash
        normalized_content = normalize_text(raw_content)
        if not normalized_content:
            raise DocumentIngestionError(f"Document '{document_id}' content is empty after normalization.")

        content_hash = compute_content_hash(normalized_content)

        # 3. Deduplication checks
        if not allow_duplicate_hash and content_hash in self._seen_content_hashes:
            # Check if this exact doc ID was already ingested
            if clean_doc_id in self._ingested_documents:
                logger.info("Document '%s' already ingested with matching content hash.", clean_doc_id)
                return self._ingested_documents[clean_doc_id]
            logger.warning("Duplicate content hash detected for document '%s' — rejecting duplicate.", clean_doc_id)
            raise DocumentIngestionError(
                f"Duplicate content detected: hash {content_hash[:12]} already exists in knowledge base."
            )

        # 4. Resolve DocumentType
        if isinstance(document_type, str):
            resolved_type = DocumentType.from_string(document_type)
        else:
            resolved_type = document_type

        # 5. Construct canonical KnowledgeDocument
        doc = KnowledgeDocument(
            document_id=clean_doc_id,
            title=title.strip(),
            document_type=resolved_type,
            source=source.strip(),
            source_uri=source_uri,
            source_path=source_path,
            version=version,
            revision=revision,
            effective_date=effective_date,
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            unit_area=unit_area,
            language=language,
            authority=authority,
            content_hash=content_hash,
            raw_content=raw_content,
            normalized_content=normalized_content,
            metadata=metadata or {},
        )

        # 6. Register
        self._seen_doc_ids.add(clean_doc_id)
        self._seen_content_hashes.add(content_hash)
        self._ingested_documents[clean_doc_id] = doc

        logger.info("Successfully ingested document '%s' (%s, hash=%s)", doc.document_id, doc.document_type.value, content_hash[:8])
        return doc

    def ingest_file(
        self,
        file_path: Union[str, Path],
        metadata_override: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        """
        Ingest a file (.md, .txt, .json, .yaml) from disk.
        """
        path = Path(file_path)
        if not path.exists():
            raise DocumentIngestionError(f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise DocumentIngestionError(f"Failed to read file '{path}': {exc}")

        override = metadata_override or {}
        stem = path.stem

        # Try to parse frontmatter or structured json/yaml if present
        doc_id = override.get("document_id") or f"DOC-{stem.upper()}"
        title = override.get("title") or stem.replace("_", " ").title()
        source = override.get("source") or "Plant Documentation"
        doc_type = override.get("document_type") or DocumentType.OTHER

        # If file is JSON, see if it has standard fields
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    doc_id = data.get("document_id", doc_id)
                    title = data.get("title", title)
                    source = data.get("source", source)
                    doc_type = data.get("document_type", doc_type)
                    raw_text = data.get("content") or data.get("text") or content
                else:
                    raw_text = content
            except Exception:
                raw_text = content
        else:
            raw_text = content

        return self.ingest_document(
            raw_content=raw_text,
            document_id=doc_id,
            title=title,
            source=source,
            document_type=doc_type,
            version=override.get("version", "v1.0.0"),
            revision=override.get("revision", "0"),
            effective_date=override.get("effective_date"),
            equipment_id=override.get("equipment_id"),
            equipment_type=override.get("equipment_type"),
            unit_area=override.get("unit_area"),
            language=override.get("language", "en"),
            authority=override.get("authority", "Plant Engineering"),
            source_path=str(path.resolve()),
            metadata=override.get("metadata", {}),
        )
