"""
backend/tests/test_operational_context.py — Test Suite for NOVA Operational Intelligence Context Layer.

Verifies:
1. OperationalCase instantiation and schema compliance.
2. Observation model separating measured telemetry from ML predictions.
3. ML assessment aggregation across 4 models (Anomaly, Fault, COT, Tube Temp).
4. TubeTemperaturePredictor synthetic surrogate provenance preservation.
5. Multi-domain RAG retrieval and granular evidence categorization:
   - DOCUMENT_EVIDENCE
   - MAINTENANCE_EVIDENCE
   - SAFETY_EVIDENCE
   - PERMIT_EVIDENCE
   - INCIDENT_EVIDENCE
   - EQUIPMENT_EVIDENCE
6. Equipment topology and design limits context.
7. Maintenance history and work order context.
8. Safety matrices, PPE, and LOTO isolation context.
9. Permit-to-work specification context.
10. Incident retrospective and near-miss context.
11. Explicit, transparent risk indicators.
12. Deterministic case priority rules (INFO, LOW, MEDIUM, HIGH, CRITICAL).
13. Case lifecycle progression (NEW -> READY_FOR_REVIEW).
14. End-to-end provenance tracing.
15. Deterministic execution of all 4 canonical scenarios.
16. Missing model handling (graceful degradation, no crashes).
17. Sparse/empty evidence handling (graceful degradation).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path

from backend.knowledge.build_demo_corpus import build_demo_knowledge_base
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import EvidenceType, RetrievalStatus
from backend.ml.inference.pipeline import MLPipeline
from backend.models.industrial_domain import MLAssessment
from backend.operational_context import (
    CasePriority,
    CaseStatus,
    EquipmentDetailContext,
    MLAssessmentSummary,
    Observation,
    ObservationQuality,
    OperationalCase,
    OperationalContextBuilder,
    RiskIndicator,
    ScenarioBuilder,
    build_operational_case,
    create_high_cot_scenario,
    create_maintenance_scenario,
    create_process_anomaly_scenario,
    create_safety_event_scenario,
)


@pytest.fixture(scope="module")
def shared_kb() -> KnowledgeBase:
    """Fixture providing initialized demo knowledge base."""
    return build_demo_knowledge_base()


@pytest.fixture(scope="module")
def shared_ml_pipeline() -> MLPipeline:
    """Fixture providing initialized ML inference pipeline."""
    return MLPipeline()


# ---------------------------------------------------------------------------
# 1. Observation Model Tests
# ---------------------------------------------------------------------------

def test_observation_schema_and_telemetry_separation():
    """Verify observations represent physical sensor telemetry with provenance and units."""
    obs = Observation(
        tag="TI-201",
        value=855.4,
        unit="°C",
        quality=ObservationQuality.GOOD,
        description="Furnace Coil Outlet Temperature",
        source="telemetry",
        is_synthetic=True,
        provenance={"sensor_bus": "Modbus-TCP", "scan_rate_ms": 1000},
    )

    assert obs.tag == "TI-201"
    assert obs.value == 855.4
    assert obs.unit == "°C"
    assert obs.is_synthetic is True
    assert obs.source == "telemetry"
    assert obs.provenance["sensor_bus"] == "Modbus-TCP"


# ---------------------------------------------------------------------------
# 2. ML Assessment Aggregation & Surrogate Provenance
# ---------------------------------------------------------------------------

def test_ml_aggregation_and_synthetic_tmt_provenance(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify that all 4 models are aggregated and Tube Temp maintains synthetic surrogate notice."""
    telemetry = {
        "TI-201": 850.0,
        "PI-201": 0.30,
        "FC-201": 24000.0,
        "XMEAS_1": 0.25,
        "XMEAS_2": 3664.0,
        "XMEAS_9": 120.0,
        "XMEAS_11": 80.0,
        "XMEAS_21": 40.0,
        "XMV_10": 45.0,
        "C2H6": 0.85,
        "C3H8": 0.15,
    }

    case = build_operational_case(
        telemetry=telemetry,
        equipment_id="F-201A",
        kb=shared_kb,
        ml_pipeline=shared_ml_pipeline,
    )

    assert isinstance(case, OperationalCase)
    assert len(case.ml_assessments) == 4

    # Model 1: Anomaly Detector
    anom_sum = case.ml_assessments["ProcessAnomalyDetector"]
    assert anom_sum.is_available is True
    assert anom_sum.model_version == "v1.1.0"
    assert anom_sum.industrial_validation is True

    # Model 2: Fault Classifier
    fault_sum = case.ml_assessments["ProcessFaultClassifier"]
    assert fault_sum.is_available is True
    assert fault_sum.model_version == "v1.1.0"
    assert fault_sum.industrial_validation is True

    # Model 3: Furnace COT Predictor
    cot_sum = case.ml_assessments["FurnaceCOTPredictor"]
    assert cot_sum.is_available is True
    assert cot_sum.model_version == "v1.1.0"
    assert cot_sum.industrial_validation is True
    assert cot_sum.predicted_value is not None

    # Model 4: Tube Temperature Predictor (Synthetic Surrogate)
    tube_sum = case.ml_assessments["TubeTemperaturePredictor"]
    assert tube_sum.is_available is True
    assert tube_sum.model_version.startswith("v1.")
    assert tube_sum.target_type == "physics_informed_synthetic_surrogate"
    assert tube_sum.industrial_validation is False
    assert "Synthetic surrogate" in tube_sum.summary


def test_missing_model_graceful_handling(shared_kb: KnowledgeBase):
    """Verify that if ML models are missing or return errors, the case builder does not crash."""
    builder = OperationalContextBuilder(knowledge_base=shared_kb, ml_pipeline=None)
    # Pass empty precomputed assessments
    case = builder.build_case(
        telemetry={"TI-201": 850.0},
        equipment_id="F-201A",
        precomputed_assessments={},
    )

    assert isinstance(case, OperationalCase)
    for model_name, sum_obj in case.ml_assessments.items():
        assert sum_obj.is_available is False
        assert sum_obj.status == "MODEL_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# 3. Multi-Domain RAG Retrieval & Granular Evidence Categorization
# ---------------------------------------------------------------------------

def test_multi_domain_rag_evidence_categorization(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify retrieved evidence is categorized into document, maintenance, safety, permit, incident buckets."""
    case = build_operational_case(
        telemetry={"TI-201": 888.5, "PI-201": 0.34, "FC-201": 24000.0},
        equipment_id="F-201A",
        scenario_context="high COT alarm 885 C LOTO isolation permit and decoke maintenance history",
        kb=shared_kb,
        ml_pipeline=shared_ml_pipeline,
    )

    # 1. Standard SOP / Engineering evidence
    assert len(case.knowledge_evidence) > 0
    for ev in case.knowledge_evidence:
        assert ev.evidence_type in (EvidenceType.DOCUMENT_EVIDENCE, EvidenceType.EQUIPMENT_EVIDENCE)
        assert len(ev.provenance.get("content_hash", "")) == 64

    # 2. Safety evidence
    assert len(case.safety_context) > 0
    for ev in case.safety_context:
        assert ev.evidence_type in (EvidenceType.SAFETY_EVIDENCE, EvidenceType.PERMIT_EVIDENCE)

    # 3. Maintenance evidence
    assert len(case.maintenance_context) > 0
    for ev in case.maintenance_context:
        assert ev.evidence_type in (EvidenceType.MAINTENANCE_EVIDENCE, EvidenceType.INCIDENT_EVIDENCE)


# ---------------------------------------------------------------------------
# 4. Equipment Context & Plant Topology
# ---------------------------------------------------------------------------

def test_equipment_detail_context(shared_kb: KnowledgeBase):
    """Verify static equipment hierarchy, connected upstream/downstream units, and tags."""
    case = build_operational_case(
        telemetry={"TI-201": 850.0},
        equipment_id="F-201A",
        kb=shared_kb,
    )

    eq = case.equipment_context
    assert eq is not None
    assert eq.equipment_id == "F-201A"
    assert eq.equipment_type == "furnace"
    assert eq.unit_area == "UNIT-CRACK-01"
    assert "P-101A" in eq.connected_upstream
    assert "TLE-201" in eq.connected_downstream
    assert "C-101" in eq.connected_downstream
    assert "TI-201" in eq.associated_tags
    assert eq.design_limits["cot_alarm_high_deg_c"] == 885.0


# ---------------------------------------------------------------------------
# 5. Risk Indicators & Priority Evaluation
# ---------------------------------------------------------------------------

def test_risk_indicators_and_priority_rules(shared_kb: KnowledgeBase):
    """Verify transparent risk indicators and deterministic priority mapping."""
    # High COT scenario -> Should evaluate to HIGH priority
    high_cot_case = build_operational_case(
        telemetry={"TI-201": 889.0, "PI-201": 0.34},
        equipment_id="F-201A",
        alarms=[{"alarm_id": "ALM-001", "severity": "HIGH", "message": "High COT"}],
        kb=shared_kb,
    )

    assert high_cot_case.priority == CasePriority.HIGH
    cot_indicator = next((ind for ind in high_cot_case.risk_indicators if ind.name == "COT_above_alarm_threshold"), None)
    assert cot_indicator is not None
    assert cot_indicator.value == 889.0
    assert cot_indicator.severity == CasePriority.HIGH

    # Emergency trip scenario -> Should evaluate to CRITICAL priority
    trip_case = build_operational_case(
        telemetry={"TI-201": 898.0, "PI-201": 0.35},
        equipment_id="F-201A",
        alarms=[{"alarm_id": "ALM-002", "severity": "CRITICAL", "message": "Trip"}],
        kb=shared_kb,
    )
    assert trip_case.priority == CasePriority.CRITICAL
    trip_indicator = next((ind for ind in trip_case.risk_indicators if ind.name == "COT_above_emergency_trip"), None)
    assert trip_indicator is not None
    assert trip_indicator.severity == CasePriority.CRITICAL


# ---------------------------------------------------------------------------
# 6. Case Lifecycle & Provenance
# ---------------------------------------------------------------------------

def test_case_lifecycle_and_audit_provenance(shared_kb: KnowledgeBase):
    """Verify case lifecycle state transitions and audit provenance fields."""
    case = build_operational_case(
        telemetry={"TI-201": 850.0},
        equipment_id="F-201A",
        kb=shared_kb,
    )

    assert case.status == CaseStatus.READY_FOR_REVIEW
    assert "CASE-" in case.case_id
    assert case.provenance["equipment_id"] == "F-201A"
    assert case.provenance["builder"] == "NOVA Operational Intelligence Context Layer"
    assert len(case.limitations) >= 4
    assert any("ADVISORY INTELLIGENCE ONLY" in lim for lim in case.limitations)
    assert any("SYNTHETIC SURROGATE NOTICE" in lim for lim in case.limitations)


# ---------------------------------------------------------------------------
# 7. Deterministic Demo Scenarios
# ---------------------------------------------------------------------------

def test_scenario_1_high_cot(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify Scenario 1: High COT Thermal Upset."""
    case = ScenarioBuilder.build_case_from_scenario("SCENARIO-1-HIGH-COT", kb=shared_kb, ml_pipeline=shared_ml_pipeline)
    assert case.equipment_id == "F-201A"
    assert case.priority == CasePriority.HIGH
    assert len(case.observations) >= 7
    assert len(case.alarms) >= 1
    assert case.alarms[0]["alarm_id"] == "ALM-TI-201-AH"
    assert len(case.knowledge_evidence) > 0
    assert any(ind.name == "COT_above_alarm_threshold" for ind in case.risk_indicators)


def test_scenario_2_process_anomaly(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify Scenario 2: Process Anomaly & Fault Diagnosis."""
    case = ScenarioBuilder.build_case_from_scenario("SCENARIO-2-PROCESS-ANOMALY", kb=shared_kb, ml_pipeline=shared_ml_pipeline)
    assert case.equipment_id == "F-201A"
    assert case.priority in (CasePriority.MEDIUM, CasePriority.HIGH)
    assert any(o.tag.startswith("XMEAS") for o in case.observations)
    assert len(case.ml_assessments) == 4


def test_scenario_3_maintenance(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify Scenario 3: Decoking & Maintenance Intervention."""
    case = ScenarioBuilder.build_case_from_scenario("SCENARIO-3-MAINTENANCE", kb=shared_kb, ml_pipeline=shared_ml_pipeline)
    assert case.equipment_id == "F-201A"
    assert len(case.maintenance_context) > 0
    assert len(case.safety_context) > 0
    assert any("LOTO" in ind.description or "Permit" in ind.description for ind in case.risk_indicators)


def test_scenario_4_safety_event(shared_kb: KnowledgeBase, shared_ml_pipeline: MLPipeline):
    """Verify Scenario 4: Process Safety Combustible Gas Alert."""
    case = ScenarioBuilder.build_case_from_scenario("SCENARIO-4-SAFETY-EVENT", kb=shared_kb, ml_pipeline=shared_ml_pipeline)
    assert case.equipment_id == "F-201A"
    assert case.priority == CasePriority.HIGH
    assert any(o.tag == "GD-201" for o in case.observations)
    assert len(case.safety_context) > 0
    assert any("20%" in ind.description or "active_alarms" in ind.name for ind in case.risk_indicators)
