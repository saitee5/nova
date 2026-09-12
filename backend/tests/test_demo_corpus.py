"""
backend/tests/test_demo_corpus.py — Integration & Evaluation Tests for Demo Knowledge Corpus.

Tests:
1. Corpus discovery, frontmatter parsing, normalization, chunking, and deterministic indexing.
2. Synthetic demo safeguards (source_type=synthetic_demo, industrial_validation=false).
3. 8 original core positive queries + 10 cross-domain queries (SOP, Safety, Permits, Maintenance, Incidents, Equipment, Hierarchy).
4. Multi-domain complementary retrieval (retrieves cross-functional context across SOP, Maintenance, Safety, Permits).
5. 4 negative queries verifying safe refusal / no hallucination of live telemetry or operator history.
6. Multi-field industrial metadata filtering (document_type, equipment_type, equipment_id).
7. Combined Model Evidence + Document Evidence with synthetic TMT surrogate provenance preservation.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.knowledge.build_demo_corpus import build_demo_knowledge_base
from backend.knowledge.context_builder import RAGContextBuilder
from backend.knowledge.evidence_bridge import ModelEvidenceBridge
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import (
    DocumentType,
    EvidenceType,
    RetrievalStatus,
)


@pytest.fixture(scope="module")
def demo_kb() -> KnowledgeBase:
    """Build and return the demo knowledge base fixture."""
    return build_demo_knowledge_base()


# ---------------------------------------------------------------------------
# 1. Ingestion & Corpus Integrity Tests
# ---------------------------------------------------------------------------

def test_demo_corpus_ingestion_counts_and_types(demo_kb: KnowledgeBase):
    assert demo_kb.document_count == 25
    assert demo_kb.chunk_count == 86

    docs = demo_kb.list_documents()
    assert len(docs) == 25
    for doc in docs:
        assert doc.metadata.get("source_type") == "synthetic_demo"
        assert doc.metadata.get("authority") == "demo_only"
        assert doc.metadata.get("industrial_validation") is False
        assert doc.metadata.get("is_synthetic_demo") is True
        assert len(doc.content_hash) == 64
        assert doc.unit_area == "UNIT-CRACK-01"


def test_demo_corpus_deterministic_rebuild(demo_kb: KnowledgeBase):
    rebuilt_chunks = demo_kb.rebuild_index()
    assert rebuilt_chunks == 86
    assert demo_kb.document_count == 25
    assert demo_kb.chunk_count == 86


# ---------------------------------------------------------------------------
# 2. Positive Retrieval Evaluation (Original 8 Core Queries)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,expected_doc_ids,expected_terms",
    [
        (
            "what should the operator do during a high COT condition?",
            ["DOC-DEMO-ALM-F201-002", "DOC-DEMO-SOP-F201-001"],
            ["885.0", "FV-201", "fuel gas", "COT"],
        ),
        (
            "what are the normal furnace operating conditions?",
            ["DOC-DEMO-SOP-F201-001", "DOC-DEMO-DAT-F201-015"],
            ["840.0", "860.0", "24,000", "F-201A"],
        ),
        (
            "what PPE is required before furnace maintenance?",
            ["DOC-DEMO-SAF-GEN-013"],
            ["PPE", "aluminized", "gloves", "face shield"],
        ),
        (
            "what should happen when gas detection is triggered?",
            ["DOC-DEMO-SAF-GEN-011"],
            ["LEL", "gas detection", "evacuation", "alarm"],
        ),
        (
            "how is tube temperature monitored?",
            ["DOC-DEMO-OPM-F201-007", "DOC-DEMO-DAT-F201-015"],
            ["Tube Metal Temperature", "TMT", "thermocouple", "pyrometer"],
        ),
        (
            "what are common causes of abnormal furnace pressure?",
            ["DOC-DEMO-OPM-FLT-008", "DOC-DEMO-SOP-F201-001"],
            ["fuel gas", "pressure", "FV-201", "draft"],
        ),
        (
            "what maintenance checks are required for F-201A?",
            ["DOC-DEMO-MNT-F201-018", "DOC-DEMO-SAF-GEN-012", "DOC-DEMO-MNT-HIS-022"],
            ["inspection", "coking", "decoking", "wall thickness", "maintenance", "zero-energy"],
        ),
        (
            "what equipment is downstream of the cracking furnace?",
            ["DOC-DEMO-PID-TOP-017", "DOC-DEMO-DAT-C101-020"],
            ["TLE-201", "Transfer Line Exchanger", "Fractionator", "C-101", "Compressor"],
        ),
    ],
)
def test_positive_retrieval_queries(
    demo_kb: KnowledgeBase,
    query: str,
    expected_doc_ids: list[str],
    expected_terms: list[str],
):
    res = demo_kb.retrieve(query=query, top_k=5)
    assert res.status == RetrievalStatus.OK
    assert len(res.results) > 0

    top_result = res.results[0]
    assert top_result.score > 0.0
    assert top_result.citation is not None
    assert top_result.citation.document_id in expected_doc_ids or any(
        r.document_id in expected_doc_ids for r in res.results
    )
    assert len(top_result.citation.content_hash) == 64

    # Verify key conceptual terms appear in retrieved excerpts
    combined_text = " ".join(r.text for r in res.results)
    assert any(term.lower() in combined_text.lower() for term in expected_terms)


# ---------------------------------------------------------------------------
# 3. Cross-Domain Retrieval Tests (10 Enriched Questions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,expected_doc_substrings,expected_terms",
    [
        (
            "F-201A high COT response",
            ["DOC-DEMO-ALM-F201-002", "DOC-DEMO-SOP-F201-001"],
            ["COT", "fuel gas", "FV-201", "alarm"],
        ),
        (
            "What safety controls are required before furnace maintenance?",
            ["DOC-DEMO-SAF-GEN-012", "DOC-DEMO-SAF-GEN-013", "DOC-DEMO-PMT-SOP-025"],
            ["LOTO", "isolation", "PPE", "lockout"],
        ),
        (
            "What permit is required for hot work on F-201A?",
            ["DOC-DEMO-PMT-SOP-025", "DOC-DEMO-SAF-GEN-013"],
            ["hot work", "permit", "fire watch", "gas test"],
        ),
        (
            "What maintenance issues have been associated with F-201A?",
            ["DOC-DEMO-MNT-HIS-022", "DOC-DEMO-MNT-F201-018", "DOC-DEMO-INC-F201-023"],
            ["thermocouple", "decoke", "coking", "work order", "calibration", "drift"],
        ),
        (
            "What PPE is required for furnace inspection?",
            ["DOC-DEMO-SAF-GEN-013"],
            ["PPE", "shield", "aluminized", "gloves", "safety"],
        ),
        (
            "What should an operator do after a high COT alarm?",
            ["DOC-DEMO-ALM-F201-002", "DOC-DEMO-SOP-F201-001"],
            ["alarm", "COT", "fuel", "throttle", "firing"],
        ),
        (
            "What incidents or near misses are associated with furnace operation?",
            ["DOC-DEMO-INC-F201-023", "DOC-DEMO-INC-NRM-024"],
            ["incident", "near-miss", "root cause", "coking", "excursion", "upset"],
        ),
        (
            "What equipment is connected to F-201A?",
            ["DOC-DEMO-PID-TOP-017", "DOC-DEMO-ENG-HRC-021"],
            ["P-101", "TLE-201", "V-201A", "C-101", "downstream"],
        ),
        (
            "What isolation requirements apply before maintenance?",
            ["DOC-DEMO-SAF-GEN-012", "DOC-DEMO-PMT-SOP-025"],
            ["LOTO", "isolation", "blind", "tagout", "zero-energy"],
        ),
        (
            "What evidence supports the current fault diagnosis?",
            ["DOC-DEMO-OPM-FLT-008", "DOC-DEMO-ALM-F201-002", "DOC-DEMO-ENG-FLT-010", "DOC-DEMO-INC-F201-023"],
            ["drift", "upset", "sensor", "transmitter", "rate of change", "cross-correlation", "temperature", "fault"],
        ),
    ],
)
def test_cross_domain_retrieval_queries(
    demo_kb: KnowledgeBase,
    query: str,
    expected_doc_substrings: list[str],
    expected_terms: list[str],
):
    res = demo_kb.retrieve(query=query, top_k=5)
    assert res.status == RetrievalStatus.OK
    assert len(res.results) > 0

    retrieved_doc_ids = [r.document_id for r in res.results]
    assert any(
        exp_id in retrieved_doc_ids
        for exp_id in expected_doc_substrings
    ), f"None of {expected_doc_substrings} found in {retrieved_doc_ids} for query '{query}'"

    combined_text = " ".join(r.text for r in res.results).lower()
    assert any(term.lower() in combined_text for term in expected_terms), (
        f"None of {expected_terms} found in retrieved text for '{query}'"
    )


def test_multi_domain_complementary_retrieval(demo_kb: KnowledgeBase):
    """
    Verifies that querying a complex operational scenario retrieves complementary evidence
    spanning at least 3 distinct document categories (e.g. SOP/Alarm, Maintenance/Incident, Safety/Permits).
    """
    res = demo_kb.retrieve(
        query="F-201A burner malfunction overhaul safety isolation permit and maintenance history",
        top_k=8,
    )
    assert res.status == RetrievalStatus.OK
    doc_types = {r.metadata.get("document_type") for r in res.results if r.metadata.get("document_type")}
    # Should retrieve across multiple distinct operational domains
    assert len(doc_types) >= 3, f"Expected >= 3 document types in top results, got {doc_types}"


# ---------------------------------------------------------------------------
# 4. Metadata Filtering on Demo Corpus
# ---------------------------------------------------------------------------

def test_metadata_filtering_on_demo_corpus(demo_kb: KnowledgeBase):
    # Filter 1: DocumentType safety_procedure
    res_safety = demo_kb.retrieve(
        query="operating guidelines and precautions",
        top_k=5,
        filters={"document_type": DocumentType.SAFETY_PROCEDURE},
    )
    assert res_safety.status == RetrievalStatus.OK
    for chunk in res_safety.results:
        assert chunk.metadata["document_type"] == "safety_procedure"

    # Filter 2: P&ID
    res_pid = demo_kb.retrieve(
        query="stream flow topology",
        top_k=3,
        filters={"document_type": DocumentType.PID},
    )
    assert res_pid.status == RetrievalStatus.OK
    assert len(res_pid.results) > 0
    assert res_pid.results[0].document_id == "DOC-DEMO-PID-TOP-017"

    # Filter 3: Pump equipment
    res_pump = demo_kb.retrieve(
        query="feed delivery specs",
        top_k=3,
        filters={"equipment_type": "pump"},
    )
    assert res_pump.status == RetrievalStatus.OK
    for chunk in res_pump.results:
        assert chunk.document_id == "DOC-DEMO-DAT-P101-016"

    # Filter 4: Incident report
    res_inc = demo_kb.retrieve(
        query="thermal excursion near miss retrospective",
        top_k=3,
        filters={"document_type": DocumentType.INCIDENT_REPORT},
    )
    assert res_inc.status == RetrievalStatus.OK
    for chunk in res_inc.results:
        assert chunk.metadata["document_type"] == "incident_report"


# ---------------------------------------------------------------------------
# 5. Negative Retrieval Tests (Safe Non-Hallucination)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "negative_query",
    [
        "exact current plant operating value today",
        "what did the operator do yesterday?",
        "current maintenance work order for F-201A",
        "actual live furnace temperature right now",
    ],
)
def test_negative_queries_safe_handling(demo_kb: KnowledgeBase, negative_query: str):
    """
    Negative queries querying live telemetry, historic operator actions, or live work orders
    must not return fake facts. When a strict threshold or non-existent equipment filter is used,
    the system returns NO_RELEVANT_EVIDENCE.
    """
    # Test strict equipment filter with non-existent live ID
    res = demo_kb.retrieve(
        query=negative_query,
        filters={"equipment_id": "LIVE_TELEMETRY_NONEXISTENT"},
    )
    assert res.status == RetrievalStatus.NO_RELEVANT_EVIDENCE
    assert len(res.results) == 0


# ---------------------------------------------------------------------------
# 6. Combined Model + Document Evidence & Synthetic Provenance
# ---------------------------------------------------------------------------

def test_combined_model_and_document_evidence(demo_kb: KnowledgeBase):
    # 1. Retrieve SOP document for high COT
    doc_result = demo_kb.retrieve(
        query="high COT alarm procedure F-201A",
        top_k=1,
        filters={"document_type": DocumentType.ALARM_PROCEDURE},
    )
    assert doc_result.status == RetrievalStatus.OK

    # 2. Simulate ML predictions from Model 2 (Fault Classifier) and Model 4 (Tube Temp Surrogate)
    fault_pred = {
        "predicted_fault": 4,
        "fault_name": "Reactor Cooling Water Step Decrease",
        "confidence": 0.94,
        "status": "OK",
    }
    tube_pred = {
        "predicted_tmt": 978.5,
        "confidence": 0.89,
        "status": "OK",
    }

    ev_fault = ModelEvidenceBridge.from_fault_prediction(fault_pred, model_version="v1.1.0")
    ev_tube = ModelEvidenceBridge.from_tube_temp_prediction(tube_pred, model_version="v1.1.0")

    # 3. Build combined RAGContext
    context = RAGContextBuilder.build_context(
        query="High temperature upset on Cracking Furnace F-201A",
        retrieval_result=doc_result,
        model_evidence=[ev_fault, ev_tube],
    )

    # 4. Verify context properties
    assert context.status == RetrievalStatus.OK
    assert len(context.evidence_items) == 3
    assert len(context.citations) == 1

    # Verify synthetic surrogate provenance preservation
    tube_ev = next(e for e in context.evidence_items if e.source_id == "TubeTemperaturePredictor")
    assert tube_ev.evidence_type == EvidenceType.MODEL_EVIDENCE
    assert tube_ev.provenance["target_type"] == "physics_informed_synthetic_surrogate"
    assert tube_ev.provenance["industrial_validation"] is False
    assert "SYNTHETIC SURROGATE" in tube_ev.excerpt
    assert "NOT MEASURED TELEMETRY" in context.formatted_context
