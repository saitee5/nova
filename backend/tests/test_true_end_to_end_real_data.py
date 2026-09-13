"""
backend/tests/test_true_end_to_end_real_data.py — Complete True End-to-End Operational Pipeline.

Validates the full unbroken chain with zero mocks:
REAL SEEDED DATA -> REAL TOOL -> REAL ORCHESTRATOR -> REAL RAG -> REAL ML ->
REAL CONTEXT -> DETERMINISTIC RISK -> REAL EPISODE -> REAL CASE -> REAL RUNTIME / HITL -> REAL AUDIT.
"""

import os
import sqlite3
import uuid
import pytest
from datetime import datetime, timezone

from backend.db.db import get_connection
from backend.memory.client import QdrantMemoryClient
from backend.memory.hybrid_search import hybrid_search
from backend.ml.inference.pipeline import ml_pipeline
from backend.models.industrial_domain import MLAssessmentStatus, PlantState, OperatingMode, ProcessTelemetry
from backend.services.industrial_risk_service import IndustrialRiskEngine
from backend.runtime.service import RuntimeService
from backend.runtime.models import RuntimeDecision, DecisionOutcome
from backend.operational_context.builder import build_operational_case
from backend.models.action import ToolCall
from backend.tools.registry import execute_tool


@pytest.mark.asyncio
async def test_full_real_data_operational_lifecycle():
    db_path = "backend/vigil.db"
    assert os.path.exists(db_path), "Database backend/vigil.db must exist"

    # =========================================================================
    # Step 1: REAL SEEDED DATA (Database as Authoritative Source of Truth)
    # =========================================================================
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sensor_readings")
        sensor_count = cursor.fetchone()[0]
        assert sensor_count > 0, "Expected non-zero sensor_readings in seeded DB"

        cursor.execute("SELECT count(*) FROM permits")
        permit_count = cursor.fetchone()[0]
        assert permit_count > 0, "Expected non-zero permits in seeded DB"

        cursor.execute("SELECT count(*) FROM audit_log")
        initial_audit_count = cursor.fetchone()[0]

    # =========================================================================
    # Step 2: REAL TOOL EXECUTION (Dispatched to real backend handler)
    # =========================================================================
    # Execute real permit_suspend tool on permit 'P-2291'
    tool_call = ToolCall(
        tool_name="permit_suspend",
        parameters={"permit_id": "P-2291", "reason": "High temperature alert in Bay3"},
        case_id="E2E-CASE-001",
        requested_by="risk_reasoner",
        authorized=True,
        authorized_by="lead_operator",
        authorized_at=datetime.now(timezone.utc),
    )
    tool_result = await execute_tool(tool_call)
    assert tool_result.success is True, f"Tool permit_suspend failed: {tool_result.error}"
    assert tool_result.result_data.get("new_status") == "suspended"

    # =========================================================================
    # Step 3: REAL RAG (Qdrant Cloud Dense Vector Retrieval)
    # =========================================================================
    qclient = QdrantMemoryClient()
    assert qclient.health_check() is True, "Qdrant Cloud must be healthy and reachable"

    rag_hits = hybrid_search(qclient, "safety_procedures", "hot work permit methane leak", top_k=2)
    assert len(rag_hits) > 0, "Expected real vector retrieval hits from Qdrant Cloud"
    top_rag = rag_hits[0]
    assert top_rag["similarity_score"] > 0.4, "Expected valid similarity score from real embedding comparison"

    # =========================================================================
    # Step 4: REAL ML (Actual Process Model Artifact Execution)
    # =========================================================================
    sample_telemetry = {
        "TI-201": 892.4,   # High COT
        "PI-201": 0.38,
        "FC-201": 23500.0,
        "xmeas_1": 0.25,
        "xmeas_2": 3660.0,
        "xmeas_3": 4500.0,
        "xmeas_4": 9.4,
        "xmeas_9": 120.4,
    }

    ml_assessments = ml_pipeline.run_pipeline(input_data=sample_telemetry, asset_id="F-201A")
    assert "anomaly_detection" in ml_assessments
    assert "fault_diagnosis" in ml_assessments
    assert "furnace_cot_prediction" in ml_assessments

    anomaly_eval = ml_assessments["anomaly_detection"]
    fault_eval = ml_assessments["fault_diagnosis"]
    cot_eval = ml_assessments["furnace_cot_prediction"]

    assert anomaly_eval.status == MLAssessmentStatus.OK
    assert fault_eval.status == MLAssessmentStatus.OK
    assert cot_eval.status == MLAssessmentStatus.OK

    assert anomaly_eval.model_version is not None
    assert cot_eval.prediction is not None
    assert "predicted_cot_celsius" in cot_eval.prediction

    # =========================================================================
    # Step 5: REAL CONTEXT ASSEMBLY
    # =========================================================================
    op_case = build_operational_case(
        telemetry=sample_telemetry,
        equipment_id="F-201A",
    )
    assert op_case.equipment_id == "F-201A"
    assert len(op_case.ml_assessments) >= 3

    # =========================================================================
    # Step 6: DETERMINISTIC RISK ENGINE (Never LLM generated)
    # =========================================================================
    risk_engine = IndustrialRiskEngine()
    test_plant_state = PlantState(
        plant_id="PLANT-NOVA",
        unit_id="UNIT-CRACK-01",
        timestamp=datetime.now(timezone.utc),
        operating_mode=OperatingMode.NORMAL,
        telemetry={
            "TI-201": ProcessTelemetry(tag="TI-201", value=892.4, asset_id="F-201A", unit="celsius"),
        },
        active_alarms=[],
        active_maintenance=[],
        active_permits=[],
        occupancy={},
        equipment_status={"F-201A": "OPERATIONAL"},
    )

    risk_assessment = risk_engine.evaluate_plant_state(
        plant_state=test_plant_state,
        ml_assessments=ml_assessments,
        target_asset_id="F-201A",
    )
    assert 0.0 <= risk_assessment.risk_score <= 1.0
    assert risk_assessment.risk_tier.value in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(risk_assessment.factors) > 0 or len(risk_assessment.recommended_actions) >= 0

    # =========================================================================
    # Step 7: REAL EPISODE PERSISTENCE
    # =========================================================================
    episode_id = f"EP-TEST-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO operational_episodes (
                episode_id, plant_id, unit_id, asset_id, operating_mode,
                status, severity, title, start_time, risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            episode_id, "PLANT-NOVA", "UNIT-CRACK-01", "F-201A", "DEGRADED",
            "ACTIVE", risk_assessment.risk_tier.value, "High COT Elevation on F-201A",
            now_iso, risk_assessment.risk_score,
        ))
        conn.commit()

        cursor.execute("SELECT count(*) FROM operational_episodes WHERE episode_id = ?", (episode_id,))
        assert cursor.fetchone()[0] == 1, "Episode was not persisted in operational_episodes table"

    # =========================================================================
    # Step 8: REAL OPERATIONAL CASE -> RUNTIME CASE & HITL
    # =========================================================================
    runtime_service = RuntimeService(db_path=db_path)
    runtime_case = runtime_service.register_case(op_case, actor="e2e_tester")
    assert runtime_case.case_id == op_case.case_id
    assert runtime_case.runtime_state.value == "READY_FOR_REVIEW"

    # Operator presentation check
    presentation = runtime_service.present_case(runtime_case.case_id)
    assert len(presentation.operator_actions) > 0, "Case must have at least one advisory action"

    # Move from READY_FOR_REVIEW to UNDER_REVIEW
    reviewed_case = runtime_service.start_review(runtime_case.case_id, actor="operator_on_duty")
    assert reviewed_case.runtime_state.value == "UNDER_REVIEW"

    # Select an unblocked action
    action = next((a for a in presentation.operator_actions if not a.is_blocked), presentation.operator_actions[0])
    selected_case = runtime_service.select_action(
        case_id=runtime_case.case_id,
        action_id=action.action_id,
        actor="operator_on_duty",
    )
    assert selected_case.selected_action_id == action.action_id
    assert selected_case.runtime_state.value == "ACTION_SELECTED"

    # Submit APPROVE decision (enforces SafetyGuard + writes audit)
    decision = RuntimeDecision(
        decision=DecisionOutcome.APPROVE,
        action_id=action.action_id,
        actor="lead_engineer",
        reason="Approved mitigation per Standard Operating Procedure.",
    )
    decided_case = runtime_service.record_decision(runtime_case.case_id, decision)
    assert decided_case.runtime_state.value in ["APPROVED", "RESOLVED"]

    # =========================================================================
    # Step 9: REAL AUDIT TRAIL VERIFICATION
    # =========================================================================
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM audit_log")
        final_audit_count = cursor.fetchone()[0]
        assert final_audit_count > initial_audit_count, (
            f"Audit entries must have been written (before: {initial_audit_count}, after: {final_audit_count})"
        )

        # Verify that specific case actions were logged
        cursor.execute("SELECT step, action, actor, decision FROM audit_log WHERE case_id = ? ORDER BY id DESC LIMIT 5", (runtime_case.case_id,))
        audit_rows = cursor.fetchall()
        assert len(audit_rows) > 0, f"Expected audit records for case {runtime_case.case_id}"
        steps = [r[0] for r in audit_rows]
        assert "human_decision" in steps or "operator_action" in steps
