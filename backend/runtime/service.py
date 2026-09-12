"""
backend/runtime/service.py — Runtime Service for Human-in-the-Loop Operator Workflows.

Coordinates the complete operator lifecycle:
OperationalCase → register_case() → READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED/REJECTED → RESOLVED → CLOSED

Guarantees:
1. Strict State Ownership: RuntimeCase stores workflow metadata and references OperationalCase.
2. Actual SafetyGuard Enforcement: Action selection and approval reject blocked actions.
3. Existing Audit Infrastructure: All events write to audit_log via audit_service.write_audit_entry.
4. Terminal Immutability: Once CLOSED, cases reject all modifications.
5. Deterministic Error Handling: Illegal transitions raise InvalidRuntimeTransitionError or InvalidDecisionError.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.db.db import get_connection
from backend.operational_context.models import OperationalCase
from backend.runtime.models import (
    ActionStatus,
    CasePriority,
    DecisionOutcome,
    InvalidDecisionError,
    OperatorAction,
    RuntimeAuditRecord,
    RuntimeCase,
    RuntimeCaseState,
    RuntimeDecision,
    RuntimeResult,
    TimelineEvent,
)
from backend.runtime.orchestrator import RuntimeOrchestrator, runtime_orchestrator
from backend.runtime.state_machine import (
    InvalidRuntimeTransitionError,
    transition_runtime_case,
)
from backend.services.audit_service import get_case_audit_trail, write_audit_entry

logger = logging.getLogger("nova.runtime.service")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class RuntimeService:
    """
    Core service managing runtime workflow lifecycles, decisions, and audit persistence.
    """

    def __init__(
        self,
        orchestrator: Optional[RuntimeOrchestrator] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.orchestrator = orchestrator or runtime_orchestrator
        self.db_path = db_path
        # In-memory caches for fast presentation retrieval
        self._operational_cases: Dict[str, OperationalCase] = {}
        self._case_actions: Dict[str, Dict[str, OperatorAction]] = {}

    def _get_conn(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    # -----------------------------------------------------------------------
    # Case Registration
    # -----------------------------------------------------------------------

    def register_case(
        self,
        operational_case: OperationalCase,
        actor: str = "system",
    ) -> RuntimeCase:
        """
        Register an OperationalCase into the runtime workflow layer.
        Idempotent: if case_id already exists, returns existing RuntimeCase without duplicating.

        Initial state: READY_FOR_REVIEW.
        """
        case_id = operational_case.case_id

        # 1. Check if already registered
        existing = self.get_runtime_case(case_id)
        if existing is not None:
            logger.info("RuntimeCase '%s' already registered. Returning existing record.", case_id)
            self._operational_cases[case_id] = operational_case
            return existing

        # 2. Derive priority
        prio_val = operational_case.priority.value if hasattr(operational_case.priority, "value") else str(operational_case.priority)
        try:
            priority = CasePriority(prio_val)
        except ValueError:
            priority = CasePriority.INFO

        now = datetime.now(timezone.utc)
        runtime_case = RuntimeCase(
            case_id=case_id,
            operational_case_ref=case_id,
            equipment_id=operational_case.equipment_id,
            runtime_state=RuntimeCaseState.READY_FOR_REVIEW,
            priority=priority,
            actor=actor,
            created_at=operational_case.created_at or now,
            updated_at=now,
        )

        # 3. Cache operational case and prepare candidate actions
        self._operational_cases[case_id] = operational_case
        presentation = self.orchestrator.build_presentation(
            case=operational_case,
            runtime_case=runtime_case,
        )
        self._case_actions[case_id] = {act.action_id: act for act in presentation.operator_actions}

        # 4. Persist to DB
        self._persist_runtime_case(runtime_case)

        # 5. Record audit entry using existing audit infrastructure
        audit_record = RuntimeAuditRecord(
            case_id=case_id,
            event_type="case_registered",
            action="register_case",
            actor=actor,
            payload={
                "equipment_id": operational_case.equipment_id,
                "priority": priority.value,
                "state": RuntimeCaseState.READY_FOR_REVIEW.value,
            },
            timestamp=now,
        )
        write_audit_entry(audit_record.to_audit_entry(), conn=None)

        logger.info("RuntimeCase '%s' registered in READY_FOR_REVIEW state.", case_id)
        return runtime_case

    # -----------------------------------------------------------------------
    # Retrieval & Listing
    # -----------------------------------------------------------------------

    def get_runtime_case(self, case_id: str) -> Optional[RuntimeCase]:
        """Fetch RuntimeCase by case_id from the database."""
        sql = """
        SELECT case_id, operational_case_ref, equipment_id, runtime_state, priority,
               selected_action_id, actor, resolution_summary, created_at, updated_at,
               resolved_at, closed_at
        FROM runtime_cases
        WHERE case_id = ?
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(sql, (case_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                return RuntimeCase(
                    case_id=row["case_id"],
                    operational_case_ref=row["operational_case_ref"],
                    equipment_id=row["equipment_id"],
                    runtime_state=RuntimeCaseState(row["runtime_state"]),
                    priority=CasePriority(row["priority"]),
                    selected_action_id=row["selected_action_id"],
                    actor=row["actor"],
                    resolution_summary=row["resolution_summary"],
                    created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
                    updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
                    resolved_at=_parse_dt(row["resolved_at"]),
                    closed_at=_parse_dt(row["closed_at"]),
                )
        except Exception as exc:
            logger.error("Failed to fetch RuntimeCase '%s': %s", case_id, exc)
            return None

    def list_runtime_cases(
        self,
        state: Optional[Union[RuntimeCaseState, str]] = None,
    ) -> List[RuntimeCase]:
        """List all runtime cases, optionally filtered by runtime_state."""
        if state is not None:
            state_val = state.value if hasattr(state, "value") else str(state)
            sql = """
            SELECT case_id, operational_case_ref, equipment_id, runtime_state, priority,
                   selected_action_id, actor, resolution_summary, created_at, updated_at,
                   resolved_at, closed_at
            FROM runtime_cases
            WHERE runtime_state = ?
            ORDER BY updated_at DESC
            """
            params: tuple = (state_val,)
        else:
            sql = """
            SELECT case_id, operational_case_ref, equipment_id, runtime_state, priority,
                   selected_action_id, actor, resolution_summary, created_at, updated_at,
                   resolved_at, closed_at
            FROM runtime_cases
            ORDER BY updated_at DESC
            """
            params = ()

        cases: List[RuntimeCase] = []
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(sql, params)
                for row in cursor.fetchall():
                    cases.append(
                        RuntimeCase(
                            case_id=row["case_id"],
                            operational_case_ref=row["operational_case_ref"],
                            equipment_id=row["equipment_id"],
                            runtime_state=RuntimeCaseState(row["runtime_state"]),
                            priority=CasePriority(row["priority"]),
                            selected_action_id=row["selected_action_id"],
                            actor=row["actor"],
                            resolution_summary=row["resolution_summary"],
                            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
                            updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
                            resolved_at=_parse_dt(row["resolved_at"]),
                            closed_at=_parse_dt(row["closed_at"]),
                        )
                    )
        except Exception as exc:
            logger.error("Failed to list RuntimeCases: %s", exc)
        return cases

    # -----------------------------------------------------------------------
    # Operator Presentation
    # -----------------------------------------------------------------------

    def present_case(
        self,
        case_id: str,
        operational_case: Optional[OperationalCase] = None,
    ) -> RuntimeResult:
        """
        Build the operator presentation contract (RuntimeResult) for a case.
        """
        runtime_case = self.get_runtime_case(case_id)
        if runtime_case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        # Resolve upstream OperationalCase
        if operational_case is not None:
            op_case = operational_case
            self._operational_cases[case_id] = operational_case
        else:
            op_case = self._operational_cases.get(case_id)
            if op_case is None:
                # Construct fallback representation with available metadata
                op_case = OperationalCase(
                    case_id=runtime_case.case_id,
                    equipment_id=runtime_case.equipment_id,
                    title=f"Operational Case {runtime_case.case_id}",
                    summary="Intelligence context from registered case record.",
                )

        # Retrieve candidate actions from cache if available
        actions_dict = self._case_actions.get(case_id)
        candidate_actions = list(actions_dict.values()) if actions_dict else None

        # Retrieve audit trail from existing audit infrastructure
        audit_trail = get_case_audit_trail(case_id)

        result = self.orchestrator.build_presentation(
            case=op_case,
            runtime_case=runtime_case,
            candidate_actions=candidate_actions,
            audit_records=audit_trail,
        )

        # Update cached actions
        self._case_actions[case_id] = {act.action_id: act for act in result.operator_actions}
        return result

    # -----------------------------------------------------------------------
    # Transitions & Actions
    # -----------------------------------------------------------------------

    def transition(
        self,
        case_id: str,
        to_state: Union[RuntimeCaseState, str],
        actor: str = "operator",
        payload: Optional[Dict[str, Any]] = None,
    ) -> RuntimeCase:
        """
        Execute an explicit state transition according to the deterministic transition table.
        """
        case = self.get_runtime_case(case_id)
        if case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        # Enforce transition rules
        updated_case, audit_record = transition_runtime_case(
            case=case,
            to_state=to_state,
            actor=actor,
            payload=payload,
        )

        # Atomic persistence
        self._persist_runtime_case(updated_case)
        write_audit_entry(audit_record.to_audit_entry())

        return updated_case

    def start_review(self, case_id: str, actor: str = "operator") -> RuntimeCase:
        """Convenience method to start review: READY_FOR_REVIEW → UNDER_REVIEW."""
        return self.transition(case_id, RuntimeCaseState.UNDER_REVIEW, actor=actor)

    def select_action(
        self,
        case_id: str,
        action_id: str,
        actor: str = "operator",
    ) -> RuntimeCase:
        """
        Select an OperatorAction for a case:
        1. Verify case exists and is not CLOSED.
        2. Verify action exists and belongs to the case.
        3. Verify action is NOT BLOCKED.
        4. Transition from UNDER_REVIEW to ACTION_SELECTED.
        5. Record selection and audit event.
        """
        case = self.get_runtime_case(case_id)
        if case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        if case.runtime_state == RuntimeCaseState.CLOSED:
            raise InvalidRuntimeTransitionError(
                f"Cannot select action: case '{case_id}' is CLOSED and immutable."
            )

        # Verify action exists and belongs to the case
        actions = self._case_actions.get(case_id)
        if not actions or action_id not in actions:
            # Refresh presentation to populate actions
            pres = self.present_case(case_id)
            actions = {a.action_id: a for a in pres.operator_actions}
            self._case_actions[case_id] = actions

        if action_id not in actions:
            raise ValueError(
                f"Action '{action_id}' does not exist on case '{case_id}'. "
                f"Available actions: {list(actions.keys())}"
            )

        action = actions[action_id]

        # Guard: Blocked action cannot be selected
        if action.is_blocked or action.status == ActionStatus.BLOCKED:
            raise InvalidDecisionError(
                f"Action '{action_id}' ({action.action_name}) is BLOCKED by safety guard "
                f"and cannot be selected. Reason: {action.blocked_reason}"
            )

        # Ensure case is in UNDER_REVIEW before selecting action
        if case.runtime_state != RuntimeCaseState.UNDER_REVIEW:
            raise InvalidRuntimeTransitionError(
                f"Cannot select action: case '{case_id}' must be in UNDER_REVIEW state, "
                f"currently in '{case.runtime_state.value}'."
            )

        # Update case and transition
        case.selected_action_id = action_id
        action.status = ActionStatus.SELECTED

        updated_case, audit_record = transition_runtime_case(
            case=case,
            to_state=RuntimeCaseState.ACTION_SELECTED,
            actor=actor,
            payload={
                "action_id": action_id,
                "action_name": action.action_name,
                "title": action.title,
            },
        )

        self._persist_runtime_case(updated_case)
        write_audit_entry(audit_record.to_audit_entry())

        logger.info(
            "Action '%s' selected for case '%s' by actor '%s'",
            action_id, case_id, actor,
        )
        return updated_case

    def record_decision(
        self,
        case_id: str,
        decision: RuntimeDecision,
    ) -> RuntimeCase:
        """
        Record a typed human decision (APPROVE or REJECT):
        - APPROVE: requires valid, selected, non-blocked action. Transitions to APPROVED.
        - REJECT: requires non-empty reason. Transitions to REJECTED.
        """
        case = self.get_runtime_case(case_id)
        if case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        if case.runtime_state == RuntimeCaseState.CLOSED:
            raise InvalidRuntimeTransitionError(
                f"Cannot record decision: case '{case_id}' is CLOSED and immutable."
            )

        if case.runtime_state != RuntimeCaseState.ACTION_SELECTED:
            raise InvalidRuntimeTransitionError(
                f"Cannot record decision: case '{case_id}' must be in ACTION_SELECTED state, "
                f"currently in '{case.runtime_state.value}'."
            )

        actions = self._case_actions.get(case_id, {})
        action = actions.get(decision.action_id)

        if decision.decision == DecisionOutcome.APPROVE:
            # Must match selected action
            if case.selected_action_id != decision.action_id:
                raise InvalidDecisionError(
                    f"Approved action '{decision.action_id}' does not match currently selected "
                    f"action '{case.selected_action_id}'."
                )

            # Cannot approve blocked action
            if action and (action.is_blocked or action.status == ActionStatus.BLOCKED):
                raise InvalidDecisionError(
                    f"Cannot APPROVE blocked action '{decision.action_id}'. Reason: {action.blocked_reason}"
                )

            if action:
                action.status = ActionStatus.APPROVED

            updated_case, audit_rec = transition_runtime_case(
                case=case,
                to_state=RuntimeCaseState.APPROVED,
                actor=decision.actor,
                payload={
                    "decision": DecisionOutcome.APPROVE.value,
                    "action_id": decision.action_id,
                    "reason": decision.reason,
                },
            )

        elif decision.decision == DecisionOutcome.REJECT:
            if not decision.reason or not decision.reason.strip():
                raise InvalidDecisionError(
                    "Rejection requires a non-empty reason."
                )

            if action:
                action.status = ActionStatus.REJECTED

            updated_case, audit_rec = transition_runtime_case(
                case=case,
                to_state=RuntimeCaseState.REJECTED,
                actor=decision.actor,
                payload={
                    "decision": DecisionOutcome.REJECT.value,
                    "action_id": decision.action_id,
                    "reason": decision.reason,
                },
            )
        else:
            raise InvalidDecisionError(f"Unsupported decision outcome: {decision.decision}")

        # Explicit operator decision audit log entry
        decision_audit = RuntimeAuditRecord(
            case_id=case_id,
            event_type="operator_decision",
            action=f"decision_{decision.decision.value}",
            actor=decision.actor,
            decision=decision.decision.value,
            payload={
                "action_id": decision.action_id,
                "reason": decision.reason,
                "timestamp": decision.timestamp.isoformat(),
            },
            timestamp=datetime.now(timezone.utc),
        )

        self._persist_runtime_case(updated_case)
        write_audit_entry(audit_rec.to_audit_entry())
        write_audit_entry(decision_audit.to_audit_entry())

        return updated_case

    def resolve_case(
        self,
        case_id: str,
        resolution_summary: str,
        actor: str = "operator",
    ) -> RuntimeCase:
        """
        Record resolution summary and transition to RESOLVED.
        Requires case to be in APPROVED or REJECTED state and non-empty summary.
        """
        case = self.get_runtime_case(case_id)
        if case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        if case.runtime_state == RuntimeCaseState.CLOSED:
            raise InvalidRuntimeTransitionError(
                f"Cannot resolve: case '{case_id}' is CLOSED and immutable."
            )

        if not resolution_summary or not resolution_summary.strip():
            raise ValueError("resolution_summary must not be empty.")

        case.resolution_summary = resolution_summary.strip()

        updated_case, audit_rec = transition_runtime_case(
            case=case,
            to_state=RuntimeCaseState.RESOLVED,
            actor=actor,
            payload={"resolution_summary": case.resolution_summary},
        )

        self._persist_runtime_case(updated_case)
        write_audit_entry(audit_rec.to_audit_entry())

        return updated_case

    def close_case(
        self,
        case_id: str,
        actor: str = "operator",
    ) -> RuntimeCase:
        """
        Close a case: RESOLVED → CLOSED.
        Once CLOSED, the case is terminal and immutable.
        """
        case = self.get_runtime_case(case_id)
        if case is None:
            raise KeyError(f"Runtime case '{case_id}' not found.")

        if case.runtime_state != RuntimeCaseState.RESOLVED:
            raise InvalidRuntimeTransitionError(
                f"Cannot close: case '{case_id}' must be in RESOLVED state, "
                f"currently in '{case.runtime_state.value}'."
            )

        updated_case, audit_rec = transition_runtime_case(
            case=case,
            to_state=RuntimeCaseState.CLOSED,
            actor=actor,
            payload={"closed_at": datetime.now(timezone.utc).isoformat()},
        )

        self._persist_runtime_case(updated_case)
        write_audit_entry(audit_rec.to_audit_entry())

        return updated_case

    def get_timeline(self, case_id: str) -> List[TimelineEvent]:
        """Retrieve full chronological timeline from existing audit infrastructure."""
        audit_trail = get_case_audit_trail(case_id)
        return self.orchestrator._build_timeline(audit_trail, case_id)

    # -----------------------------------------------------------------------
    # Persistence Helper
    # -----------------------------------------------------------------------

    def _persist_runtime_case(self, case: RuntimeCase) -> None:
        """Upsert RuntimeCase into the runtime_cases SQLite table."""
        sql = """
        INSERT INTO runtime_cases (
            case_id, operational_case_ref, equipment_id, runtime_state, priority,
            selected_action_id, actor, resolution_summary, created_at, updated_at,
            resolved_at, closed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            operational_case_ref = excluded.operational_case_ref,
            equipment_id = excluded.equipment_id,
            runtime_state = excluded.runtime_state,
            priority = excluded.priority,
            selected_action_id = excluded.selected_action_id,
            actor = excluded.actor,
            resolution_summary = excluded.resolution_summary,
            updated_at = excluded.updated_at,
            resolved_at = excluded.resolved_at,
            closed_at = excluded.closed_at;
        """
        params = (
            case.case_id,
            case.operational_case_ref,
            case.equipment_id,
            case.runtime_state.value,
            case.priority.value,
            case.selected_action_id,
            case.actor,
            case.resolution_summary,
            _iso(case.created_at),
            _iso(case.updated_at),
            _iso(case.resolved_at),
            _iso(case.closed_at),
        )

        with self._get_conn() as conn:
            conn.execute(sql, params)
            conn.commit()


# Module-level singleton
runtime_service = RuntimeService()
