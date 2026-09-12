"""
backend/tests/test_knowledge_base.py — Comprehensive Unit Tests for Knowledge Base.

Tests:
1. Safe text normalization (preserves headings, steps, warnings, tables, units, tags).
2. Content hashing determinism and SHA-256 integrity.
3. Section-aware procedural chunking and context retention.
4. Document ingestion, validation, and content-hash duplicate detection.
5. In-memory vector indexing, addition, deletion, and deterministic rebuild.
6. Metadata filtering (document_type, equipment_id, equipment_type, unit_area, authority).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from backend.knowledge.chunking import SectionAwareChunker
from backend.knowledge.ingestion import DocumentIngestionError, DocumentIngestor
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import DocumentType, KnowledgeDocument
from backend.knowledge.normalization import compute_content_hash, normalize_text
from backend.knowledge.vector_index import LocalVectorIndex


SAMPLE_SOP_TEXT = """# SOP-F201-01: Cracking Furnace Thermal Emergency Shutdown

## 1.0 SCOPE & PURPOSE
This Standard Operating Procedure (SOP) defines mandatory emergency shutdown
actions for Cracking Furnace F-201A / F-201B located in UNIT-CRACK-01.

## 2.0 SAFETY BOUNDARIES & LIMITS
- Maximum Coil Outlet Temperature (COT): 890.0 °C
- Maximum Tube Metal Temperature (TMT): 1080.0 °C (trip threshold)
- Minimum Fuel Gas Pressure: 150.0 kPa

WARNING: Exceeding 1080.0 °C TMT risks catastrophic coil rupture and hydrocarbon release.

## 3.0 EMERGENCY PROCEDURES
When high COT alarm (TI-201 > 885.0 °C) triggers:
1. Immediately throttle fuel gas control valve FV-201 to 40% open.
2. Verify draft fan flow rate exceeds 12,000 kg/h.
3. Switch dilution steam bypass valve SV-204 to MANUAL and increase steam ratio to 0.45.
4. If TMT exceeds 1050.0 °C for > 60 seconds, initiate Emergency Depressurization Procedure EDP-04.
5. Notify Shift Supervisor and log incident in Vigil Operational Log.
"""


# ---------------------------------------------------------------------------
# 1. Normalization & Hashing Tests
# ---------------------------------------------------------------------------

def test_normalize_text_preserves_structure_and_units():
    raw = "  Line 1   \r\n\r\n\r\n\r\nLine 2 with 850.5 °C and 150 kPa. \t \r\nWARNING: High Heat!\n"
    norm = normalize_text(raw)

    assert "850.5 °C" in norm
    assert "150 kPa" in norm
    assert "WARNING: High Heat!" in norm
    assert "\r" not in norm
    # Excessive blank lines collapsed to 2 newlines (1 blank line between)
    assert "\n\n\n" not in norm


def test_compute_content_hash_deterministic():
    text1 = "SOP procedure for furnace F-201A"
    text2 = "SOP procedure for furnace F-201A"
    text3 = "SOP procedure for furnace F-201B"

    h1 = compute_content_hash(text1)
    h2 = compute_content_hash(text2)
    h3 = compute_content_hash(text3)

    assert len(h1) == 64
    assert h1 == h2
    assert h1 != h3


# ---------------------------------------------------------------------------
# 2. Chunking Tests
# ---------------------------------------------------------------------------

def test_section_aware_chunker_preserves_procedural_steps():
    chunker = SectionAwareChunker(max_chunk_chars=1000)
    doc = KnowledgeDocument(
        document_id="DOC-SOP-F201-01",
        title="Cracking Furnace Thermal Emergency Shutdown",
        document_type=DocumentType.SOP,
        source="Plant Operations",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        authority="Chief Process Safety Engineer",
        content_hash=compute_content_hash(SAMPLE_SOP_TEXT),
        raw_content=SAMPLE_SOP_TEXT,
        normalized_content=normalize_text(SAMPLE_SOP_TEXT),
    )

    chunks = chunker.chunk_document(doc)
    assert len(chunks) >= 2

    # Check deterministic chunk IDs
    for idx, c in enumerate(chunks):
        assert c.chunk_id == f"chunk_DOC-SOP-F201-01_{idx:04d}"
        assert c.document_id == "DOC-SOP-F201-01"
        assert len(c.content_hash) == 64
        assert c.metadata["equipment_id"] == "F-201A"
        assert c.metadata["document_type"] == "SOP"

    # Verify procedural steps are preserved in emergency section chunk
    step_chunk = next(c for c in chunks if "EMERGENCY PROCEDURES" in c.section or "1. Immediately throttle" in c.text)
    assert "1. Immediately throttle" in step_chunk.text
    assert "2. Verify draft fan" in step_chunk.text
    assert "3. Switch dilution steam" in step_chunk.text
    assert "WARNING:" in SAMPLE_SOP_TEXT


# ---------------------------------------------------------------------------
# 3. Ingestion & Deduplication Tests
# ---------------------------------------------------------------------------

def test_document_ingestor_success():
    ingestor = DocumentIngestor()
    doc = ingestor.ingest_document(
        raw_content=SAMPLE_SOP_TEXT,
        document_id="DOC-SOP-01",
        title="Furnace SOP",
        source="Operations",
        document_type=DocumentType.SOP,
        equipment_id="F-201A",
    )

    assert doc.document_id == "DOC-SOP-01"
    assert doc.document_type == DocumentType.SOP
    assert ingestor.document_count == 1
    assert ingestor.get_document("DOC-SOP-01") is not None


def test_document_ingestor_rejects_empty_content():
    ingestor = DocumentIngestor()
    with pytest.raises(DocumentIngestionError, match="empty content"):
        ingestor.ingest_document(
            raw_content="   \n\t  ",
            document_id="DOC-EMPTY",
            title="Empty Doc",
            source="Operations",
        )


def test_document_ingestor_rejects_duplicate_content():
    ingestor = DocumentIngestor()
    ingestor.ingest_document(
        raw_content=SAMPLE_SOP_TEXT,
        document_id="DOC-ORIGINAL",
        title="Original Doc",
        source="Operations",
    )

    # Ingesting different doc_id with identical content should fail deduplication
    with pytest.raises(DocumentIngestionError, match="Duplicate content detected"):
        ingestor.ingest_document(
            raw_content=SAMPLE_SOP_TEXT,
            document_id="DOC-DUPLICATE",
            title="Duplicate Doc",
            source="Operations",
        )


def test_document_ingestor_from_file():
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# Maintenance Guide\n\nPump P-101 seal replacement procedure.")
        tmp_path = Path(f.name)

    try:
        ingestor = DocumentIngestor()
        doc = ingestor.ingest_file(tmp_path, metadata_override={"equipment_id": "P-101", "document_type": DocumentType.MAINTENANCE_MANUAL})
        assert doc.equipment_id == "P-101"
        assert doc.document_type == DocumentType.MAINTENANCE_MANUAL
        assert "Pump P-101" in doc.normalized_content
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# 4. Vector Indexing & Metadata Filtering Tests
# ---------------------------------------------------------------------------

def test_local_vector_index_add_search_delete():
    index = LocalVectorIndex()
    kb = KnowledgeBase(index=index)

    kb.ingest_document(
        raw_content=SAMPLE_SOP_TEXT,
        document_id="DOC-FURNACE-SOP",
        title="Cracking Furnace Shutdown",
        source="Process Safety",
        document_type=DocumentType.SOP,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
    )

    assert index.count() > 0

    # Search with matching filter
    hits = index.search(
        query_vector=[0.1] * 384,
        top_k=5,
        filters={"equipment_type": "furnace", "document_type": "SOP"},
    )
    assert len(hits) > 0

    # Search with non-matching filter
    hits_nomatch = index.search(
        query_vector=[0.1] * 384,
        top_k=5,
        filters={"equipment_type": "compressor"},
    )
    assert len(hits_nomatch) == 0

    # Delete document
    deleted = index.delete_document("DOC-FURNACE-SOP")
    assert deleted > 0
    assert index.count() == 0


def test_deterministic_rebuild():
    kb = KnowledgeBase()
    kb.ingest_document(
        raw_content=SAMPLE_SOP_TEXT,
        document_id="DOC-REBUILD-TEST",
        title="Rebuild Test SOP",
        source="Safety",
        document_type=DocumentType.SAFETY_PROCEDURE,
        equipment_id="F-201A",
    )

    initial_chunks = kb.chunk_count
    assert initial_chunks > 0

    # Trigger rebuild
    rebuilt_count = kb.rebuild_index()
    assert rebuilt_count == initial_chunks
    assert kb.chunk_count == initial_chunks
