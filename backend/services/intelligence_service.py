"""
backend/services/intelligence_service.py — NOVA Intelligence Pipeline Service.

This is the top-level service that orchestrates the complete intelligence pipeline:

  Telemetry / Provider Data
        ↓
  ContextEngine.assemble()          → OperationalContextSnapshot
        ↓
  ContextRiskBridge.evaluate()      → IndustrialRiskAssessment
        ↓
  AgentOrchestrator.run()           → OrchestratedAdvisory
        ↓
  IntelligenceResult                → API response / NOVA response

Usage:
    result = intelligence_service.run(asset_id="F-201A")
    print(result.advisory.to_full_text())

Zero-Actuation Rule:
  This service is read-only / advisory. It never issues commands.
  SafetyGuard remains the policy enforcement boundary for all API outputs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.agents.industrial.orchestrator import AgentOrchestrator, OrchestratedAdvisory, agent_orchestrator
from backend.models.industrial_domain import IndustrialRiskAssessment
from backend.services.context_engine import ContextEngine, OperationalContextSnapshot, context_engine
from backend.services.context_risk_bridge import ContextRiskBridge, context_risk_bridge

logger = logging.getLogger("nova.intelligence_service")


class IntelligenceResult(BaseModel):
    """
    The complete intelligence pipeline output for one asset evaluation.

    This is the typed output of IntelligenceService.run() — the single
    object returned by the /intelligence/* API routes.
    """
    model_config = {"arbitrary_types_allowed": True}

    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    error: Optional[str] = None

    # Pipeline outputs
    context: Optional[OperationalContextSnapshot] = None
    risk_assessment: Optional[IndustrialRiskAssessment] = None
    advisory: Optional[OrchestratedAdvisory] = None

    # Pipeline timing
    context_duration_ms: float = 0.0
    risk_duration_ms: float = 0.0
    agent_duration_ms: float = 0.0
    total_duration_ms: float = 0.0

    def to_api_dict(self) -> Dict[str, Any]:
        """Serialize to API-safe dict (excludes large ML evidence arrays by default)."""
        out: Dict[str, Any] = {
            "run_id": self.run_id,
            "asset_id": self.asset_id,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "timing_ms": {
                "context": self.context_duration_ms,
                "risk": self.risk_duration_ms,
                "agents": self.agent_duration_ms,
                "total": self.total_duration_ms,
            },
        }
        if self.error:
            out["error"] = self.error
        if self.risk_assessment:
            out["risk"] = {
                "risk_score": self.risk_assessment.risk_score,
                "risk_tier": self.risk_assessment.risk_tier.value if self.risk_assessment.risk_tier else None,
                "recommendations": self.risk_assessment.recommended_actions,
                "factors": self.risk_assessment.factors,
            }
        if self.advisory:
            out["advisory"] = {
                "orchestration_id": self.advisory.orchestration_id,
                "overall_severity": self.advisory.overall_severity.value,
                "is_safety_critical": self.advisory.is_safety_critical,
                "headline": self.advisory.headline,
                "agents": [
                    {
                        "agent": a.agent_name,
                        "severity": a.severity.value,
                        "headline": a.headline,
                        "key_findings": a.key_findings,
                        "recommendations": a.recommendations,
                    }
                    for a in self.advisory.advisories
                ],
                "summary_text": self.advisory.to_summary_text(),
            }
        if self.context:
            out["context_summary"] = {
                "context_id": self.context.context_id,
                "providers_used": self.context.providers_used,
                "operating_mode": self.context.operating_mode.value,
                "active_alarms": len(self.context.active_alarms),
                "active_maintenance": len(self.context.active_maintenance),
                "active_permits": len(self.context.active_permits),
                "ml_available": self.context.ml_summary is not None,
                "warnings": self.context.warnings,
                "assembly_duration_ms": self.context.assembly_duration_ms,
            }
        return out


class IntelligenceService:
    """
    NOVA Intelligence Pipeline Service.

    Orchestrates the full pipeline:
      ContextEngine → ContextRiskBridge → AgentOrchestrator → IntelligenceResult

    All components are injectable for testing and future provider upgrades.
    """

    def __init__(
        self,
        context_engine: Optional[ContextEngine] = None,
        risk_bridge: Optional[ContextRiskBridge] = None,
        orchestrator: Optional[AgentOrchestrator] = None,
    ) -> None:
        self._context_engine = context_engine
        self._risk_bridge = risk_bridge
        self._orchestrator = orchestrator

    @property
    def context_engine(self) -> ContextEngine:
        if self._context_engine is None:
            from backend.services.context_engine import context_engine as _ce
            self._context_engine = _ce
        return self._context_engine

    @property
    def risk_bridge(self) -> ContextRiskBridge:
        if self._risk_bridge is None:
            self._risk_bridge = context_risk_bridge
        return self._risk_bridge

    @property
    def orchestrator(self) -> AgentOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = agent_orchestrator
        return self._orchestrator

    def run(
        self,
        asset_id: str,
        telemetry_override: Optional[Dict[str, Any]] = None,
        query_hint: Optional[str] = None,
        include_knowledge: bool = True,
        include_history: bool = True,
    ) -> IntelligenceResult:
        """
        Execute the complete intelligence pipeline for the given asset.

        Args:
            asset_id:            Target asset (e.g. "F-201A")
            telemetry_override:  Supply telemetry directly (bypasses live provider)
            query_hint:          Override query string for knowledge/episode search
            include_knowledge:   Include knowledge retrieval
            include_history:     Include historical episode retrieval

        Returns:
            IntelligenceResult with context, risk, and advisory.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        t0 = datetime.now(timezone.utc)

        logger.info("IntelligenceService.run: run_id=%s asset=%s", run_id, asset_id)

        # ── Stage 1: Context Assembly ──────────────────────────────────────
        t_ctx_start = datetime.now(timezone.utc)
        context: Optional[OperationalContextSnapshot] = None
        try:
            context = self.context_engine.assemble(
                asset_id=asset_id,
                telemetry_override=telemetry_override,
                query_hint=query_hint,
                include_knowledge=include_knowledge,
                include_history=include_history,
            )
        except Exception as exc:
            logger.error("ContextEngine failed for %s: %s", asset_id, exc, exc_info=True)
            return IntelligenceResult(
                run_id=run_id,
                asset_id=asset_id,
                success=False,
                error=f"Context assembly failed: {exc}",
                total_duration_ms=_elapsed_ms(t0),
            )
        t_ctx_end = datetime.now(timezone.utc)
        context_duration_ms = _elapsed_ms(t_ctx_start)

        # ── Stage 2: Risk Evaluation ───────────────────────────────────────
        t_risk_start = datetime.now(timezone.utc)
        risk_assessment: Optional[IndustrialRiskAssessment] = None
        try:
            risk_assessment = self.risk_bridge.evaluate(context)
        except Exception as exc:
            logger.warning("RiskBridge failed for %s: %s", asset_id, exc, exc_info=True)
            # Non-fatal: continue to agents with risk=None
        risk_duration_ms = _elapsed_ms(t_risk_start)

        # ── Stage 3: Agent Orchestration ───────────────────────────────────
        t_agent_start = datetime.now(timezone.utc)
        advisory: Optional[OrchestratedAdvisory] = None
        try:
            advisory = self.orchestrator.run(context, risk_assessment)
        except Exception as exc:
            logger.error("AgentOrchestrator failed for %s: %s", asset_id, exc, exc_info=True)
            # Non-fatal: return partial result
        agent_duration_ms = _elapsed_ms(t_agent_start)

        total_duration_ms = _elapsed_ms(t0)

        logger.info(
            "IntelligenceService.run: run_id=%s asset=%s total=%.1fms ctx=%.1fms risk=%.1fms agents=%.1fms",
            run_id, asset_id, total_duration_ms, context_duration_ms, risk_duration_ms, agent_duration_ms,
        )

        return IntelligenceResult(
            run_id=run_id,
            asset_id=asset_id,
            success=True,
            context=context,
            risk_assessment=risk_assessment,
            advisory=advisory,
            context_duration_ms=round(context_duration_ms, 2),
            risk_duration_ms=round(risk_duration_ms, 2),
            agent_duration_ms=round(agent_duration_ms, 2),
            total_duration_ms=round(total_duration_ms, 2),
        )


def _elapsed_ms(t0: datetime) -> float:
    return (datetime.now(timezone.utc) - t0).total_seconds() * 1000.0


# Module-level singleton
intelligence_service = IntelligenceService()
