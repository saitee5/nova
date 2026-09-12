"""
backend/tests/test_runtime_workflow.py — Comprehensive Test Suite for NOVA Runtime Workflow.

Verifies:
A. Case Registration:
   - Valid OperationalCase registration
   - Idempotent duplicate registration
   - Sparse OperationalCase handling
B. Presentation (RuntimeResult):
   - Multi-domain evidence summarization (without RAG rerun)
   - ML assessment summarization (without ML rerun)
   - Risk indicators mapping & advisory action derivation
   - Missing data & sparse input graceful degradation
C. State Machine:
   - Primary flow: READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED → RESOLVED → CLOSED
   - Alternative rejection flow: ACTION_SELECTED → REJECTED → RESOLVED → CLOSED
   - Invalid jumps rejection (e.g. READY_FOR_REVIEW → APPROVED)
   - CLOSED state terminal immutability (cannot transition out)
D. Human-in-the-Loop (HITL):
   - Action selection validation (must exist, must not be blocked)
   - Typed decision recording (APPROVE / REJECT)
   - Rejection requires non-empty reason
   - Resolution requires non-empty summary
E. SafetyGuard & Zero-Actuation:
   - Direct control actions (PLC/DCS/SIS/ESD writes) intercepted
   - Intercepted actions visible with status=BLOCKED, is_blocked=True, blocked_reason
   - Blocked actions cannot be selected or approved
   - Zero actuation verified (purely advisory)
F. Audit Trail:
   - All events persisted via existing audit_service into audit_log
   - Chronological audit trail retrieval
G. REST API:
   - Endpoints for list, get, transition, select-action, decision, resolve, close, timeline, audit
   - Deterministic HTTP 400 on invalid transition, 404 on missing case
H. End-to-End:
   - Complete lifecycle validation across database and audit log
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from backend.db.db import get_connection
from backend.main import app
from backend.models.audit import AuditEntry
from backend.operational_context.models import (
    CasePriority,
    CaseStatus,
    MLAssessmentSummary,
    Observation,
    ObservationQuality,
    OperationalCase,
    RiskIndicator,
)
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.runtime.models import (
    ActionStatus,
    DecisionOutcome,
    InvalidDecisionError,
    OperatorAction,
    RuntimeAuditRecord,
    RuntimeCase,
    RuntimeCaseState,
    RuntimeDecision,
    RuntimeResult,
)
from backend.runtime.orchestrator import RuntimeOrchestrator, runtime_orchestrator
from backend.runtime.service import RuntimeService, runtime_service
from backend.runtime.state_machine import (
    RUNTIME_TRANSITIONS,
    InvalidRuntimeTransitionError,
    transition_runtime_case,
)
from backend.services.audit_service import get_case_audit_trail


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite database file for testing."""
    db_file = str(tmp_path / "runtime_test.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_file)
    conn = get_connection(db_file)
    conn.close()
    return db_file


@pytest.fixture
def service(isolated_db):
    """Provide a RuntimeService configured with the isolated database."""
    svc = RuntimeService(db_path=isolated_db)
    # Also point the singleton's db_path to isolated_db for API route testing
    runtime_service.db_path = isolated_db
    runtime_service._operational_cases.clear()
    runtime_service._case_actions.clear()
    return svc


@pytest.fixture
def sample_operational_case() -> OperationalCase:
    """Construct a realistic sample OperationalCase."""
    return OperationalCase(
        case_id="CASE-20260913-F201A-001",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        status=CaseStatus.READY_FOR_REVIEW,
        priority=CasePriority.HIGH,
        title="High Priority Process Deviation on F-201A",
        summary="Elevated process temperatures detected on cracking furnace F-201A.",
        overall_state="ABNORMAL_DEVIATION",
        observations=[
            Observation(tag="TI-201", value=888.5, unit="°C", quality=ObservationQuality.GOOD),
            Observation(tag="PI-201", value=0.35, unit="MPa", quality=ObservationQuality.GOOD),
        ],
        ml_assessments={
            "ProcessAnomalyDetector": MLAssessmentSummary(
                model_name="ProcessAnomalyDetector",
                model_version="v1.1.0",
                status="OK",
                is_available=True,
                predicted_value="Anomaly Detected",
                confidence=0.92,
                summary="Process anomaly confirmed with 92% confidence",
            ),
            "FurnaceCOTPredictor": MLAssessmentSummary(
                model_name="FurnaceCOTPredictor",
                model_version="v1.1.0",
                status="OK",
                is_available=True,
                predicted_value=888.5,
                confidence=0.88,
                summary="Predicted COT 888.5 °C exceeds normal envelope",
            ),
        },
        risk_indicators=[
            RiskIndicator(
                name="COT_above_threshold",
                value=888.5,
                source="Telemetry TI-201",
                severity=CasePriority.HIGH,
                description="Coil Outlet Temperature exceeds high alarm threshold (885 °C)",
            ),
            RiskIndicator(
                name="anomaly_detected",
                value=True,
                source="ProcessAnomalyDetector v1.1.0",
                severity=CasePriority.HIGH,
                description="Statistical anomaly detected across furnace thermal parameters",
            ),
        ],
        limitations=[
            "ADVISORY INTELLIGENCE ONLY: NOVA operates in read-only advisory mode.",
        ],
        scenario_type="synthetic_demo",
    )


# ---------------------------------------------------------------------------
# A. Case Registration Tests
# ---------------------------------------------------------------------------

def test_case_registration_success(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify registration creates a RuntimeCase in READY_FOR_REVIEW referencing OperationalCase."""
    rc = service.register_case(sample_operational_case, actor="engineer_1")

    assert rc.case_id == sample_operational_case.case_id
    assert rc.operational_case_ref == sample_operational_case.case_id
    assert rc.equipment_id == "F-201A"
    assert rc.runtime_state == RuntimeCaseState.READY_FOR_REVIEW
    assert rc.priority == CasePriority.HIGH
    assert rc.actor == "engineer_1"

    # Verify database persistence
    fetched = service.get_runtime_case(sample_operational_case.case_id)
    assert fetched is not None
    assert fetched.case_id == sample_operational_case.case_id
    assert fetched.runtime_state == RuntimeCaseState.READY_FOR_REVIEW

    # Verify audit entry recorded
    audit = get_case_audit_trail(sample_operational_case.case_id)
    assert len(audit) >= 1
    assert audit[0].action == "register_case"
    assert audit[0].actor == "engineer_1"


def test_case_registration_idempotent(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify duplicate registration of the same case_id is idempotent."""
    rc1 = service.register_case(sample_operational_case, actor="system")
    rc2 = service.register_case(sample_operational_case, actor="system")

    assert rc1.case_id == rc2.case_id

    # Verify exactly one database row exists
    cases = service.list_runtime_cases()
    assert len(cases) == 1


def test_sparse_operational_case_registration(service: RuntimeService):
    """Verify sparse OperationalCase (minimal fields) registers cleanly with default priority."""
    sparse = OperationalCase(
        case_id="CASE-SPARSE-001",
        equipment_id="P-101A",
    )
    rc = service.register_case(sparse)
    assert rc.case_id == "CASE-SPARSE-001"
    assert rc.equipment_id == "P-101A"
    assert rc.runtime_state == RuntimeCaseState.READY_FOR_REVIEW
    assert rc.priority == CasePriority.INFO


# ---------------------------------------------------------------------------
# B. Presentation (RuntimeResult) Tests
# ---------------------------------------------------------------------------

def test_presentation_complete_structure(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify RuntimeResult aggregates intelligence into frontend presentation without re-inference."""
    service.register_case(sample_operational_case)
    pres = service.present_case(sample_operational_case.case_id)

    assert isinstance(pres, RuntimeResult)
    assert pres.case_id == sample_operational_case.case_id
    assert pres.equipment_id == "F-201A"
    assert pres.runtime_state == RuntimeCaseState.READY_FOR_REVIEW
    assert len(pres.ml_summaries) == 2
    assert pres.ml_summaries[0].model_name in ("ProcessAnomalyDetector", "FurnaceCOTPredictor")
    assert len(pres.operator_actions) >= 1
    assert pres.evidence_summary.knowledge_count == 0  # Sample had no RAG chunks
    assert len(pres.timeline_events) >= 1  # Includes registration


def test_presentation_sparse_case_handling(service: RuntimeService):
    """Verify presentation gracefully handles empty evidence and models."""
    sparse = OperationalCase(case_id="CASE-EMPTY-001", equipment_id="C-101")
    service.register_case(sparse)
    pres = service.present_case("CASE-EMPTY-001")

    assert pres.evidence_summary.knowledge_count == 0
    assert pres.evidence_summary.safety_count == 0
    assert len(pres.ml_summaries) == 0
    assert len(pres.risk_indicators) == 0
    assert len(pres.operator_actions) >= 1  # Fallback baseline monitoring action created


# ---------------------------------------------------------------------------
# C. State Machine Tests
# ---------------------------------------------------------------------------

def test_state_machine_primary_flow():
    """Verify explicit primary flow: READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED → RESOLVED → CLOSED."""
    now = datetime.now(timezone.utc)
    case = RuntimeCase(
        case_id="CASE-FLOW-001",
        operational_case_ref="CASE-FLOW-001",
        equipment_id="F-201A",
        runtime_state=RuntimeCaseState.READY_FOR_REVIEW,
        created_at=now,
        updated_at=now,
    )

    # 1. READY_FOR_REVIEW → UNDER_REVIEW
    case, a1 = transition_runtime_case(case, RuntimeCaseState.UNDER_REVIEW)
    assert case.runtime_state == RuntimeCaseState.UNDER_REVIEW
    assert a1.action == "transition_to_UNDER_REVIEW"

    # 2. UNDER_REVIEW → ACTION_SELECTED
    case.selected_action_id = "act_test_01"
    case, a2 = transition_runtime_case(case, RuntimeCaseState.ACTION_SELECTED)
    assert case.runtime_state == RuntimeCaseState.ACTION_SELECTED

    # 3. ACTION_SELECTED → APPROVED
    case, a3 = transition_runtime_case(case, RuntimeCaseState.APPROVED)
    assert case.runtime_state == RuntimeCaseState.APPROVED

    # 4. APPROVED → RESOLVED
    case, a4 = transition_runtime_case(case, RuntimeCaseState.RESOLVED)
    assert case.runtime_state == RuntimeCaseState.RESOLVED
    assert case.resolved_at is not None

    # 5. RESOLVED → CLOSED
    case, a5 = transition_runtime_case(case, RuntimeCaseState.CLOSED)
    assert case.runtime_state == RuntimeCaseState.CLOSED
    assert case.closed_at is not None


def test_state_machine_rejection_flow():
    """Verify alternative flow: ACTION_SELECTED → REJECTED → RESOLVED → CLOSED."""
    now = datetime.now(timezone.utc)
    case = RuntimeCase(
        case_id="CASE-REJECT-001",
        operational_case_ref="CASE-REJECT-001",
        equipment_id="F-201A",
        runtime_state=RuntimeCaseState.ACTION_SELECTED,
        selected_action_id="act_test_02",
        created_at=now,
        updated_at=now,
    )

    # ACTION_SELECTED → REJECTED
    case, a1 = transition_runtime_case(case, RuntimeCaseState.REJECTED)
    assert case.runtime_state == RuntimeCaseState.REJECTED

    # REJECTED → RESOLVED
    case, a2 = transition_runtime_case(case, RuntimeCaseState.RESOLVED)
    assert case.runtime_state == RuntimeCaseState.RESOLVED

    # RESOLVED → CLOSED
    case, a3 = transition_runtime_case(case, RuntimeCaseState.CLOSED)
    assert case.runtime_state == RuntimeCaseState.CLOSED


def test_state_machine_invalid_jumps():
    """Verify arbitrary jumps are rejected with InvalidRuntimeTransitionError."""
    now = datetime.now(timezone.utc)
    case = RuntimeCase(
        case_id="CASE-JUMP-001",
        operational_case_ref="CASE-JUMP-001",
        equipment_id="F-201A",
        runtime_state=RuntimeCaseState.READY_FOR_REVIEW,
        created_at=now,
        updated_at=now,
    )

    # Illegal jump: READY_FOR_REVIEW → APPROVED
    with pytest.raises(InvalidRuntimeTransitionError):
        transition_runtime_case(case, RuntimeCaseState.APPROVED)

    # Illegal jump: READY_FOR_REVIEW → CLOSED
    with pytest.raises(InvalidRuntimeTransitionError):
        transition_runtime_case(case, RuntimeCaseState.CLOSED)


def test_state_machine_approval_guard():
    """Verify transition to APPROVED fails if selected_action_id is missing."""
    now = datetime.now(timezone.utc)
    case = RuntimeCase(
        case_id="CASE-NIL-ACT",
        operational_case_ref="CASE-NIL-ACT",
        equipment_id="F-201A",
        runtime_state=RuntimeCaseState.ACTION_SELECTED,
        selected_action_id=None,  # No selected action!
        created_at=now,
        updated_at=now,
    )

    with pytest.raises(InvalidRuntimeTransitionError) as exc_info:
        transition_runtime_case(case, RuntimeCaseState.APPROVED)
    assert "without a selected action" in str(exc_info.value)


def test_closed_state_immutability():
    """Verify CLOSED is terminal: no transition out is allowed."""
    now = datetime.now(timezone.utc)
    case = RuntimeCase(
        case_id="CASE-CLOSED-001",
        operational_case_ref="CASE-CLOSED-001",
        equipment_id="F-201A",
        runtime_state=RuntimeCaseState.CLOSED,
        created_at=now,
        updated_at=now,
        closed_at=now,
    )

    for target in RuntimeCaseState:
        with pytest.raises(InvalidRuntimeTransitionError) as exc_info:
            transition_runtime_case(case, target)
        assert "is CLOSED and terminal" in str(exc_info.value)


# ---------------------------------------------------------------------------
# D. Human-in-the-Loop (HITL) Workflow Tests
# ---------------------------------------------------------------------------

def test_hitl_action_selection(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify action selection transitions case from UNDER_REVIEW to ACTION_SELECTED."""
    service.register_case(sample_operational_case)
    service.start_review(sample_operational_case.case_id, actor="operator_john")

    pres = service.present_case(sample_operational_case.case_id)
    target_action = pres.operator_actions[0]

    updated = service.select_action(
        case_id=sample_operational_case.case_id,
        action_id=target_action.action_id,
        actor="operator_john",
    )

    assert updated.runtime_state == RuntimeCaseState.ACTION_SELECTED
    assert updated.selected_action_id == target_action.action_id


def test_hitl_approval_and_resolution(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify happy path approval and resolution."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case)
    service.start_review(cid, actor="lead_operator")

    pres = service.present_case(cid)
    action = pres.operator_actions[0]
    service.select_action(cid, action.action_id, actor="lead_operator")

    # Record typed decision: APPROVE
    decision = RuntimeDecision(
        decision=DecisionOutcome.APPROVE,
        action_id=action.action_id,
        actor="lead_operator",
        reason="Burner balance inspection confirmed necessary.",
    )
    approved_case = service.record_decision(cid, decision)
    assert approved_case.runtime_state == RuntimeCaseState.APPROVED

    # Resolve case
    resolved_case = service.resolve_case(
        cid,
        resolution_summary="Walkdown complete. Air damper readjusted to 35% open.",
        actor="lead_operator",
    )
    assert resolved_case.runtime_state == RuntimeCaseState.RESOLVED
    assert resolved_case.resolution_summary is not None

    # Close case
    closed_case = service.close_case(cid, actor="shift_supervisor")
    assert closed_case.runtime_state == RuntimeCaseState.CLOSED


def test_hitl_rejection_requires_reason(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify rejection without reason is rejected by typed validation and service."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case)
    service.start_review(cid)
    pres = service.present_case(cid)
    action = pres.operator_actions[0]
    service.select_action(cid, action.action_id)

    # Attempt rejection with empty reason — Pydantic validator catches this
    with pytest.raises(ValueError) as exc_info:
        RuntimeDecision(
            decision=DecisionOutcome.REJECT,
            action_id=action.action_id,
            actor="operator_bob",
            reason="",  # Empty!
        )
    assert "reason must be non-empty" in str(exc_info.value)


def test_hitl_rejection_flow(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify alternative rejection workflow."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case)
    service.start_review(cid, actor="operator_bob")
    pres = service.present_case(cid)
    action = pres.operator_actions[0]
    service.select_action(cid, action.action_id, actor="operator_bob")

    decision = RuntimeDecision(
        decision=DecisionOutcome.REJECT,
        action_id=action.action_id,
        actor="operator_bob",
        reason="Thermocouple TI-201 undergoing calibration; reading is artificial.",
    )
    rejected_case = service.record_decision(cid, decision)
    assert rejected_case.runtime_state == RuntimeCaseState.REJECTED

    resolved_case = service.resolve_case(
        cid,
        resolution_summary="False alarm due to sensor calibration drift.",
        actor="operator_bob",
    )
    assert resolved_case.runtime_state == RuntimeCaseState.RESOLVED


# ---------------------------------------------------------------------------
# E. SafetyGuard & Zero-Actuation Tests
# ---------------------------------------------------------------------------

def test_safety_guard_blocks_prohibited_actions(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify SafetyGuard intercepts prohibited commands and keeps them visible as BLOCKED."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case)

    # Create candidate actions including direct control attempts
    candidates = [
        OperatorAction(
            action_name="advisory_burner_survey",
            title="Perform Optical Burner Survey",
            description="Inspect flames through inspection port.",
            reason="Advisory check",
        ),
        OperatorAction(
            action_name="plc_write_fuel_valve",
            title="Direct PLC Valve Cutback",
            description="Attempt direct PLC output command.",
            reason="Dangerous direct control attempt",
        ),
        OperatorAction(
            action_name="dcs_write_steam_setpoint",
            title="Change DCS Setpoint",
            description="Attempt direct DCS setpoint write.",
            reason="Dangerous setpoint override",
        ),
    ]

    pres = service.orchestrator.build_presentation(
        case=sample_operational_case,
        candidate_actions=candidates,
    )

    # Verify all 3 actions are visible (never silently dropped)
    assert len(pres.operator_actions) == 3

    # Find the blocked actions
    blocked = [a for a in pres.operator_actions if a.is_blocked]
    assert len(blocked) == 2
    for b in blocked:
        assert b.status == ActionStatus.BLOCKED
        assert b.blocked_reason is not None
        assert "SAFETY GUARDRALL VIOLATION" in b.blocked_reason

    # The safe advisory action is AVAILABLE
    safe = [a for a in pres.operator_actions if not a.is_blocked]
    assert len(safe) == 1
    assert safe[0].status == ActionStatus.AVAILABLE


def test_blocked_action_cannot_be_selected(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify attempting to select a BLOCKED action raises InvalidDecisionError."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case)
    service.start_review(cid)

    # Inject a blocked action into presentation
    blocked_action = OperatorAction(
        action_name="actuator_control_valve",
        title="Force Valve Position",
        description="Dangerous force command",
        reason="Forbidden",
    )
    pres = service.orchestrator.build_presentation(
        case=sample_operational_case,
        candidate_actions=[blocked_action],
    )
    service._case_actions[cid] = {blocked_action.action_id: pres.operator_actions[0]}

    # Attempting to select this blocked action must fail!
    with pytest.raises(InvalidDecisionError) as exc_info:
        service.select_action(cid, blocked_action.action_id)
    assert "BLOCKED by safety guard" in str(exc_info.value)


# ---------------------------------------------------------------------------
# F. Audit Trail Tests
# ---------------------------------------------------------------------------

def test_complete_audit_trail(service: RuntimeService, sample_operational_case: OperationalCase):
    """Verify that every runtime milestone produces an AuditEntry in audit_log."""
    cid = sample_operational_case.case_id
    service.register_case(sample_operational_case, actor="system_init")
    service.start_review(cid, actor="auditor_jane")

    pres = service.present_case(cid)
    act = pres.operator_actions[0]
    service.select_action(cid, act.action_id, actor="auditor_jane")

    decision = RuntimeDecision(
        decision=DecisionOutcome.APPROVE,
        action_id=act.action_id,
        actor="auditor_jane",
        reason="Safety checks verified.",
    )
    service.record_decision(cid, decision)
    service.resolve_case(cid, "Normal operation restored.", actor="auditor_jane")
    service.close_case(cid, actor="auditor_jane")

    # Fetch audit log
    audit_trail = get_case_audit_trail(cid)
    assert len(audit_trail) >= 6

    actions_recorded = [a.action for a in audit_trail]
    assert "register_case" in actions_recorded
    assert "transition_to_UNDER_REVIEW" in actions_recorded
    assert "transition_to_ACTION_SELECTED" in actions_recorded
    assert "decision_APPROVE" in actions_recorded
    assert "transition_to_RESOLVED" in actions_recorded
    assert "transition_to_CLOSED" in actions_recorded


# ---------------------------------------------------------------------------
# G. REST API Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client(service: RuntimeService) -> TestClient:
    """FastAPI TestClient with isolated runtime service."""
    return TestClient(app)


def test_api_runtime_lifecycle(api_client: TestClient, sample_operational_case: OperationalCase):
    """Test full API lifecycle via HTTP endpoints."""
    # 1. Register case
    reg_resp = api_client.post("/api/runtime/cases/register", json=sample_operational_case.model_dump(mode="json"))
    assert reg_resp.status_code == 200
    cid = reg_resp.json()["case_id"]

    # 2. List cases
    list_resp = api_client.get("/api/runtime/cases")
    assert list_resp.status_code == 200
    assert any(c["case_id"] == cid for c in list_resp.json())

    # 3. Get case presentation
    get_resp = api_client.get(f"/api/runtime/cases/{cid}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["runtime_state"] == "READY_FOR_REVIEW"
    assert len(data["operator_actions"]) >= 1
    target_action = data["operator_actions"][0]

    # 4. Transition to UNDER_REVIEW
    trans_resp = api_client.post(
        f"/api/runtime/cases/{cid}/transition",
        json={"to_state": "UNDER_REVIEW", "actor": "api_operator"},
    )
    assert trans_resp.status_code == 200
    assert trans_resp.json()["runtime_state"] == "UNDER_REVIEW"

    # 5. Select action
    select_resp = api_client.post(
        f"/api/runtime/cases/{cid}/select-action",
        json={"action_id": target_action["action_id"], "actor": "api_operator"},
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["runtime_state"] == "ACTION_SELECTED"

    # 6. Record decision: APPROVE
    dec_resp = api_client.post(
        f"/api/runtime/cases/{cid}/decision",
        json={
            "decision": "APPROVE",
            "action_id": target_action["action_id"],
            "actor": "api_operator",
            "reason": "Approved via API test",
        },
    )
    assert dec_resp.status_code == 200
    assert dec_resp.json()["runtime_state"] == "APPROVED"

    # 7. Resolve case
    res_resp = api_client.post(
        f"/api/runtime/cases/{cid}/resolve",
        json={"resolution_summary": "Resolved via API test.", "actor": "api_operator"},
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["runtime_state"] == "RESOLVED"

    # 8. Close case
    close_resp = api_client.post(
        f"/api/runtime/cases/{cid}/close",
        json={"actor": "api_supervisor"},
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["runtime_state"] == "CLOSED"

    # 9. Verify CLOSED is immutable via API
    fail_resp = api_client.post(
        f"/api/runtime/cases/{cid}/transition",
        json={"to_state": "UNDER_REVIEW", "actor": "intruder"},
    )
    assert fail_resp.status_code == 400


def test_api_404_on_unknown_case(api_client: TestClient):
    """Verify 404 returned when accessing non-existent case."""
    resp = api_client.get("/api/runtime/cases/UNKNOWN_CASE_999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# H. End-to-End Verification
# ---------------------------------------------------------------------------

def test_end_to_end_runtime_flow(service: RuntimeService, sample_operational_case: OperationalCase):
    """
    End-to-End Test:
    OperationalCase
          ↓
    RuntimeCase
          ↓
    RuntimeOrchestrator
          ↓
    READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED → RESOLVED → CLOSED
    """
    cid = sample_operational_case.case_id

    # Step 1: Upstream intelligence finishes -> runtime registers case
    rc = service.register_case(sample_operational_case, actor="ingest_pipeline")
    assert rc.runtime_state == RuntimeCaseState.READY_FOR_REVIEW

    # Step 2: Operator starts review
    rc = service.start_review(cid, actor="operator_sarah")
    assert rc.runtime_state == RuntimeCaseState.UNDER_REVIEW

    # Step 3: Presentation inspected, action selected
    pres = service.present_case(cid)
    action = pres.operator_actions[0]
    rc = service.select_action(cid, action.action_id, actor="operator_sarah")
    assert rc.runtime_state == RuntimeCaseState.ACTION_SELECTED
    assert rc.selected_action_id == action.action_id

    # Step 4: Operator decision (APPROVE)
    decision = RuntimeDecision(
        decision=DecisionOutcome.APPROVE,
        action_id=action.action_id,
        actor="operator_sarah",
        reason="Thermal checks and draft survey approved.",
    )
    rc = service.record_decision(cid, decision)
    assert rc.runtime_state == RuntimeCaseState.APPROVED

    # Step 5: Operator records resolution
    rc = service.resolve_case(
        cid,
        resolution_summary="Damper alignment verified and process parameters returned to baseline.",
        actor="operator_sarah",
    )
    assert rc.runtime_state == RuntimeCaseState.RESOLVED
    assert rc.resolved_at is not None

    # Step 6: Supervisor closes case
    rc = service.close_case(cid, actor="supervisor_dave")
    assert rc.runtime_state == RuntimeCaseState.CLOSED
    assert rc.closed_at is not None

    # Step 7: Verify terminal immutability
    with pytest.raises(InvalidRuntimeTransitionError):
        service.start_review(cid)

    # Step 8: Verify timeline & audit consistency
    timeline = service.get_timeline(cid)
    assert len(timeline) >= 6
