"""
backend/knowledge/models.py — Canonical Document, Chunk, and Evidence Models for NOVA.

Defines the core data contracts for the NOVA Knowledge Base & RAG layer:
- Document & metadata schemas with industrial taxonomies
- Section-aware chunk representations
- Canonical evidence models (DOCUMENT_EVIDENCE & MODEL_EVIDENCE)
- Source citation and provenance tracing
- Structured RAG context containers
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported industrial document categories for NOVA."""
    SOP = "SOP"
    OPERATING_MANUAL = "operating_manual"
    SAFETY_PROCEDURE = "safety_procedure"
    MAINTENANCE_MANUAL = "maintenance_manual"
    ENGINEERING_DOCUMENT = "engineering_document"
    PID = "P&ID"
    ALARM_PROCEDURE = "alarm_procedure"
    EMERGENCY_PROCEDURE = "emergency_procedure"
    INCIDENT_REPORT = "incident_report"
    INSPECTION_REPORT = "inspection_report"
    EQUIPMENT_DATASHEET = "equipment_datasheet"
    TRAINING_MATERIAL = "training_material"
    OTHER = "other"

    @classmethod
    def from_string(cls, val: str) -> "DocumentType":
        """Coerce raw strings or common aliases into canonical DocumentType."""
        normalized = val.strip().lower()
        mapping = {
            "sop": cls.SOP,
            "standard_operating_procedure": cls.SOP,
            "operating_manual": cls.OPERATING_MANUAL,
            "ops_manual": cls.OPERATING_MANUAL,
            "manual": cls.OPERATING_MANUAL,
            "safety_procedure": cls.SAFETY_PROCEDURE,
            "safety": cls.SAFETY_PROCEDURE,
            "maintenance_manual": cls.MAINTENANCE_MANUAL,
            "maintenance": cls.MAINTENANCE_MANUAL,
            "engineering_document": cls.ENGINEERING_DOCUMENT,
            "engineering": cls.ENGINEERING_DOCUMENT,
            "p&id": cls.PID,
            "pid": cls.PID,
            "p_and_id": cls.PID,
            "alarm_procedure": cls.ALARM_PROCEDURE,
            "alarm": cls.ALARM_PROCEDURE,
            "emergency_procedure": cls.EMERGENCY_PROCEDURE,
            "emergency": cls.EMERGENCY_PROCEDURE,
            "incident_report": cls.INCIDENT_REPORT,
            "incident": cls.INCIDENT_REPORT,
            "inspection_report": cls.INSPECTION_REPORT,
            "inspection": cls.INSPECTION_REPORT,
            "equipment_datasheet": cls.EQUIPMENT_DATASHEET,
            "datasheet": cls.EQUIPMENT_DATASHEET,
            "training_material": cls.TRAINING_MATERIAL,
            "training": cls.TRAINING_MATERIAL,
            "other": cls.OTHER,
        }
        if normalized in mapping:
            return mapping[normalized]
        for item in cls:
            if item.value.lower() == normalized:
                return item
        return cls.OTHER


class RetrievalStatus(str, Enum):
    """Status outcomes for knowledge retrieval operations."""
    OK = "OK"
    NO_KNOWLEDGE_AVAILABLE = "NO_KNOWLEDGE_AVAILABLE"
    NO_RELEVANT_EVIDENCE = "NO_RELEVANT_EVIDENCE"
    KNOWLEDGE_BASE_UNAVAILABLE = "KNOWLEDGE_BASE_UNAVAILABLE"
    INVALID_QUERY = "INVALID_QUERY"


class EvidenceType(str, Enum):
    """Types of evidence supported in NOVA."""
    DOCUMENT_EVIDENCE = "DOCUMENT_EVIDENCE"
    MODEL_EVIDENCE = "MODEL_EVIDENCE"


class KnowledgeDocument(BaseModel):
    """
    Canonical representation of an engineering document in the NOVA Knowledge Base.
    Preserves comprehensive industrial metadata and provenance.
    """
    document_id: str = Field(..., description="Unique, deterministic identifier for the document")
    title: str = Field(..., description="Human-readable title of the document")
    document_type: DocumentType = Field(default=DocumentType.OTHER, description="Category of the document")
    source: str = Field(..., description="Originating authority or system (e.g., Plant Operations)")
    source_uri: Optional[str] = Field(default=None, description="Original URI or path of the document")
    source_path: Optional[str] = Field(default=None, description="Filesystem path if ingested from local file")
    version: str = Field(default="v1.0.0", description="Document version string")
    revision: str = Field(default="0", description="Document revision number or code")
    effective_date: Optional[str] = Field(default=None, description="ISO-8601 effective date")
    equipment_id: Optional[str] = Field(default=None, description="Target equipment tag (e.g. F-201A)")
    equipment_type: Optional[str] = Field(default=None, description="Target equipment type (e.g. furnace)")
    unit_area: Optional[str] = Field(default=None, description="Plant unit or area (e.g. UNIT-CRACK-01)")
    language: str = Field(default="en", description="Language code")
    authority: str = Field(default="Plant Engineering", description="Issuing standard body or department")
    ingested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="UTC timestamp of ingestion",
    )
    content_hash: str = Field(..., description="SHA-256 hash of normalized content")
    raw_content: str = Field(..., description="Original raw document content")
    normalized_content: str = Field(..., description="Cleaned, normalized text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata key-values")


class DocumentChunk(BaseModel):
    """
    Semantic, section-aware chunk derived from a KnowledgeDocument.
    """
    chunk_id: str = Field(..., description="Deterministic chunk identifier: chunk_<doc_id>_<idx>")
    document_id: str = Field(..., description="Parent document identifier")
    text: str = Field(..., description="Normalized text content of this chunk")
    section: str = Field(default="", description="Section title or heading context")
    page_reference: Optional[str] = Field(default=None, description="Page or structural reference")
    chunk_index: int = Field(default=0, description="0-based sequence index within parent document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Inherited and chunk-specific metadata")
    content_hash: str = Field(..., description="SHA-256 hash of chunk text")


class Citation(BaseModel):
    """
    Explicit citation linking an evidence excerpt back to its authoritative source.
    """
    document_id: str = Field(..., description="Authoritative document identifier")
    chunk_id: str = Field(..., description="Specific chunk identifier")
    source: str = Field(..., description="Source organization or authority")
    document_title: str = Field(..., description="Title of the source document")
    section: str = Field(default="", description="Section where excerpt appears")
    page_reference: Optional[str] = Field(default=None, description="Page or subsection reference")
    content_hash: str = Field(..., description="SHA-256 hash of the cited chunk")
    version: Optional[str] = Field(default=None, description="Version of the source document")


class RetrievedChunk(BaseModel):
    """
    Ranked search result from the knowledge retriever with full source attribution.
    """
    chunk_id: str
    document_id: str
    text: str
    score: float = Field(..., description="Relevance similarity score (0.0 - 1.0)")
    rank: int = Field(..., description="Rank in retrieval result (1-indexed)")
    source: str
    document_title: str
    section: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    citation: Citation


class RetrievalResult(BaseModel):
    """
    Structured outcome of a retrieval query.
    """
    query: str
    status: RetrievalStatus
    results: List[RetrievedChunk] = Field(default_factory=list)
    total_found: int = 0
    message: str = ""
    applied_filters: Dict[str, Any] = Field(default_factory=dict)


class CanonicalEvidence(BaseModel):
    """
    Unified evidence container used across NOVA.
    Can represent authoritative DOCUMENT_EVIDENCE or ML MODEL_EVIDENCE.
    """
    evidence_id: str = Field(..., description="Unique evidence identifier")
    evidence_type: EvidenceType = Field(..., description="DOCUMENT_EVIDENCE or MODEL_EVIDENCE")
    source_type: str = Field(..., description="Document type, ML model name, etc.")
    source_id: str = Field(..., description="Document ID or model identifier")
    source_title: str = Field(..., description="Document title or model display name")
    excerpt: str = Field(..., description="Extracted text or prediction summary")
    relevance_score: float = Field(default=1.0, description="Relevance or confidence score [0.0, 1.0]")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp of evidence creation",
    )
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Detailed audit provenance")
    model_version: Optional[str] = Field(default=None, description="Version of model or document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Domain metadata")
    citation: Optional[Citation] = Field(default=None, description="Source citation if document evidence")


class RAGContext(BaseModel):
    """
    Structured RAG context package formatted for downstream reasoning components.
    Preserves grounded citations, ranking, and full provenance without fabricating data.
    """
    query: str
    status: RetrievalStatus
    evidence_items: List[CanonicalEvidence] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    formatted_context: str = Field(default="", description="Pre-assembled context text")
    metadata: Dict[str, Any] = Field(default_factory=dict)
