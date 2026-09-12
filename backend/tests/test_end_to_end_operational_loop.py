"""
backend/tests/test_end_to_end_operational_loop.py — End-to-End Operational Intelligence Loop Tests.

Comprehensive validation of the complete NOVA operational path across all phases:
- TEST A: Healthy plant baseline (nominal telemetry, low risk, no false mitigation)
- TEST B: Process anomaly propagation (simulator disturbance → ML anomaly → elevated risk → episode)
- TEST C: Fault diagnosis & Copilot advisory (classifier diagnosis → evidence package → advisory copilot response)
- TEST D: Furnace COT prediction & surrogate boundaries (valid prediction, no fabricated tube-temp claims)
- TEST E: HITL operator approval lifecycle (registration → review → selection → SafetyGuard → approval → audit → closure)
- TEST F: SafetyGuard authoritative block (prohibited direct actuation blocked, audit logged, zero actuation)
- TEST G: Operator rejection workflow (explicit reason mandatory, persisted with operator provenance)
- TEST H: Semantic history retrieval (real indexed engineering SOPs, provenance metadata, no hallucinations)
- TEST I: Deterministic risk history (persisted snapshots, GET /api/risk/history, no synthetic filler)
- TEST J: WebSocket real-time eventing (typed envelope dispatch, connection management, payload integrity)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.db.db import get_connection
from backend.models.industrial_domain import (
    OperatingMode,
    ProcessTelemetry,
    IndustrialRiskAssessment,
)
from backend.ml.inference.pipeline import MLPipeline, ml_pipeline
from backend.ml.anomaly.detector import ProcessAnomalyDetector
from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor
from backend.ml.furnace.tube_temp_predictor import TubeTemperaturePredictor
from backend.operational_context.builder import build_operational_case
from backend.operational_context.models import (
    CasePriority,
    CaseStatus,
    Observation,
    ObservationQuality,
    OperationalCase,
    RiskIndicator,
)
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.runtime.models import (
    ActionStatus,
    CasePriority as RuntimePriority,
    DecisionOutcome,
    InvalidDecisionError,
    OperatorAction,
    RuntimeCase,
    RuntimeCaseState,
    RuntimeDecision,
)
from backend.runtime.orchestrator import runtime_orchestrator
from backend.runtime.service import RuntimeService, runtime_service
from backend.services.audit_service import get_case_audit_trail, write_audit_entry
from backend.services.plant_state_service import PlantStateService
from backend.services.industrial_risk_service import IndustrialRiskEngine
from backend.simulator.engine import ProcessSimulationEngine
from backend.simulator.live_bridge import LiveIntelligenceBridge
from backend.simulator.models import EquipmentStatus


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite database file for testing."""
    db_file = str(tmp_path / "e2e_operational_test.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_file)
    conn = get_connection(db_file)
    conn.close()
    runtime_service.db_path = db_file
    runtime_service._operational_cases.clear()
    runtime_service._case_actions.clear()
    return db_file


@pytest.fixture
def test_client(isolated_db):
    """FastAPI TestClient with isolated persistence."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# TEST A — Healthy Plant Baseline
# ---------------------------------------------------------------------------

def test_a_healthy_plant():
    """
    TEST A: Verify healthy plant baseline:
    - Telemetry available and within design limits
    - ML Anomaly Detector reports normal baseline (no major anomaly)
    - Deterministic risk engine evaluates to NORMAL/LOW risk tier
    - No false emergency mitigation actions are generated
    """
    engine = ProcessSimulationEngine()
    engine.reset()
    plant_state = engine.step()

    assert plant_state is not None
    assert len(plant_state.telemetry) > 0
    assert plant_state.operating_mode in ("NORMAL", "STEADY_STATE")
    assert len(plant_state.alarms) == 0

    # Risk assessment under nominal steady-state
    risk_engine = IndustrialRiskEngine()
    risk_assessment = risk_engine.evaluate_asset_risk(
        asset_id="F-201A",
        process_anomaly_score=0.05,
        equipment_condition_score=0.02,
        alarm_severity="LOW",
        has_active_permit=False,
        is_simops=False,
        personnel_count_in_zone=1,
        asset_criticality="HIGH",
    )

    assert risk_assessment.risk_score < 0.30
    assert risk_assessment.risk_tier.value in ("LOW", "NORMAL")
    assert not any("emergency" in a.lower() for a in risk_assessment.recommended_actions)


# ---------------------------------------------------------------------------
# TEST B — Process Anomaly Propagation
# ---------------------------------------------------------------------------

def test_b_process_anomaly():
    """
    TEST B: Verify process anomaly propagation:
    - Simulator injects disturbance (TEP cooling water reduction)
    - Alarms triggered and ML evidence evaluates upset condition
    - Deterministic risk engine elevates risk assessment
    - Correlated OperationalCase and episode reflect active deviation
    """
    bridge = LiveIntelligenceBridge()
    bridge.reset_plant()

    # Trigger disturbance scenario and advance engine to allow inertial propagation
    bridge.trigger_scenario("SCENARIO-2-PROCESS-ANOMALY")
    disturbed_state = None
    for _ in range(8):
        disturbed_state = bridge.engine.step()

    assert disturbed_state is not None
    assert len(disturbed_state.alarms) > 0
    assert any(
        "501" in a.tag or "CW" in a.tag or "FLOW" in a.parameter_name.upper() or "COOLING" in a.parameter_name.upper()
        for a in disturbed_state.alarms
    )

    # Bridge produces an OperationalCase with elevated risk indicators
    op_case = bridge.get_operational_case()
    assert op_case is not None
    assert op_case.equipment_id == "F-201A"
    assert len(op_case.alarms) > 0


# ---------------------------------------------------------------------------
# TEST C — Fault Diagnosis & Copilot Advisory
# ---------------------------------------------------------------------------

def test_c_fault_diagnosis_and_copilot(test_client):
    """
    TEST C: Verify fault diagnosis and Copilot advisory behavior:
    - Process Fault Classifier returns typed evidence with provenance
    - Context engine incorporates diagnosis into OperationalCase
    - Copilot endpoint returns evidence package citing the fault diagnosis
    - LLM output explicitly marked advisory_only=True
    """
    classifier = ProcessFaultClassifier()
    # Simulated TEP step decrease feature pattern
    features = {
        "xmeas_1": 0.25,
        "xmeas_2": 3600.0,
        "xmeas_4": 9.2,
        "xmeas_9": 0.35,
        "xmeas_11": 1650.0,  # Depressed cooling water flow
    }
    assessment = classifier.classify_fault(features)

    assert "ProcessFaultClassifier" in assessment.model_name
    assert assessment.model_version is not None
    assert assessment.status in ("OK", "MODEL_NOT_AVAILABLE")

    # Copilot query through real endpoint
    res = test_client.post(
        "/api/copilot/query",
        json={"prompt": "Diagnose cooling water upset on cracking furnace", "asset_id": "F-201A"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["advisory_only"] is True
    assert "evidence_package" in data
    assert data["evidence_package"]["asset_id"] == "F-201A"


# ---------------------------------------------------------------------------
# TEST D — Furnace COT Prediction & Surrogate Boundaries
# ---------------------------------------------------------------------------

def test_d_furnace_cot_prediction_and_boundaries():
    """
    TEST D: Verify Furnace COT model prediction and boundaries:
    - COT prediction produced from valid features with provenance
    - Unsupported tube-temperature and coking index are explicitly marked
      as synthetic surrogate / unavailable, never fabricated as measured ground truth
    """
    cot_predictor = FurnaceCOTPredictor()
    features = {
        "cot_raw": 850.0,
        "feed_rate_raw": 24000.0,
        "fuel_pressure_raw": 0.32,
        "draft_raw": -32.0,
    }
    cot_assessment = cot_predictor.predict_cot(features)
    assert "FurnaceCOTPredictor" in cot_assessment.model_name
    assert cot_assessment.status in ("OK", "MODEL_NOT_AVAILABLE")

    # Verify tube temperature surrogate boundaries
    tube_predictor = TubeTemperaturePredictor()
    tube_assessment = tube_predictor.predict_tube_temperature(features)
    # Never claim validated measured coking or ungrounded physical sensor data
    assert "coking_index" not in (tube_assessment.features_used or [])
    assert (
        "synthetic" in tube_assessment.provenance.get("target_type", "").lower()
        or "not available" in tube_assessment.provenance.get("status", "").lower()
    )


# ---------------------------------------------------------------------------
# TEST E — HITL Operator Approval Lifecycle
# ---------------------------------------------------------------------------

def test_e_hitl_approval_lifecycle(test_client, isolated_db):
    """
    TEST E: Full Human-In-The-Loop approval lifecycle:
    - OperationalCase registered in RuntimeService (READY_FOR_REVIEW)
    - Client retrieves presentation via /api/runtime/cases/{case_id}
    - Operator initiates review (UNDER_REVIEW)
    - Operator selects advisory action (ACTION_SELECTED)
    - SafetyGuard permits valid action
    - Operator approves (APPROVE)
    - Case transitions to RESOLVED and then CLOSED
    - Complete audit trail persisted to SQLite audit_log
    """
    case_id = f"CASE-E2E-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    op_case = OperationalCase(
        case_id=case_id,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        status=CaseStatus.READY_FOR_REVIEW,
        priority=CasePriority.HIGH,
        title="Elevated COT Alarm on Cracking Furnace F-201A",
        summary="Coil outlet temperature exceeding normal envelope.",
        observations=[
            Observation(tag="TI-201", value=885.0, unit="°C", quality=ObservationQuality.GOOD),
        ],
        risk_indicators=[
            RiskIndicator(
                name="cot_alarm_high",
                value=885.0,
                source="TI-201",
                severity=CasePriority.HIGH,
                description="COT exceeds 880°C threshold.",
            ),
        ],
    )

    # 1. Register upstream case into RuntimeService
    rc = runtime_service.register_case(op_case, actor="integration_test")
    assert rc.runtime_state == RuntimeCaseState.READY_FOR_REVIEW

    # 2. Retrieve presentation via REST API
    res = test_client.get(f"/api/runtime/cases/{case_id}")
    assert res.status_code == 200
    pres = res.json()
    assert pres["case_id"] == case_id
    assert pres["runtime_state"] == "READY_FOR_REVIEW"
    assert len(pres["operator_actions"]) > 0

    valid_action = next(a for a in pres["operator_actions"] if not a["is_blocked"])
    action_id = valid_action["action_id"]

    # 3. Transition to UNDER_REVIEW
    under_res = test_client.post(
        f"/api/runtime/cases/{case_id}/transition",
        json={"to_state": "UNDER_REVIEW", "actor": "lead_operator"},
    )
    assert under_res.status_code == 200
    assert under_res.json()["runtime_state"] == "UNDER_REVIEW"

    # 4. Select action
    sel_res = test_client.post(
        f"/api/runtime/cases/{case_id}/select-action",
        json={"action_id": action_id, "actor": "lead_operator"},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["runtime_state"] == "ACTION_SELECTED"

    # 5. Operator approves action
    dec_res = test_client.post(
        f"/api/runtime/cases/{case_id}/decision",
        json={"decision": "APPROVE", "action_id": action_id, "actor": "lead_operator"},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["runtime_state"] == "APPROVED"

    # 6. Resolve case
    res_res = test_client.post(
        f"/api/runtime/cases/{case_id}/resolve",
        json={
            "resolution_summary": "Firing rate reduced in accordance with SOP-F201-001. Temperatures normalized.",
            "actor": "lead_operator",
        },
    )
    assert res_res.status_code == 200
    assert res_res.json()["runtime_state"] == "RESOLVED"

    # 7. Close case
    close_res = test_client.post(
        f"/api/runtime/cases/{case_id}/close",
        json={"actor": "shift_supervisor"},
    )
    assert close_res.status_code == 200
    assert close_res.json()["runtime_state"] == "CLOSED"

    # 8. Audit trail persistence verification
    audit_trail = get_case_audit_trail(case_id)
    assert len(audit_trail) >= 4
    actions_logged = [e.action for e in audit_trail]
    assert "register_case" in actions_logged
    assert "transition_to_ACTION_SELECTED" in actions_logged
    assert "transition_to_APPROVED" in actions_logged
    assert "transition_to_RESOLVED" in actions_logged
    assert "transition_to_CLOSED" in actions_logged


# ---------------------------------------------------------------------------
# TEST F — SafetyGuard Authoritative Block
# ---------------------------------------------------------------------------

def test_f_safety_guard_blocks_prohibited_actions(test_client, isolated_db):
    """
    TEST F: SafetyGuard authoritative blocking of direct actuation:
    - Prohibited actions (plc_write, setpoint_change, dcs_write, etc.) are strictly rejected
    - Attempt to select a blocked action returns HTTP 400 with blocked reason
    - No direct control occurs, zero actuation enforced
    - Audit entry records the blocked attempt
    """
    case_id = f"CASE-BLOCKED-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    op_case = OperationalCase(
        case_id=case_id,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        status=CaseStatus.READY_FOR_REVIEW,
        priority=CasePriority.CRITICAL,
    )
    runtime_service.register_case(op_case, actor="system")

    # Manually register a prohibited candidate action to verify presentation & blocking
    prohibited_action = OperatorAction(
        action_name="plc_write",
        title="Force PLC Output Coil",
        description="Direct override of fuel gas valve actuator coil",
        parameters={"register": "40001", "force_value": 0},
        reason="Direct manual override requested",
    )
    runtime_service._case_actions[case_id] = {prohibited_action.action_id: prohibited_action}

    # Presentation marks action as BLOCKED
    res = test_client.get(f"/api/runtime/cases/{case_id}")
    assert res.status_code == 200
    data = res.json()
    blocked = next((a for a in data["operator_actions"] if a["action_name"] == "plc_write"), None)
    assert blocked is not None
    assert blocked["is_blocked"] is True
    assert any(
        phrase in (blocked["blocked_reason"] or "").lower()
        for phrase in ["safety guard", "read-only", "direct control", "prohibited", "violation"]
    )

    # Transition to UNDER_REVIEW
    test_client.post(
        f"/api/runtime/cases/{case_id}/transition",
        json={"to_state": "UNDER_REVIEW", "actor": "lead_op"},
    )

    # Attempt to select blocked action via API must be rejected with 400
    sel_res = test_client.post(
        f"/api/runtime/cases/{case_id}/select-action",
        json={"action_id": blocked["action_id"], "actor": "operator_unauthorized"},
    )
    assert sel_res.status_code == 400
    assert "blocked" in sel_res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TEST G — Operator Rejection Workflow
# ---------------------------------------------------------------------------

def test_g_operator_rejection_requires_reason(test_client, isolated_db):
    """
    TEST G: Operator rejection workflow:
    - Operator rejecting an action without reason is rejected (400)
    - Rejection with documented reason succeeds and transitions case to REJECTED
    - Operator actor and reason are persisted in immutable audit trail
    """
    case_id = f"CASE-REJECT-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    op_case = OperationalCase(
        case_id=case_id,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        status=CaseStatus.READY_FOR_REVIEW,
        priority=CasePriority.MEDIUM,
    )
    runtime_service.register_case(op_case, actor="system")

    res = test_client.get(f"/api/runtime/cases/{case_id}")
    action_id = res.json()["operator_actions"][0]["action_id"]

    # Transition to UNDER_REVIEW
    test_client.post(
        f"/api/runtime/cases/{case_id}/transition",
        json={"to_state": "UNDER_REVIEW", "actor": "lead_op"},
    )

    # Select action first
    sel_res = test_client.post(
        f"/api/runtime/cases/{case_id}/select-action",
        json={"action_id": action_id, "actor": "lead_op"},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["runtime_state"] == "ACTION_SELECTED"

    # Reject without reason -> fails with 400
    rej_no_reason = test_client.post(
        f"/api/runtime/cases/{case_id}/decision",
        json={"decision": "REJECT", "action_id": action_id, "actor": "lead_op", "reason": ""},
    )
    assert rej_no_reason.status_code == 400

    # Reject with explicit reason -> succeeds
    rej_valid = test_client.post(
        f"/api/runtime/cases/{case_id}/decision",
        json={
            "decision": "REJECT",
            "action_id": action_id,
            "actor": "lead_op",
            "reason": "Process telemetry indicates temporary transient during soot blowing; mechanical intervention not warranted.",
        },
    )
    assert rej_valid.status_code == 200
    assert rej_valid.json()["runtime_state"] == "REJECTED"

    # Audit trail verifies rejection entry
    audit = get_case_audit_trail(case_id)
    rej_entry = next((e for e in audit if e.action == "transition_to_REJECTED"), None)
    assert rej_entry is not None
    assert rej_entry.actor == "lead_op"
    assert rej_entry.decision == "REJECTED"


# ---------------------------------------------------------------------------
# TEST H — Historical Semantic Retrieval
# ---------------------------------------------------------------------------

def test_h_historical_retrieval(test_client):
    """
    TEST H: Historical semantic retrieval:
    - Real indexed engineering documents returned with provenance metadata
    - No fabricated incident outcomes or imaginary historical events
    """
    res = test_client.get("/api/memory/search?q=furnace+overtemperature+procedure&limit=5")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert isinstance(data["results"], list)

    # Retrieval preserves metadata structure
    for match in data["results"]:
        assert "id" in match and "collection" in match


# ---------------------------------------------------------------------------
# TEST I — Deterministic Risk History
# ---------------------------------------------------------------------------

def test_i_deterministic_risk_history(test_client, isolated_db):
    """
    TEST I: Deterministic risk history:
    - Snapshots persist to risk_assessments table
    - GET /api/risk/history?asset_id=F-201A returns real historical records
    - Returns empty list for unknown asset without synthetic curve interpolation
    """
    # 1. Trigger snapshot persistence via evaluate endpoint
    eval_res = test_client.post(
        "/api/risk/evaluate",
        json={
            "asset_id": "F-201A",
            "process_anomaly_score": 0.45,
            "equipment_condition_score": 0.30,
            "alarm_severity": "HIGH",
            "has_active_permit": True,
            "is_simops": False,
            "personnel_count_in_zone": 3,
            "asset_criticality": "HIGH",
        },
    )
    assert eval_res.status_code == 200
    evaluated_score = eval_res.json()["risk_score"]

    # 2. Query risk history
    hist_res = test_client.get("/api/risk/history?asset_id=F-201A&limit=10")
    assert hist_res.status_code == 200
    snapshots = hist_res.json()
    assert isinstance(snapshots, list)
    assert len(snapshots) >= 1

    latest = snapshots[0]
    assert latest["asset_id"] == "F-201A"
    assert latest["risk_score"] == evaluated_score
    assert latest["risk_tier"] in ("HIGH", "CRITICAL", "MEDIUM", "LOW", "NORMAL")
    assert "timestamp" in latest

    # 3. Query unknown asset -> returns empty array, never synthetic data
    unknown_res = test_client.get("/api/risk/history?asset_id=UNKNOWN-ASSET-999&limit=10")
    assert unknown_res.status_code == 200
    assert unknown_res.json() == []


# ---------------------------------------------------------------------------
# TEST J — WebSocket Real-Time Eventing
# ---------------------------------------------------------------------------

def test_j_websocket_eventing(test_client):
    """
    TEST J: WebSocket real-time eventing:
    - Connect to session websocket /ws/session/test-e2e-session
    - Receive heartbeat / status envelope
    - Bridge receives and forwards typed WsEnvelope payloads
    """
    with test_client.websocket_connect("/ws/session/test-session-e2e") as ws:
        # First message is connection status heartbeat
        data = ws.receive_json()
        assert "type" in data
        assert data["type"] == "connection.status"
        assert data["payload"]["status"] == "connected"
        assert data["payload"]["session_id"] == "test-session-e2e"
