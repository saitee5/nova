"""
backend/tests/test_rag_pipeline.py — Integration & Contract Tests for RAG Pipeline.

Tests:
1. End-to-end retrieval with source traceability and citations.
2. Safe failure modes (NO_KNOWLEDGE_AVAILABLE, NO_RELEVANT_EVIDENCE, INVALID_QUERY, KNOWLEDGE_BASE_UNAVAILABLE).
3. Model Evidence Bridge across all 4 ML models.
4. TubeTemperaturePredictor synthetic surrogate provenance and limitations contract.
5. RAG Context Builder and citation preservation.
6. RAGKnowledgeProvider interface compliance.
"""

from __future__ import annotations

import pytest

from backend.knowledge.context_builder import RAGContextBuilder
from backend.knowledge.evidence_bridge import ModelEvidenceBridge
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import (
    DocumentType,
    EvidenceType,
    RetrievalStatus,
)
from backend.knowledge.provider import RAGKnowledgeProvider
from backend.knowledge.retriever import KnowledgeRetriever


SAMPLE_DOC_1 = """# SOP-F201-01: Cracking Furnace High COT Alarm Response
## 1.0 General
Furnace F-201A operates in UNIT-CRACK-01 with maximum COT limit of 890.0 °C.

## 2.0 Response Steps
1. Reduce fuel gas pressure to 160 kPa.
2. Increase steam dilution flow.
3. Check tube skin thermocouples for local hotspotting.
"""

SAMPLE_DOC_2 = """# OPM-P101-02: Centrifugal Pump Cavitation Mitigation
## 1.0 General
Pump P-101 in UNIT-CRACK-01 transfer service.

## 2.0 Symptoms & Action
Vibration above 4.5 mm/s indicates cavitation.
1. Throttle discharge valve.
2. Check suction strainer differential pressure.
"""


@pytest.fixture
def populated_kb() -> KnowledgeBase:
    kb = KnowledgeBase()
    kb.ingest_document(
        raw_content=SAMPLE_DOC_1,
        document_id="DOC-SOP-F201",
        title="Cracking Furnace High COT Alarm Response",
        source="Furnace Operations Team",
        document_type=DocumentType.SOP,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        authority="Lead Furnace Engineer",
        version="v2.0",
    )
    kb.ingest_document(
        raw_content=SAMPLE_DOC_2,
        document_id="DOC-OPM-P101",
        title="Centrifugal Pump Cavitation Mitigation",
        source="Machinery Reliability Group",
        document_type=DocumentType.OPERATING_MANUAL,
        equipment_id="P-101",
        equipment_type="pump",
        unit_area="UNIT-CRACK-01",
        authority="Rotating Equipment Lead",
        version="v1.1",
    )
    return kb


# ---------------------------------------------------------------------------
# 1. Retrieval & Citation Traceability Tests
# ---------------------------------------------------------------------------

def test_retrieval_returns_traceable_attributed_chunks(populated_kb: KnowledgeBase):
    res = populated_kb.retrieve(
        query="furnace COT high alarm response",
        top_k=2,
    )

    assert res.status == RetrievalStatus.OK
    assert len(res.results) > 0

    top_chunk = res.results[0]
    assert top_chunk.rank == 1
    assert top_chunk.score > 0.0
    assert top_chunk.document_id in ("DOC-SOP-F201", "DOC-OPM-P101")
    assert top_chunk.citation is not None
    assert top_chunk.citation.document_id == top_chunk.document_id
    assert top_chunk.citation.chunk_id == top_chunk.chunk_id
    assert len(top_chunk.citation.content_hash) == 64
    assert top_chunk.source != ""


def test_retrieval_with_metadata_filters(populated_kb: KnowledgeBase):
    # Filter by equipment_id F-201A
    res_furnace = populated_kb.retrieve(
        query="emergency procedure steps",
        filters={"equipment_id": "F-201A"},
    )
    assert res_furnace.status == RetrievalStatus.OK
    for item in res_furnace.results:
        assert item.document_id == "DOC-SOP-F201"
        assert item.metadata["equipment_id"] == "F-201A"

    # Filter by equipment_type pump
    res_pump = populated_kb.retrieve(
        query="operating limits",
        filters={"equipment_type": "pump"},
    )
    assert res_pump.status == RetrievalStatus.OK
    for item in res_pump.results:
        assert item.document_id == "DOC-OPM-P101"


# ---------------------------------------------------------------------------
# 2. Safe Failure Modes
# ---------------------------------------------------------------------------

def test_retrieval_empty_kb():
    empty_kb = KnowledgeBase()
    res = empty_kb.retrieve("any query")
    assert res.status == RetrievalStatus.NO_KNOWLEDGE_AVAILABLE
    assert len(res.results) == 0


def test_retrieval_invalid_query(populated_kb: KnowledgeBase):
    res = populated_kb.retrieve("   ")
    assert res.status == RetrievalStatus.INVALID_QUERY
    assert len(res.results) == 0


def test_retrieval_no_relevant_evidence(populated_kb: KnowledgeBase):
    # Filter for non-existent equipment
    res = populated_kb.retrieve(
        query="furnace COT",
        filters={"equipment_id": "NON_EXISTENT_EQ_99"},
    )
    assert res.status == RetrievalStatus.NO_RELEVANT_EVIDENCE
    assert len(res.results) == 0


def test_retrieval_index_unavailable():
    retriever = KnowledgeRetriever(index=None)
    res = retriever.retrieve("query")
    assert res.status == RetrievalStatus.KNOWLEDGE_BASE_UNAVAILABLE


# ---------------------------------------------------------------------------
# 3. Model Evidence Bridge & Synthetic Provenance Tests
# ---------------------------------------------------------------------------

def test_model_evidence_bridge_anomaly_and_fault():
    # ProcessAnomalyDetector
    anomaly_pred = {"is_anomaly": True, "anomaly_score": 0.88, "status": "OK", "threshold": 0.5}
    ev_anomaly = ModelEvidenceBridge.from_anomaly_prediction(anomaly_pred, model_version="v1.1.0")
    assert ev_anomaly.evidence_type == EvidenceType.MODEL_EVIDENCE
    assert ev_anomaly.source_id == "ProcessAnomalyDetector"
    assert ev_anomaly.provenance["status"] == "VALIDATED_WITH_LIMITATIONS"
    assert "Anomaly detected=True" in ev_anomaly.excerpt

    # ProcessFaultClassifier
    fault_pred = {"predicted_fault": 4, "fault_name": "Reactor Cooling Water Step Decrease", "confidence": 0.92, "status": "OK"}
    ev_fault = ModelEvidenceBridge.from_fault_prediction(fault_pred, model_version="v1.1.0")
    assert ev_fault.evidence_type == EvidenceType.MODEL_EVIDENCE
    assert ev_fault.source_id == "ProcessFaultClassifier"
    assert ev_fault.relevance_score == 0.92


def test_model_evidence_bridge_furnace_cot():
    cot_pred = {"predicted_cot": 852.4, "confidence": 0.98, "status": "OK"}
    ev_cot = ModelEvidenceBridge.from_cot_prediction(cot_pred, model_version="v1.1.0")
    assert ev_cot.evidence_type == EvidenceType.MODEL_EVIDENCE
    assert ev_cot.source_id == "FurnaceCOTPredictor"
    assert "852.4" in ev_cot.excerpt


def test_model_evidence_bridge_tube_temp_synthetic_provenance():
    """
    CRITICAL: TubeTemperaturePredictor must explicitly declare its target_type as
    physics_informed_synthetic_surrogate and industrial_validation as False.
    """
    tube_pred = {"predicted_tmt": 965.8, "confidence": 0.95, "status": "OK"}
    ev_tube = ModelEvidenceBridge.from_tube_temp_prediction(tube_pred, model_version="v1.1.0")

    assert ev_tube.evidence_type == EvidenceType.MODEL_EVIDENCE
    assert ev_tube.source_id == "TubeTemperaturePredictor"
    assert ev_tube.provenance["target_type"] == "physics_informed_synthetic_surrogate"
    assert ev_tube.provenance["industrial_validation"] is False
    assert ev_tube.metadata["industrial_validation"] is False
    assert "SYNTHETIC SURROGATE" in ev_tube.excerpt
    assert "NOT measured industrial telemetry" in ev_tube.excerpt


# ---------------------------------------------------------------------------
# 4. RAG Context Builder Tests
# ---------------------------------------------------------------------------

def test_rag_context_builder_combines_document_and_model_evidence(populated_kb: KnowledgeBase):
    retrieval_res = populated_kb.retrieve(query="high COT alarm response F-201A")

    tube_pred = {"predicted_tmt": 970.0, "confidence": 0.90, "status": "OK"}
    tube_ev = ModelEvidenceBridge.from_tube_temp_prediction(tube_pred)

    context = RAGContextBuilder.build_context(
        query="High COT alarm investigation",
        retrieval_result=retrieval_res,
        model_evidence=[tube_ev],
    )

    assert context.status == RetrievalStatus.OK
    assert len(context.evidence_items) >= 2
    assert len(context.citations) >= 1
    assert "Authoritative Documentation Evidence" in context.formatted_context
    assert "Machine Learning Model Evidence" in context.formatted_context
    assert "SYNTHETIC SURROGATE" in context.formatted_context


# ---------------------------------------------------------------------------
# 5. RAGKnowledgeProvider Interface Tests
# ---------------------------------------------------------------------------

def test_rag_knowledge_provider_conformance(populated_kb: KnowledgeBase):
    provider = RAGKnowledgeProvider(knowledge_base=populated_kb)

    # 1. search_knowledge
    results = provider.search_knowledge("furnace fuel gas pressure", asset_id="F-201A")
    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["asset_id"] == "F-201A"
    assert results[0]["knowledge_type"] == "SOP"
    assert len(results[0]["content_hash"]) == 64

    # 2. get_operating_limits
    limits = provider.get_operating_limits(asset_id="F-201A", parameter="COT")
    assert isinstance(limits, dict)
    assert limits.get("asset_id") == "F-201A"
    assert limits.get("retrieved") is True
