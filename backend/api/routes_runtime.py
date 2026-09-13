"""
backend/api/routes_runtime.py — REST API for the Runtime Operator Workflow.

Exposes endpoints for the human-in-the-loop operator workflow:
- GET  /api/runtime/cases                   → List runtime cases
- GET  /api/runtime/cases/{case_id}         → Present case (RuntimeResult)
- POST /api/runtime/cases/{case_id}/transition     → State machine transition
- POST /api/runtime/cases/{case_id}/select-action → Select an advisory action
- POST /api/runtime/cases/{case_id}/decision      → Submit typed decision (APPROVE/REJECT)
- POST /api/runtime/cases/{case_id}/resolve       → Resolve case with notes
- POST /api/runtime/cases/{case_id}/close         → Close case (terminal)
- GET  /api/runtime/cases/{case_id}/timeline      → Case timeline events
- GET  /api/runtime/cases/{case_id}/audit         → Audit trail
- POST /api/runtime/cases/register                → Ingest OperationalCase
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.operational_context.models import OperationalCase
from backend.runtime.models import (
    DecisionOutcome,
    InvalidDecisionError,
    RuntimeCase,
    RuntimeCaseState,
    RuntimeDecision,
    RuntimeResult,
    TimelineEvent,
)
from backend.runtime.service import runtime_service
from backend.runtime.state_machine import InvalidRuntimeTransitionError
from backend.services.audit_service import get_case_audit_trail

logger = logging.getLogger("nova.api.runtime")

router = APIRouter(prefix="/runtime", tags=["runtime"])


# ---------------------------------------------------------------------------
# Request Bodies
# ---------------------------------------------------------------------------

class TransitionRequest(BaseModel):
    to_state: str = Field(..., description="Target RuntimeCaseState string")
    actor: str = Field(default="operator", description="Operator identity")


class SelectActionRequest(BaseModel):
    action_id: str = Field(..., description="action_id of the OperatorAction to select")
    actor: str = Field(default="operator", description="Operator identity")


class DecisionRequest(BaseModel):
    decision: DecisionOutcome = Field(..., description="APPROVE or REJECT")
    action_id: str = Field(..., description="action_id being decided upon")
    actor: str = Field(..., description="Operator identity (cannot be empty)")
    reason: str = Field(default="", description="Mandatory non-empty reason for REJECT")


class ResolveRequest(BaseModel):
    resolution_summary: str = Field(..., description="Mandatory resolution notes")
    actor: str = Field(default="operator", description="Operator identity")


class CloseRequest(BaseModel):
    actor: str = Field(default="operator", description="Operator identity")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/cases", response_model=List[RuntimeCase])
async def list_cases(
    state: Optional[str] = Query(default=None, description="Filter by RuntimeCaseState"),
) -> List[RuntimeCase]:
    """List all runtime cases, optionally filtered by state."""
    try:
        cases = runtime_service.list_runtime_cases(state=state)
        if not cases and state is None:
            from backend.operational_context.models import OperationalCase
            from backend.runtime.models import CasePriority
            default_case = OperationalCase(
                case_id="CASE-2026-F201A-01",
                equipment_id="F-201A",
                equipment_type="furnace",
                unit_area="UNIT-CRACK-01",
                title="Pyrolysis Furnace Thermal Overload & Compressor Risk",
                summary="Elevated tube skin temperatures detected on Pass 4 of Cracker Furnace F-201A with associated acoustic vibration signatures.",
                priority=CasePriority.HIGH,
                risk_indicators=[
                    {"name": "tube_temperature", "value": 1064.2, "status": "CRITICAL", "unit": "°C"},
                    {"name": "pass_4_dp", "value": 3.8, "status": "ELEVATED", "unit": "bar"},
                    {"name": "burner_acoustic", "value": 5.6, "status": "WARNING", "unit": "mm/s"},
                ],
                safety_context={"interlock_margin": "19.2°C to safety shutdown", "simops": "Hot work permit active in adjacent Bay 3"},
            )
            runtime_service.register_case(default_case)
            cases = runtime_service.list_runtime_cases()
        return cases
    except Exception as exc:
        logger.error("Failed to list runtime cases: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/register", response_model=RuntimeCase)
async def register_case(case: OperationalCase) -> RuntimeCase:
    """Register an upstream OperationalCase into the runtime layer."""
    try:
        return runtime_service.register_case(case)
    except Exception as exc:
        logger.error("Failed to register case '%s': %s", case.case_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/cases/{case_id}", response_model=RuntimeResult)
async def get_case(case_id: str) -> RuntimeResult:
    """Retrieve the full frontend presentation for a runtime case."""
    try:
        return runtime_service.present_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to present case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/{case_id}/transition", response_model=RuntimeCase)
async def transition_case(case_id: str, req: TransitionRequest) -> RuntimeCase:
    """Execute an explicit state transition on a case."""
    try:
        return runtime_service.transition(case_id, req.to_state, actor=req.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidRuntimeTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to transition case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/{case_id}/select-action", response_model=RuntimeCase)
async def select_action(case_id: str, req: SelectActionRequest) -> RuntimeCase:
    """Select an advisory action for a case under review."""
    try:
        return runtime_service.select_action(case_id, req.action_id, actor=req.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidDecisionError, InvalidRuntimeTransitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to select action on case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/{case_id}/decision", response_model=RuntimeCase)
async def record_decision(case_id: str, req: DecisionRequest) -> RuntimeCase:
    """Record a human operator decision (APPROVE / REJECT)."""
    try:
        decision = RuntimeDecision(
            decision=req.decision,
            action_id=req.action_id,
            actor=req.actor,
            reason=req.reason,
        )
        return runtime_service.record_decision(case_id, decision)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidDecisionError, InvalidRuntimeTransitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to record decision on case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/{case_id}/resolve", response_model=RuntimeCase)
async def resolve_case(case_id: str, req: ResolveRequest) -> RuntimeCase:
    """Record resolution notes and transition case to RESOLVED."""
    try:
        return runtime_service.resolve_case(case_id, req.resolution_summary, actor=req.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidRuntimeTransitionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to resolve case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cases/{case_id}/close", response_model=RuntimeCase)
async def close_case(case_id: str, req: CloseRequest) -> RuntimeCase:
    """Close a resolved case. CLOSED is terminal and immutable."""
    try:
        return runtime_service.close_case(case_id, actor=req.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidRuntimeTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to close case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cases/{case_id}/timeline", response_model=List[TimelineEvent])
async def get_timeline(case_id: str) -> List[TimelineEvent]:
    """Retrieve the chronological timeline of events for a case."""
    try:
        return runtime_service.get_timeline(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to get timeline for case '%s': %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cases/{case_id}/audit", response_model=List[Dict[str, Any]])
async def get_audit(case_id: str) -> List[Dict[str, Any]]:
    """Retrieve raw audit trail entries for a case from existing audit infrastructure."""
    entries = get_case_audit_trail(case_id)
    return [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in entries]
