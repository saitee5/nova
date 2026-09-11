"""Response Orchestrator Agent — action proposal & policy coordination (§10.3).

Coordinates tool call authorization with the policy engine and transitions cases through
their lifecycle. Does NOT execute tools directly — delegates execution to backend.tools.registry.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.agents.response_orchestrator.workflow import (
    finalize_authorization,
    propose_tool_call,
)
from backend.models.action import ToolCall, ToolResult
from backend.models.audit import AuditEntry
from backend.models.case import Case
from backend.models.risk import RiskAssessment
from backend.policy_engine.authorization import required_authorization
from backend.services.audit_service import persist_case, write_audit_entry
from backend.services.case_state_machine import transition
from backend.services.notification_service import VoiceNotifier, notify_for_tier
from backend.tools.registry import execute_tool
from backend.bus.event_bus import bus

logger = logging.getLogger(__name__)


_last_announced_tier: dict[str, str] = {}


class ResponseOrchestratorAgent:
    """Agent responsible for proposing actions and orchestrating authorized responses."""

    def __init__(self, notifier: VoiceNotifier) -> None:
        self.notifier = notifier

    async def handle_assessment(
        self, assessment: RiskAssessment, case: Case
    ) -> tuple[Case, ToolCall | None]:
        """Process a RiskAssessment, transition case lifecycle, and propose action if warranted.

        Transitions:
            DETECTED -> INVESTIGATING -> NOTIFYING -> AWAITING_RESPONSE (if required != "none")
        """
        # Update case with assessment score & tier
        current_case = Case(
            case_id=case.case_id,
            zone_id=case.zone_id,
            state=case.state,
            tier=assessment.tier,
            compound_score=assessment.compound_score,
            created_at=case.created_at,
            resolved_at=case.resolved_at,
        )

        prev_tier = _last_announced_tier.get(case.case_id)
        current_tier = assessment.tier

        # 1. State machine transitions DETECTED -> INVESTIGATING -> NOTIFYING
        if current_case.state == "DETECTED":
            current_case, audit = transition(current_case, "INVESTIGATING")
            write_audit_entry(audit)

        if current_case.state == "INVESTIGATING":
            current_case, audit = transition(current_case, "NOTIFYING")
            write_audit_entry(audit)

        # 2. Check required authorization
        required = required_authorization(assessment.tier)

        # 3. Low tier / no authorization required -> reset view to plant overview
        if required == "none" or current_tier == "low":
            if prev_tier and prev_tier != "low":
                await bus.publish("ui.directive", {
                    "type": "ui.reset_view",
                    "payload": {"zone_id": assessment.zone_id, "reason": "risk_low"}
                })
            _last_announced_tier[case.case_id] = "low"
            persist_case(current_case)
            return current_case, None

        # 4. Medium / High / Critical tier -> notify and transition to AWAITING_RESPONSE
        msg = (
            f"VIGIL Risk Alert [{assessment.tier.upper()}]: Zone {assessment.zone_id} "
            f"compound score {assessment.compound_score:.2f}."
        )
        notify_for_tier(current_case, assessment.tier, msg, self.notifier)

        if current_case.state != "AWAITING_RESPONSE":
            current_case, audit = transition(current_case, "AWAITING_RESPONSE")
            write_audit_entry(audit)

        # Propose tool call if warranted by tier + evidence pattern
        tool_call = propose_tool_call(assessment)

        tier_changed = (prev_tier != current_tier)
        _last_announced_tier[case.case_id] = current_tier

        # Only emit UI panel opens, voice speaking, and announcements ONCE per tier transition
        if tier_changed:
            await bus.publish("ui.directive", {
                "type": "ui.focus_zone",
                "payload": {"zone_id": assessment.zone_id}
            })
            await bus.publish("ui.directive", {
                "type": "ui.open_panel",
                "payload": {
                    "panel": "authorization" if (tool_call and tool_call.tool_name == "UpdateControlParameter") else "evidence",
                    "context": {
                        "title": "Authorization Required" if (tool_call and tool_call.tool_name == "UpdateControlParameter") else "Context & Evidence",
                        "subtitle": f"Correlated signals for {assessment.zone_id}"
                    }
                }
            })
            await bus.publish("ui.directive", {
                "type": "ui.announce",
                "payload": {"text": msg}
            })
            await bus.publish("voice.speak", {
                "case_id": case.case_id,
                "text": msg
            })

        if tool_call:
            if tool_call.tool_name == "permit_suspend":
                permit_id = tool_call.parameters.get("permit_id")
                if not permit_id or permit_id == "UNKNOWN_PERMIT":
                    import sqlite3, os
                    db_path = os.environ.get("SQLITE_PATH", "./vigil.db")
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cur = conn.execute("SELECT permit_id FROM permits WHERE status='active' AND (zone_id=? OR zone_id IS NULL) LIMIT 1", (assessment.zone_id,))
                        row = cur.fetchone()
                        if row:
                            permit_id = row["permit_id"]
                            tool_call.parameters["permit_id"] = permit_id
                        conn.close()
                    except Exception:
                        permit_id = "P-2291"
                
                await bus.publish("ui.directive", {
                    "type": "ui.focus_permit",
                    "payload": {
                        "permit_id": permit_id,
                        "zone_id": assessment.zone_id
                    }
                })
            elif tool_call.tool_name == "UpdateControlParameter":
                await bus.publish("ui.directive", {
                    "type": "ui.propose_edit",
                    "payload": {
                        "target_id": tool_call.parameters.get("parameter_id", "param"),
                        "field": "value",
                        "from_value": str(tool_call.parameters.get("current_value", "N/A")),
                        "to_value": str(tool_call.parameters.get("new_value", "N/A")),
                        "reason": tool_call.parameters.get("reason", "Automatic risk mitigation")
                    }
                })

        persist_case(current_case)
        return current_case, tool_call

    async def handle_human_decision(
        self,
        case: Case,
        tool_call: ToolCall,
        decision: bool,
        authorized_by: str,
    ) -> tuple[Case, ToolResult | None]:
        """Handle human authorization decision for a proposed tool call.

        - If decision is True: finalizes authorization, transitions to ACTING, calls
          execute_tool, then transitions to MONITORING.
        - If decision is False: finalizes as unauthorized, audits decision, transitions
          through to RESOLVED (officer dismissed), and NEVER calls execute_tool.
        """
        # 1. Finalize authorization
        finalized_tool = finalize_authorization(tool_call, decision, authorized_by)

        now = datetime.now(timezone.utc)
        decision_str = "APPROVED" if decision else "REJECTED"

        # 2. Write audit entry for human decision
        human_audit = AuditEntry(
            entry_id=str(uuid.uuid4()),
            case_id=case.case_id,
            step="human_decision",
            action="human_decision",
            actor=authorized_by,
            decision=decision_str,
            payload={
                "tool_name": tool_call.tool_name,
                "parameters": tool_call.parameters,
                "timestamp": now.isoformat(),
            },
            ts=now,
        )
        write_audit_entry(human_audit)

        # 3. Decision is False -> officer dismissed action
        if not decision:
            # Transition case through ACTING -> MONITORING -> RESOLVING -> RESOLVED
            c = case
            if c.state == "AWAITING_RESPONSE":
                c, a = transition(c, "ACTING")
                write_audit_entry(a)
            if c.state == "ACTING":
                c, a = transition(c, "MONITORING")
                write_audit_entry(a)
            if c.state == "MONITORING":
                c, a = transition(c, "RESOLVING")
                write_audit_entry(a)
            if c.state == "RESOLVING":
                c, a = transition(c, "RESOLVED")
                write_audit_entry(a)

            persist_case(c)
            logger.info("Human decision REJECTED for case %s; case resolved without tool execution.", case.case_id)
            return c, None

        # 4. Decision is True -> execute tool
        c = case
        if c.state == "AWAITING_RESPONSE":
            c, a = transition(c, "ACTING")
            write_audit_entry(a)

        persist_case(c)

        tool_result: ToolResult | None = None
        try:
            tool_result = await execute_tool(finalized_tool)
        except Exception as exc:
            logger.error("Tool execution failed for tool %s on case %s: %s", finalized_tool.tool_name, case.case_id, exc)
            fail_audit = AuditEntry(
                entry_id=str(uuid.uuid4()),
                case_id=case.case_id,
                step="tool_executed",
                action="tool_execution_failed",
                actor="system",
                payload={
                    "tool_name": finalized_tool.tool_name,
                    "error": str(exc),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                ts=datetime.now(timezone.utc),
            )
            write_audit_entry(fail_audit)

        # Transition to MONITORING after tool execution attempt
        if c.state == "ACTING":
            c, a = transition(c, "MONITORING")
            write_audit_entry(a)

        persist_case(c)
        return c, tool_result
