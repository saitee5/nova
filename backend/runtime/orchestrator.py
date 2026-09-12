"""
backend/runtime/orchestrator.py — Runtime Orchestrator for Operator Workflows.

The RuntimeOrchestrator is a pure workflow and presentation adapter.
It consumes an OperationalCase (the read-only upstream intelligence product)
and produces a structured, frontend-ready RuntimeResult.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Pure Consumer: Never reruns ML models, RAG retrieval, risk calculation, or episode correlation.
2. Safety Guard Enforcement: Every proposed OperatorAction passes through SafetyGuard.
   Prohibited control attempts are flagged as BLOCKED with reason and NEVER silently removed.
3. Zero Actuation: No PLC, DCS, SIS, ESD, valve, actuator, or setpoint writes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.operational_context.models import OperationalCase
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.runtime.models import (
    ActionStatus,
    CasePriority,
    EvidenceSummary,
    MLSummary,
    OperatorAction,
    RuntimeCase,
    RuntimeCaseState,
    RuntimeResult,
    TimelineEvent,
)

logger = logging.getLogger("nova.runtime.orchestrator")


class RuntimeOrchestrator:
    """
    Workflow presentation adapter transforming an OperationalCase into a RuntimeResult.
    """

    def __init__(self, guard: Any = None) -> None:
        self.guard = guard or safety_guard

    def build_presentation(
        self,
        case: OperationalCase,
        runtime_case: Optional[RuntimeCase] = None,
        candidate_actions: Optional[List[OperatorAction]] = None,
        audit_records: Optional[List[Any]] = None,
    ) -> RuntimeResult:
        """
        Build the complete frontend-facing RuntimeResult from an OperationalCase.

        Args:
            case: Upstream OperationalCase (intelligence product).
            runtime_case: Current runtime workflow state (if registered).
            candidate_actions: Optional explicitly provided actions to evaluate.
            audit_records: Audit log entries for populating timeline events.

        Returns:
            RuntimeResult ready for operator UI presentation.
        """
        # 1. Determine workflow state and metadata from RuntimeCase or default
        runtime_state = runtime_case.runtime_state if runtime_case else RuntimeCaseState.READY_FOR_REVIEW
        selected_action_id = runtime_case.selected_action_id if runtime_case else None
        resolution_summary = runtime_case.resolution_summary if runtime_case else None
        actor = runtime_case.actor if runtime_case else None
        created_at = runtime_case.created_at if runtime_case else case.created_at
        updated_at = runtime_case.updated_at if runtime_case else case.updated_at
        resolved_at = runtime_case.resolved_at if runtime_case else None
        closed_at = runtime_case.closed_at if runtime_case else None

        # Map priority
        priority_val = case.priority.value if hasattr(case.priority, "value") else str(case.priority)
        try:
            priority = CasePriority(priority_val)
        except ValueError:
            priority = CasePriority.INFO

        # 2. Summarize evidence without re-querying RAG
        evidence_summary = self._summarize_evidence(case)

        # 3. Summarize ML assessments without re-running ML models
        ml_summaries = self._summarize_ml(case)

        # 4. Extract risk indicators & safety constraints
        risk_indicators = [
            ind.model_dump() if hasattr(ind, "model_dump") else dict(ind)
            for ind in getattr(case, "risk_indicators", [])
        ]

        safety_constraints = self._extract_safety_constraints(case)

        # 5. Derive or take candidate actions and run them through SafetyGuard
        actions = self._prepare_actions(
            case=case,
            candidate_actions=candidate_actions,
            selected_action_id=selected_action_id,
            runtime_state=runtime_state,
        )

        # 6. Build timeline events from audit records
        timeline_events = self._build_timeline(audit_records or [], case.case_id)

        # 7. Assemble final RuntimeResult
        return RuntimeResult(
            case_id=case.case_id,
            equipment_id=case.equipment_id,
            unit_area=case.unit_area or "",
            runtime_state=runtime_state,
            priority=priority,
            title=case.title or f"Operational Case for {case.equipment_id}",
            summary=case.summary or "",
            overall_state=case.overall_state or "NORMAL",
            operator_actions=actions,
            evidence_summary=evidence_summary,
            ml_summaries=ml_summaries,
            risk_indicators=risk_indicators,
            safety_constraints=safety_constraints,
            limitations=getattr(case, "limitations", []),
            provenance_note=getattr(case, "scenario_type", "") or "Operational Intelligence Context",
            scenario_type=getattr(case, "scenario_type", None),
            selected_action_id=selected_action_id,
            resolution_summary=resolution_summary,
            actor=actor,
            timeline_events=timeline_events,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            closed_at=closed_at,
        )

    def _summarize_evidence(self, case: OperationalCase) -> EvidenceSummary:
        """Extract evidence counts and top snippets from existing CanonicalEvidence."""
        knowledge_ev = getattr(case, "knowledge_evidence", []) or []
        maint_ev = getattr(case, "maintenance_context", []) or []
        safety_ev = getattr(case, "safety_context", []) or []
        permit_ev = getattr(case, "permit_context", []) or []
        incident_ev = getattr(case, "incident_context", []) or []

        def _top_items(ev_list: List[Any], limit: int = 3) -> List[Dict[str, Any]]:
            items = []
            for ev in ev_list[:limit]:
                items.append({
                    "source_id": getattr(ev, "source_id", ""),
                    "title": getattr(ev, "title", ""),
                    "excerpt": (getattr(ev, "content", "") or "")[:200],
                    "evidence_type": getattr(getattr(ev, "evidence_type", None), "value", "DOCUMENT"),
                })
            return items

        return EvidenceSummary(
            knowledge_count=len(knowledge_ev),
            maintenance_count=len(maint_ev),
            safety_count=len(safety_ev),
            permit_count=len(permit_ev),
            incident_count=len(incident_ev),
            top_knowledge=_top_items(knowledge_ev),
            top_safety=_top_items(safety_ev),
            top_maintenance=_top_items(maint_ev),
        )

    def _summarize_ml(self, case: OperationalCase) -> List[MLSummary]:
        """Convert existing MLAssessmentSummary records without running inference."""
        ml_assessments = getattr(case, "ml_assessments", {}) or {}
        summaries: List[MLSummary] = []
        for name, assess in ml_assessments.items():
            summaries.append(
                MLSummary(
                    model_name=getattr(assess, "model_name", name),
                    status=getattr(assess, "status", "UNKNOWN"),
                    is_available=getattr(assess, "is_available", False),
                    predicted_value=getattr(assess, "predicted_value", None),
                    confidence=getattr(assess, "confidence", None),
                    summary=getattr(assess, "summary", ""),
                )
            )
        return summaries

    def _extract_safety_constraints(self, case: OperationalCase) -> List[str]:
        """Extract explicit safety and permit constraints from multi-domain evidence."""
        constraints: List[str] = []
        safety_ev = getattr(case, "safety_context", []) or []
        for ev in safety_ev:
            title = getattr(ev, "title", "")
            if title and title not in constraints:
                constraints.append(f"Safety: {title}")

        permit_ev = getattr(case, "permit_context", []) or []
        for ev in permit_ev:
            title = getattr(ev, "title", "")
            if title and title not in constraints:
                constraints.append(f"Permit Requirement: {title}")

        if not constraints:
            constraints.append("Standard plant PPE and LOTO isolation requirements apply.")

        return constraints

    def _prepare_actions(
        self,
        case: OperationalCase,
        candidate_actions: Optional[List[OperatorAction]],
        selected_action_id: Optional[str],
        runtime_state: RuntimeCaseState,
    ) -> List[OperatorAction]:
        """
        Derive advisory actions from risk indicators and evaluate through SafetyGuard.
        Blocked actions are retained with is_blocked=True and blocked_reason.
        """
        raw_candidates = list(candidate_actions) if candidate_actions is not None else []

        if not raw_candidates:
            # Derive deterministic advisory actions from indicators and priority
            raw_candidates = self._derive_advisory_actions(case)

        evaluated_actions: List[OperatorAction] = []

        for act in raw_candidates:
            # Validate through SafetyGuard
            try:
                self.guard.validate_action(act.action_name, act.parameters)
                # Passed safety guard
                if not act.is_blocked:
                    act.is_blocked = False
                    act.blocked_reason = None
                    # Update status based on selection / runtime state
                    if selected_action_id and act.action_id == selected_action_id:
                        if runtime_state == RuntimeCaseState.APPROVED:
                            act.status = ActionStatus.APPROVED
                        elif runtime_state == RuntimeCaseState.REJECTED:
                            act.status = ActionStatus.REJECTED
                        else:
                            act.status = ActionStatus.SELECTED
                    elif act.status == ActionStatus.BLOCKED:
                        act.status = ActionStatus.AVAILABLE
            except DirectControlAttemptError as exc:
                # Intercepted! Retain action visible as BLOCKED
                act.is_blocked = True
                act.status = ActionStatus.BLOCKED
                act.blocked_reason = str(exc)
                logger.warning(
                    "SafetyGuard blocked action '%s' on case '%s': %s",
                    act.action_name, case.case_id, exc,
                )

            evaluated_actions.append(act)

        return evaluated_actions

    def _derive_advisory_actions(self, case: OperationalCase) -> List[OperatorAction]:
        """Derive structured advisory actions from operational risk indicators."""
        actions: List[OperatorAction] = []
        indicators = getattr(case, "risk_indicators", []) or []

        # Map each indicator to an advisory action
        for ind in indicators:
            ind_name = getattr(ind, "name", "")
            ind_desc = getattr(ind, "description", "")
            severity = getattr(ind, "severity", CasePriority.MEDIUM)
            prio_val = severity.value if hasattr(severity, "value") else str(severity)
            try:
                prio = CasePriority(prio_val)
            except ValueError:
                prio = CasePriority.MEDIUM

            if "cot" in ind_name.lower() or "temperature" in ind_name.lower():
                actions.append(
                    OperatorAction(
                        action_name="advisory_inspect_firing_balance",
                        title=f"Inspect Burner Balance on {case.equipment_id}",
                        description=(
                            f"Perform immediate visual burner inspection on {case.equipment_id}, check draft pressure, "
                            "and verify dilution steam ratio against SOP-F201-001."
                        ),
                        reason=ind_desc or "Thermal limit excursion indicated by telemetry/models.",
                        priority=prio,
                        risk_level="HIGH" if prio in (CasePriority.HIGH, CasePriority.CRITICAL) else "MEDIUM",
                        supporting_evidence_refs=[ind_name],
                        required_approval=True,
                        safety_constraints=["PPE High-Temp Zone required", "Observe LOTO protocol before opening dampers"],
                    )
                )
            elif "fault" in ind_name.lower() or "anomaly" in ind_name.lower():
                actions.append(
                    OperatorAction(
                        action_name="advisory_diagnose_process_upset",
                        title=f"Investigate Process Anomaly on {case.equipment_id}",
                        description=(
                            f"Review redundant sensor instrumentation on {case.equipment_id}, verify valve feed alignment, "
                            "and notify shift lead of detected deviation."
                        ),
                        reason=ind_desc or "Process fault pattern identified.",
                        priority=prio,
                        risk_level="MEDIUM",
                        supporting_evidence_refs=[ind_name],
                        required_approval=True,
                    )
                )

        # Baseline fallback if no specific indicator action was generated
        if not actions:
            actions.append(
                OperatorAction(
                    action_name="advisory_baseline_monitoring",
                    title=f"Routine Surveillance on {case.equipment_id}",
                    description=f"Maintain standard DCS scan and log parameter trends for {case.equipment_id}.",
                    reason="Operating parameters within normal envelope or undergoing initial review.",
                    priority=CasePriority.INFO,
                    risk_level="LOW",
                    required_approval=False,
                )
            )

        return actions

    def _build_timeline(self, audit_records: List[Any], case_id: str) -> List[TimelineEvent]:
        """Convert audit records or entries into chronological timeline events."""
        events: List[TimelineEvent] = []
        for r in audit_records:
            if hasattr(r, "to_timeline_event"):
                events.append(r.to_timeline_event())
            elif hasattr(r, "entry_id"):
                # Handle AuditEntry instance
                payload = getattr(r, "payload", {}) or {}
                events.append(
                    TimelineEvent(
                        event_id=getattr(r, "entry_id", ""),
                        case_id=getattr(r, "case_id", case_id),
                        event_type=getattr(r, "step", "operator_action"),
                        description=f"{getattr(r, 'actor', 'system')}: {getattr(r, 'action', '')}".strip(),
                        actor=getattr(r, "actor", None),
                        decision=getattr(r, "decision", None),
                        previous_state=payload.get("from_state") if isinstance(payload, dict) else None,
                        new_state=payload.get("to_state") if isinstance(payload, dict) else None,
                        timestamp=getattr(r, "ts", datetime.now(timezone.utc)),
                        payload=payload if isinstance(payload, dict) else None,
                    )
                )
            elif isinstance(r, dict):
                events.append(
                    TimelineEvent(
                        event_id=str(r.get("id") or r.get("entry_id") or ""),
                        case_id=r.get("case_id", case_id),
                        event_type=r.get("step") or r.get("action") or "operator_action",
                        description=f"{r.get('actor', 'system')}: {r.get('action', '')}".strip(),
                        actor=r.get("actor"),
                        decision=r.get("decision"),
                        timestamp=r.get("ts") or datetime.now(timezone.utc),
                        payload=r.get("payload") if isinstance(r.get("payload"), dict) else None,
                    )
                )
        return events


# Module-level singleton
runtime_orchestrator = RuntimeOrchestrator()
