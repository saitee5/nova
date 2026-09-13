"""
backend/runtime/__init__.py — NOVA Runtime Engineer Workstream.

Provides the human-in-the-loop operator workflow layer that consumes
an OperationalCase (status=READY_FOR_REVIEW) and orchestrates:

    OperationalCase
          ↓
    RuntimeOrchestrator
          ↓
    RuntimeResult (operator presentation)
          ↓
    READY_FOR_REVIEW → UNDER_REVIEW → ACTION_SELECTED
                                    ↓           ↓
                                APPROVED     REJECTED
                                    ↓           ↓
                                RESOLVED ← RESOLVED
                                    ↓
                                 CLOSED

Zero-actuation guarantee: runtime never writes to PLC/DCS/SIS/ESD.
"""
from __future__ import annotations

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
)
from backend.runtime.state_machine import (
    RUNTIME_TRANSITIONS,
    InvalidRuntimeTransitionError,
    transition_runtime_case,
)
from backend.runtime.orchestrator import RuntimeOrchestrator, runtime_orchestrator
from backend.runtime.service import RuntimeService, runtime_service

__all__ = [
    # Models
    "RuntimeCaseState",
    "ActionStatus",
    "CasePriority",
    "OperatorAction",
    "DecisionOutcome",
    "InvalidDecisionError",
    "RuntimeDecision",
    "RuntimeCase",
    "RuntimeResult",
    "RuntimeAuditRecord",
    # State machine
    "RUNTIME_TRANSITIONS",
    "InvalidRuntimeTransitionError",
    "transition_runtime_case",
    # Orchestrator
    "RuntimeOrchestrator",
    "runtime_orchestrator",
    # Service
    "RuntimeService",
    "runtime_service",
]

