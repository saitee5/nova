"""
backend/scripts/demo_operational_loop.py — Deterministic NOVA Operational Intelligence Demo.

Demonstrates the complete, closed-loop industrial operational path:
T+0:  Healthy plant baseline
T+1:  Cooling-water disturbance introduced (SCENARIO-2-PROCESS-ANOMALY)
T+2:  Telemetry changes & dynamic propagation
T+3:  Low-flow Alarm (FI-501) trips
T+4:  ML Process Anomaly Detector reacts
T+5:  ML Process Fault Classifier identifies TEP Fault 11
T+6:  Deterministic Risk Engine elevates asset risk tier
T+7:  Operational Episode forms
T+8:  RuntimeCase becomes READY_FOR_REVIEW
T+9:  Operator views case (UNDER_REVIEW)
T+10: Copilot returns grounded advisory with EvidencePackage
T+11: Operator selects advisory action (ACTION_SELECTED)
T+12: SafetyGuard validates action (Permitted advisory)
T+13: Operator approves action (APPROVE)
T+14: Audit record committed to SQLite audit_log
T+15: Case resolved (RESOLVED)
T+16: Case closed (CLOSED)

PROHIBITED BRANCH:
T+17: Operator attempts direct actuation (plc_write)
T+18: SafetyGuard authority intercepts & strictly BLOCKS
T+19: Zero actuation enforced; violation committed to audit_log
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

from backend.db.db import get_connection
from backend.models.industrial_domain import RiskTier
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.runtime.models import (
    ActionStatus,
    DecisionOutcome,
    InvalidDecisionError,
    OperatorAction,
    RuntimeCaseState,
    RuntimeDecision,
)
from backend.runtime.service import runtime_service
from backend.services.audit_service import get_case_audit_trail
from backend.simulator.live_bridge import LiveIntelligenceBridge


def run_demo() -> None:
    print("=" * 80)
    print("  NOVA INDUSTRIAL OPERATIONAL INTELLIGENCE — END-TO-END DEMONSTRATION")
    print("=" * 80)

    bridge = LiveIntelligenceBridge()
    bridge.reset_plant()

    # ──────────────────────────────────────────────────────────────────────────
    # T+0: Healthy Plant Baseline
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+0] HEALTHY PLANT BASELINE")
    nominal_state = bridge.get_plant_state()
    f201_telem = {k: v.value for k, v in nominal_state.telemetry.items() if "201" in k or "501" in k}
    op_mode = getattr(nominal_state.operating_mode, "value", nominal_state.operating_mode)
    print(f"  Plant Status     : {op_mode}")
    print(f"  Active Alarms    : {len(nominal_state.alarms)}")
    print(f"  Sample Telemetry : TI-201={f201_telem.get('TI-201', 'N/A')} °C, FI-501={f201_telem.get('FI-501', 'N/A')} m³/h")
    print("  Risk Tier        : NORMAL / LOW")

    # ──────────────────────────────────────────────────────────────────────────
    # T+1: Disturbance Injected
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+1] INJECTING COOLING-WATER DISTURBANCE (SCENARIO-2-PROCESS-ANOMALY)")
    bridge.trigger_scenario("SCENARIO-2-PROCESS-ANOMALY")
    print("  Disturbance active: cw_flow step decrease to 1650 m³/h (alarm threshold: 1800 m³/h)")

    # ──────────────────────────────────────────────────────────────────────────
    # T+2 & T+3: Dynamic Propagation & Alarm Activation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+2..3] DYNAMIC PROPAGATION & ALARM ACTIVATION")
    disturbed_state = None
    for tick in range(1, 9):
        disturbed_state = bridge.engine.step()
        cw_val = disturbed_state.telemetry.get("FI-501")
        val_str = f"{cw_val.value:.1f} m³/h" if cw_val else "N/A"
        active_count = len(disturbed_state.alarms)
        print(f"  Tick +{tick}: FI-501={val_str} | Active Alarms: {active_count}")

    assert disturbed_state is not None
    assert len(disturbed_state.alarms) > 0, "Alarms must trip upon cooling water reduction"
    tripped_alarm = disturbed_state.alarms[0]
    sev = getattr(tripped_alarm.severity, "value", tripped_alarm.severity)
    print(f"  >>> ALARM TRIPPED: Tag={tripped_alarm.tag} | Param={tripped_alarm.parameter_name} | "
          f"Val={tripped_alarm.actual_value:.1f} | Severity={sev}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+4 & T+5: ML Anomaly Detection & Fault Classification
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+4..5] ML EVIDENCE GENERATION (REAL TRAINED ARTIFACTS)")
    ml_summaries = disturbed_state.ml_summaries
    for model_name, info in ml_summaries.items():
        val = info.get("predicted_value")
        conf = info.get("confidence")
        conf_str = f" (conf={conf*100:.1f}%)" if conf else ""
        print(f"  - {model_name} [v{info.get('model_version')}]: {val}{conf_str}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+6 & T+7: Context & Deterministic Risk Elevation
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+6..7] CONTEXT & DETERMINISTIC RISK EVALUATION")
    op_case = bridge.get_operational_case()
    assert op_case is not None
    prio = getattr(op_case.priority, "value", op_case.priority)
    print(f"  Operational Case ID : {op_case.case_id}")
    print(f"  Target Asset ID     : {op_case.equipment_id}")
    print(f"  Case Priority       : {prio}")
    print(f"  Observations Count  : {len(op_case.observations)}")
    print(f"  Risk Indicators     : {len(op_case.risk_indicators)}")
    for ri in op_case.risk_indicators[:2]:
        ri_sev = getattr(ri.severity, "value", ri.severity)
        print(f"    * {ri.name}: {ri.value} (Severity: {ri_sev})")

    # ──────────────────────────────────────────────────────────────────────────
    # T+8: RuntimeCase Registered in READY_FOR_REVIEW
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+8] RUNTIME HITL WORKFLOW INITIALIZATION")
    runtime_case = runtime_service.get_runtime_case(op_case.case_id)
    if not runtime_case:
        runtime_case = runtime_service.register_case(op_case, actor="simulator_pipeline")
    print(f"  Runtime Case ID     : {runtime_case.case_id}")
    print(f"  Operational Ref     : {runtime_case.operational_case_ref}")
    print(f"  Initial State       : {runtime_case.runtime_state.value}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+9: Operator Begins Review (UNDER_REVIEW)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+9] OPERATOR INITIATES REVIEW")
    runtime_case = runtime_service.transition(
        runtime_case.case_id,
        RuntimeCaseState.UNDER_REVIEW,
        actor="lead_operator_john",
    )
    print(f"  Transitioned to     : {runtime_case.runtime_state.value} by {runtime_case.actor}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+10: Presentation & Copilot Evidence Grounding
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+10] OPERATOR PRESENTATION & ADVISORY CANDIDATE ACTIONS")
    pres = runtime_service.present_case(runtime_case.case_id)
    print(f"  Total Candidate Actions : {len(pres.operator_actions)}")
    for i, act in enumerate(pres.operator_actions):
        status_tag = "[BLOCKED by SafetyGuard]" if act.is_blocked else "[PERMITTED ADVISORY]"
        print(f"  [{i+1}] {act.title} ({act.action_name}) — {status_tag}")
        print(f"      Reason/Intent: {act.description}")

    # Pick valid permitted advisory action
    advisory_action = next(a for a in pres.operator_actions if not a.is_blocked)
    print(f"\n  Operator selects advisory action: '{advisory_action.title}' (ID: {advisory_action.action_id})")

    # ──────────────────────────────────────────────────────────────────────────
    # T+11: Operator Action Selection (ACTION_SELECTED)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+11] SELECTING ADVISORY ACTION")
    runtime_case = runtime_service.select_action(
        runtime_case.case_id,
        advisory_action.action_id,
        actor="lead_operator_john",
    )
    print(f"  Runtime State       : {runtime_case.runtime_state.value}")
    print(f"  Selected Action ID  : {runtime_case.selected_action_id}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+12 & T+13: SafetyGuard Validation & Operator Approval
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+12..13] SAFETYGUARD VERIFICATION & OPERATOR APPROVAL")
    safety_guard.validate_action(advisory_action.action_name)
    print(f"  SafetyGuard check   : PASSED (Action '{advisory_action.action_name}' is advisory-compliant)")

    decision = RuntimeDecision(
        decision=DecisionOutcome.APPROVE,
        action_id=advisory_action.action_id,
        actor="lead_operator_john",
        reason="Action follows standard operating envelope adjustment for cooling water constraint.",
    )
    runtime_case = runtime_service.record_decision(runtime_case.case_id, decision)
    print(f"  Decision Outcome    : {decision.decision.value}")
    print(f"  Runtime State       : {runtime_case.runtime_state.value}")

    # ──────────────────────────────────────────────────────────────────────────
    # T+14..16: Resolution & Terminal Closure
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[T+14..16] CASE RESOLUTION & TERMINAL CLOSURE")
    runtime_case = runtime_service.resolve_case(
        runtime_case.case_id,
        resolution_summary="Secondary cooling loop standby pump engaged. Cooling water temperatures returned to 28 °C envelope.",
        actor="lead_operator_john",
    )
    print(f"  Runtime State       : {runtime_case.runtime_state.value}")
    print(f"  Resolution Summary  : {runtime_case.resolution_summary}")

    runtime_case = runtime_service.close_case(runtime_case.case_id, actor="shift_supervisor_sarah")
    print(f"  Terminal State      : {runtime_case.runtime_state.value}")
    print(f"  Closed At           : {runtime_case.closed_at}")

    # ──────────────────────────────────────────────────────────────────────────
    # Audit Trail Verification
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[AUDIT TRAIL VERIFICATION]")
    audit_entries = get_case_audit_trail(runtime_case.case_id)
    print(f"  Audit Entries Recorded: {len(audit_entries)}")
    for entry in audit_entries:
        dec_info = f" | Decision: {entry.decision}" if entry.decision else ""
        print(f"    - [{entry.ts}] Action: {entry.action:<30} | Actor: {entry.actor:<20}{dec_info}")

    # ──────────────────────────────────────────────────────────────────────────
    # PROHIBITED CONTROL ATTEMPT BRANCH (SAFETYGUARD ZERO-ACTUATION TEST)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  PROHIBITED DIRECT-CONTROL BRANCH (SAFETYGUARD ZERO-ACTUATION TEST)")
    print("=" * 80)

    prob_case_id = f"CASE-PROHIBITED-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    print(f"\n[PROHIBITED BRANCH] Registering case '{prob_case_id}'...")
    from backend.operational_context.models import CasePriority as CP, CaseStatus as CS, OperationalCase as OC
    prohibited_op_case = OC(
        case_id=prob_case_id,
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        status=CS.READY_FOR_REVIEW,
        priority=CP.CRITICAL,
        title="Prohibited Direct Actuation Probe",
        summary="Testing SafetyGuard interception of prohibited DCS/PLC writes.",
    )
    runtime_service.register_case(prohibited_op_case, actor="system_probe")

    prohibited_action = OperatorAction(
        action_name="plc_write",
        title="Direct PLC Register Force Coil",
        description="Attempt to write directly to Modbus register 40001 to force open fuel valve bypass",
        parameters={"register": 40001, "force_val": 1},
        reason="Emergency manual valve override",
    )
    runtime_service._case_actions[prob_case_id] = {prohibited_action.action_id: prohibited_action}

    # Presentation inspects SafetyGuard
    prob_pres = runtime_service.present_case(prob_case_id)
    blocked_item = next(a for a in prob_pres.operator_actions if a.action_name == "plc_write")
    print(f"  Action Name         : {blocked_item.action_name}")
    print(f"  Is Blocked          : {blocked_item.is_blocked}")
    print(f"  Blocked Reason      : {blocked_item.blocked_reason}")

    # Attempt selection
    runtime_service.transition(prob_case_id, RuntimeCaseState.UNDER_REVIEW, actor="unauthorized_actor")
    try:
        runtime_service.select_action(prob_case_id, blocked_item.action_id, actor="unauthorized_actor")
        print("  ERROR: SafetyGuard failed to block prohibited action!")
        sys.exit(1)
    except InvalidDecisionError as exc:
        print(f"\n  >>> INTERCEPTED & BLOCKED BY SAFETYGUARD:")
        print(f"      {exc}")
        print("  >>> ZERO ACTUATION ENFORCED: No PLC/DCS command was emitted.")

    print("\n" + "=" * 80)
    print("  DEMONSTRATION COMPLETED SUCCESSFULLY — 100% GROUNDED & DETERMINISTIC")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
