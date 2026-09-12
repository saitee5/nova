"""
backend/runtime/state_machine.py — Deterministic State Machine for Runtime Cases.

Enforces strict, unidirectional lifecycle transitions for operator workflows.
CLOSED is terminal and immutable.
Arbitrary jumps or backwards transitions raise InvalidRuntimeTransitionError.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.runtime.models import (
    RuntimeAuditRecord,
    RuntimeCase,
    RuntimeCaseState,
)

logger = logging.getLogger("nova.runtime.state_machine")


class InvalidRuntimeTransitionError(ValueError):
    """Raised when an invalid state transition is attempted on a RuntimeCase."""
    pass


# ---------------------------------------------------------------------------
# Transition Table
# ---------------------------------------------------------------------------

RUNTIME_TRANSITIONS: Dict[RuntimeCaseState, List[RuntimeCaseState]] = {
    # Primary flow:
    # READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED → APPROVED → RESOLVED → CLOSED
    RuntimeCaseState.READY_FOR_REVIEW: [RuntimeCaseState.UNDER_REVIEW],
    RuntimeCaseState.UNDER_REVIEW:     [RuntimeCaseState.ACTION_SELECTED],
    RuntimeCaseState.ACTION_SELECTED:  [RuntimeCaseState.APPROVED, RuntimeCaseState.REJECTED],
    RuntimeCaseState.APPROVED:         [RuntimeCaseState.RESOLVED],
    # Alternative rejection flow:
    # ACTION_SELECTED → REJECTED → RESOLVED → CLOSED
    RuntimeCaseState.REJECTED:         [RuntimeCaseState.RESOLVED],
    RuntimeCaseState.RESOLVED:         [RuntimeCaseState.CLOSED],
    # CLOSED is terminal:
    RuntimeCaseState.CLOSED:           [],
}


def transition_runtime_case(
    case: RuntimeCase,
    to_state: Union[RuntimeCaseState, str],
    actor: str = "operator",
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[RuntimeCase, RuntimeAuditRecord]:
    """
    Validate and execute a deterministic state transition on a RuntimeCase.

    Args:
        case: Current RuntimeCase instance.
        to_state: Target RuntimeCaseState (or valid enum string value).
        actor: Identity of the operator or system initiating the transition.
        payload: Additional audit payload dictionary.

    Returns:
        Tuple of (updated_case, audit_record).

    Raises:
        InvalidRuntimeTransitionError: If the transition is illegal or violates guards.
    """
    # Parse target state
    if isinstance(to_state, str):
        try:
            target_state = RuntimeCaseState(to_state)
        except ValueError:
            raise InvalidRuntimeTransitionError(
                f"Unknown target state '{to_state}'. Valid states are: "
                f"{[s.value for s in RuntimeCaseState]}"
            )
    else:
        target_state = to_state

    current_state = case.runtime_state

    # 1. Guard against any transitions from CLOSED (terminal & immutable)
    if current_state == RuntimeCaseState.CLOSED:
        raise InvalidRuntimeTransitionError(
            f"Case '{case.case_id}' is CLOSED and terminal. No transitions are permitted out of CLOSED."
        )

    # 2. Check transition validity against the explicit transition table
    allowed_states = RUNTIME_TRANSITIONS.get(current_state, [])
    if target_state not in allowed_states:
        raise InvalidRuntimeTransitionError(
            f"Invalid state transition for case '{case.case_id}': "
            f"cannot transition from '{current_state.value}' to '{target_state.value}'. "
            f"Allowed next states: {[s.value for s in allowed_states]}"
        )

    # 3. Specific transition guards
    if target_state == RuntimeCaseState.APPROVED:
        if not case.selected_action_id:
            raise InvalidRuntimeTransitionError(
                f"Cannot transition case '{case.case_id}' to APPROVED without a selected action. "
                "selected_action_id must be set."
            )

    if target_state == RuntimeCaseState.RESOLVED:
        if current_state not in (RuntimeCaseState.APPROVED, RuntimeCaseState.REJECTED):
            raise InvalidRuntimeTransitionError(
                f"Cannot transition case '{case.case_id}' to RESOLVED from '{current_state.value}'. "
                "Case must be in APPROVED or REJECTED state before resolution."
            )

    # 4. Perform the transition
    now = datetime.now(timezone.utc)
    case.runtime_state = target_state
    case.updated_at = now
    if actor:
        case.actor = actor

    if target_state == RuntimeCaseState.RESOLVED:
        case.resolved_at = now
    elif target_state == RuntimeCaseState.CLOSED:
        case.closed_at = now

    # 5. Create the matching audit record
    audit_record = RuntimeAuditRecord(
        case_id=case.case_id,
        event_type="state_transition",
        action=f"transition_to_{target_state.value}",
        actor=actor,
        decision=target_state.value if target_state in (RuntimeCaseState.APPROVED, RuntimeCaseState.REJECTED) else None,
        payload={
            "from_state": current_state.value,
            "to_state": target_state.value,
            "selected_action_id": case.selected_action_id,
            **(payload or {}),
        },
        timestamp=now,
    )

    logger.info(
        "RuntimeCase '%s' transitioned: %s → %s by actor '%s'",
        case.case_id, current_state.value, target_state.value, actor,
    )
    return case, audit_record
