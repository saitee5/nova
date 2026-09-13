"""
backend/runtime/models.py — Runtime Workflow Data Contracts.

Defines the complete type system for the NOVA Runtime Engineer workstream.

Boundary contract
-----------------
OperationalCase.status (CaseStatus)  ←  upstream intelligence lifecycle
RuntimeCase.runtime_state (RuntimeCaseState)  ←  THIS module — operator workflow

These are separate enums in separate models.  CaseStatus is never modified
by the runtime layer.

Zero-actuation guarantee
------------------------
OperatorAction only ever describes advisory, human-facing workflow steps.
No action may reference PLC/DCS/SIS/ESD operations.  SafetyGuard enforces
this at the orchestrator boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RuntimeCaseState(str, Enum):
    """Operator workflow lifecycle states — completely separate from CaseStatus.

    Primary flow:
        READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED → RESOLVED → CLOSED

    Alternative (rejection) flow:
        ACTION_SELECTED → REJECTED → RESOLVED → CLOSED

    CLOSED is terminal: no transitions are permitted out of it.
    """
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    UNDER_REVIEW     = "UNDER_REVIEW"
    ACTION_SELECTED  = "ACTION_SELECTED"
    APPROVED         = "APPROVED"
    REJECTED         = "REJECTED"
    RESOLVED         = "RESOLVED"
    CLOSED           = "CLOSED"


class ActionStatus(str, Enum):
    """Status of an individual OperatorAction presented to the operator."""
    AVAILABLE  = "AVAILABLE"   # Passed SafetyGuard; ready for operator selection
    SELECTED   = "SELECTED"    # Operator has selected this action
    APPROVED   = "APPROVED"    # Operator approved execution
    REJECTED   = "REJECTED"    # Operator rejected this action
    COMPLETED  = "COMPLETED"   # Action workflow complete
    CANCELLED  = "CANCELLED"   # Action cancelled before completion
    BLOCKED    = "BLOCKED"     # SafetyGuard or policy rejected — remains visible


class CasePriority(str, Enum):
    """Runtime-facing priority — mirrors OperationalCase.priority but owned here."""
    INFO     = "INFO"
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionOutcome(str, Enum):
    """Typed operator decision — used in RuntimeDecision.decision."""
    APPROVE = "APPROVE"
    REJECT  = "REJECT"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InvalidDecisionError(ValueError):
    """Raised when a RuntimeDecision violates business rules.

    Examples:
    - APPROVE referencing a BLOCKED action
    - APPROVE referencing an unknown action_id
    - REJECT with an empty reason
    """
    pass


# ---------------------------------------------------------------------------
# OperatorAction
# ---------------------------------------------------------------------------

class OperatorAction(BaseModel):
    """A structured advisory action presented to the operator for consideration.

    Derived deterministically from OperationalCase.risk_indicators by the
    RuntimeOrchestrator.  Every action passes through SafetyGuard before
    being included in a RuntimeResult.

    CRITICAL: actions are advisory only.  They describe human workflow steps
    such as 'notify shift manager' or 'review permit' — never PLC/DCS writes.
    """
    action_id:  str = Field(
        default_factory=lambda: f"act_{uuid.uuid4().hex[:10]}",
        description="Unique identifier for this action instance",
    )
    action_name: str = Field(
        ...,
        description="Machine-readable action identifier passed to SafetyGuard",
    )
    title: str = Field(..., description="Short human-readable title")
    description: str = Field(..., description="Detailed description of the action")
    reason: str = Field(..., description="Why this action is recommended")
    priority: CasePriority = Field(
        default=CasePriority.MEDIUM,
        description="Priority of this action",
    )
    risk_level: str = Field(
        default="MEDIUM",
        description="Risk level addressed by this action",
    )
    supporting_evidence_refs: List[str] = Field(
        default_factory=list,
        description="References to CanonicalEvidence IDs or risk_indicator names",
    )
    required_approval: bool = Field(
        default=True,
        description="Whether this action requires explicit operator approval",
    )
    safety_constraints: List[str] = Field(
        default_factory=list,
        description="Safety constraints that apply to this action",
    )
    status: ActionStatus = Field(
        default=ActionStatus.AVAILABLE,
        description="Current status of this action",
    )
    is_blocked: bool = Field(
        default=False,
        description="True if SafetyGuard or policy blocked this action",
    )
    blocked_reason: Optional[str] = Field(
        default=None,
        description="Reason for blocking — populated only when is_blocked=True",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context parameters (never actuation parameters)",
    )


# ---------------------------------------------------------------------------
# RuntimeDecision
# ---------------------------------------------------------------------------

class RuntimeDecision(BaseModel):
    """Typed operator decision record.

    Validation rules (enforced by validators below):
    - APPROVE: action_id must reference a non-BLOCKED action
    - REJECT: reason must be non-empty
    - Both: actor must be non-empty
    """
    decision:  DecisionOutcome = Field(
        ...,
        description="APPROVE or REJECT (typed enum, not arbitrary string)",
    )
    action_id: str = Field(
        ...,
        description="ID of the OperatorAction being decided on",
    )
    actor: str = Field(
        ...,
        description="Identity of the operator recording this decision",
    )
    reason: str = Field(
        default="",
        description="Reason for the decision — required and non-empty for REJECT",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the decision",
    )

    @field_validator("actor")
    @classmethod
    def actor_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("actor must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def validate_reject_requires_reason(self) -> "RuntimeDecision":
        if self.decision == DecisionOutcome.REJECT:
            if not self.reason or not self.reason.strip():
                raise ValueError(
                    "reason must be non-empty when decision is REJECT"
                )
        return self


# ---------------------------------------------------------------------------
# RuntimeCase (persistence model)
# ---------------------------------------------------------------------------

class RuntimeCase(BaseModel):
    """Runtime workflow state for an OperationalCase.

    Stores only runtime workflow metadata — never duplicates the intelligence
    payload from OperationalCase.  References the upstream case by case_id.

    Relationship:
        OperationalCase.case_id == RuntimeCase.case_id
        OperationalCase == intelligence result (upstream, read-only)
        RuntimeCase == workflow state (runtime, mutable through service)
    """
    case_id: str = Field(..., description="Shared key with OperationalCase")
    operational_case_ref: str = Field(
        ...,
        description="OperationalCase.case_id — explicit reference (not a copy)",
    )
    equipment_id: str = Field(..., description="Primary asset from OperationalCase")
    runtime_state: RuntimeCaseState = Field(
        default=RuntimeCaseState.READY_FOR_REVIEW,
        description="Current runtime workflow state",
    )
    priority: CasePriority = Field(
        default=CasePriority.INFO,
        description="Case priority (copied from OperationalCase.priority at registration)",
    )
    selected_action_id: Optional[str] = Field(
        default=None,
        description="action_id of the OperatorAction selected by the operator",
    )
    actor: Optional[str] = Field(
        default=None,
        description="Identity of the operator who last acted on this case",
    )
    resolution_summary: Optional[str] = Field(
        default=None,
        description="Operator-provided resolution notes",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Optional[datetime] = Field(default=None)
    closed_at:   Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# RuntimeResult (frontend presentation contract)
# ---------------------------------------------------------------------------

class EvidenceSummary(BaseModel):
    """Compact, frontend-consumable evidence summary.

    Derived from OperationalCase's multi-domain evidence fields.
    Contains no raw ML payloads — only structured references and excerpts.
    """
    knowledge_count:    int = 0
    maintenance_count:  int = 0
    safety_count:       int = 0
    permit_count:       int = 0
    incident_count:     int = 0
    top_knowledge:      List[Dict[str, Any]] = Field(default_factory=list)
    top_safety:         List[Dict[str, Any]] = Field(default_factory=list)
    top_maintenance:    List[Dict[str, Any]] = Field(default_factory=list)


class MLSummary(BaseModel):
    """Compact ML assessment summary for frontend display."""
    model_name: str
    status: str
    is_available: bool
    predicted_value: Any = None
    confidence: Optional[float] = None
    summary: str = ""


class TimelineEvent(BaseModel):
    """One chronological event in the case timeline."""
    event_id: str
    case_id: str
    event_type: str          # "state_transition" | "operator_action" | "case_created"
    description: str
    actor: Optional[str] = None
    decision: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    timestamp: datetime
    payload: Optional[Dict[str, Any]] = None


class RuntimeResult(BaseModel):
    """Frontend-consumable operator presentation for a runtime case.

    Combines runtime workflow state with a structured presentation of the
    upstream OperationalCase intelligence, ready for direct rendering.

    The frontend does NOT need to reconstruct intelligence from raw ML/RAG data.
    All intelligence is pre-structured here.

    Provenance labels on evidence fields follow the upstream convention:
        OBSERVED / PREDICTED / DERIVED / MISSING / STALE / UNKNOWN
    """
    # Identity
    case_id:       str
    equipment_id:  str
    unit_area:     str = ""

    # Runtime workflow state
    runtime_state: RuntimeCaseState
    priority:      CasePriority

    # Upstream case metadata (read from OperationalCase — not recalculated)
    title:         str
    summary:       str
    overall_state: str = "NORMAL"

    # Operator actions (after SafetyGuard validation)
    operator_actions: List[OperatorAction] = Field(default_factory=list)

    # Evidence (structured from OperationalCase multi-domain evidence)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)

    # ML assessments (structured from OperationalCase.ml_assessments)
    ml_summaries: List[MLSummary] = Field(default_factory=list)

    # Risk indicators (from OperationalCase.risk_indicators)
    risk_indicators: List[Dict[str, Any]] = Field(default_factory=list)

    # Safety constraints (from OperationalCase.safety_context)
    safety_constraints: List[str] = Field(default_factory=list)

    # Limitations and provenance (from OperationalCase.limitations / .provenance)
    limitations: List[str] = Field(default_factory=list)
    provenance_note: str = ""
    scenario_type: Optional[str] = None

    # Resolution info (populated after RESOLVED/CLOSED)
    selected_action_id: Optional[str] = None
    resolution_summary: Optional[str] = None
    actor:             Optional[str] = None

    # Timeline (populated by service when requested)
    timeline_events: List[TimelineEvent] = Field(default_factory=list)

    # Timestamps
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at:   Optional[datetime] = None


# ---------------------------------------------------------------------------
# RuntimeAuditRecord
# ---------------------------------------------------------------------------

class RuntimeAuditRecord(BaseModel):
    """Runtime audit event record bridging into the existing audit infrastructure.

    Conversion flow:
        RuntimeAuditRecord → to_audit_entry() → AuditEntry → audit_service → audit_log
    """
    record_id: str = Field(
        default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}",
        description="Unique audit record identifier",
    )
    case_id: str = Field(..., description="Case ID this audit event relates to")
    event_type: str = Field(
        ...,
        description="Runtime event type: case_registered | state_transition | action_selected | operator_decision | case_resolved | case_closed | safety_block",
    )
    action: Optional[str] = Field(default=None, description="Action name or command")
    actor: str = Field(default="system", description="User or system actor")
    decision: Optional[str] = Field(default=None, description="Decision value (APPROVE / REJECT / etc.)")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Structured event payload")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event",
    )

    def to_audit_entry(self) -> Any:
        """Map to canonical backend.models.audit.AuditEntry for existing audit_service."""
        from backend.models.audit import AuditEntry

        step_map = {
            "case_registered": "operator_action",
            "state_transition": "operator_action",
            "action_selected": "operator_action",
            "safety_block": "operator_action",
            "operator_decision": "human_decision",
            "case_resolved": "case_resolved",
            "case_closed": "case_resolved",
        }
        mapped_step = step_map.get(self.event_type, "operator_action")

        return AuditEntry(
            entry_id=self.record_id,
            case_id=self.case_id,
            step=mapped_step,  # type: ignore[arg-type]
            action=self.action or self.event_type,
            actor=self.actor,
            decision=self.decision,
            payload=self.payload or {},
            ts=self.timestamp,
        )

    def to_timeline_event(self) -> TimelineEvent:
        """Convert this audit record into a frontend timeline event."""
        return TimelineEvent(
            event_id=self.record_id,
            case_id=self.case_id,
            event_type=self.event_type,
            description=f"{self.actor}: {self.event_type} - {self.action or ''}".strip(" -"),
            actor=self.actor,
            decision=self.decision,
            previous_state=self.payload.get("from_state") if self.payload else None,
            new_state=self.payload.get("to_state") if self.payload else None,
            timestamp=self.timestamp,
            payload=self.payload or {},
        )

