"""
backend/agents/industrial/orchestrator.py — Agent Orchestrator.

The Agent Orchestrator is the intelligence pipeline's final stage:
  1. Accepts an OperationalContextSnapshot
  2. Accepts an IndustrialRiskAssessment
  3. Dispatches to all four industrial agents
  4. Collects AgentAdvisory records
  5. Determines overall severity
  6. Assembles the final OrchestratedAdvisory for NOVA response generation

This is the entry point for the complete intelligence pipeline:
  ContextEngine → ContextRiskBridge → AgentOrchestrator → NOVA response

Zero-Actuation Rule:
  The orchestrator is purely advisory. It never issues commands.
  SafetyGuard enforces this at the API boundary.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.agents.industrial.anomaly_agent import AnomalyIntelAgent
from backend.agents.industrial.base import AgentAdvisory, AgentSeverity
from backend.agents.industrial.cot_agent import COTMonitorAgent
from backend.agents.industrial.fault_agent import FaultDiagnosisAgent
from backend.agents.industrial.tube_agent import TubeIntegrityAgent
from backend.services.context_engine import OperationalContextSnapshot

logger = logging.getLogger("nova.agents.orchestrator")

# Severity precedence (higher index = higher severity)
_SEVERITY_ORDER = [
    AgentSeverity.NORMAL,
    AgentSeverity.ADVISORY,
    AgentSeverity.WARNING,
    AgentSeverity.ALERT,
    AgentSeverity.CRITICAL,
]


class OrchestratedAdvisory(BaseModel):
    """
    The final assembled intelligence output from the Agent Orchestrator.

    Contains:
      - Overall severity (highest across all agents)
      - Individual agent advisories
      - Summary for NOVA response generation
      - Safety-critical flag (for escalation)
      - Risk score from the Risk Engine
    """
    orchestration_id: str = Field(default_factory=lambda: f"orch_{uuid.uuid4().hex[:12]}")
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Overall severity — highest across all agents
    overall_severity: AgentSeverity = AgentSeverity.NORMAL
    is_safety_critical: bool = False

    # Individual agent outputs
    advisories: List[AgentAdvisory] = Field(default_factory=list)

    # Summary fields for quick access
    headline: str = ""
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None

    # Context and pipeline metadata
    context_id: Optional[str] = None
    agent_names: List[str] = Field(default_factory=list)
    orchestration_duration_ms: float = 0.0
    providers_used: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def to_summary_text(self) -> str:
        """Render a concise summary for embedding in NOVA response."""
        lines = [
            f"NOVA Intelligence Advisory — Asset: {self.asset_id}",
            f"Overall Severity: {self.overall_severity.value}",
            f"Risk Score: {self.risk_score:.3f}" if self.risk_score is not None else "Risk Score: N/A",
            "",
        ]
        for adv in self.advisories:
            lines.append(f"[{adv.severity.value}] {adv.agent_name}: {adv.headline}")
        return "\n".join(lines)

    def to_full_text(self) -> str:
        """Render full advisory text for NOVA response generation."""
        lines = [self.to_summary_text(), ""]
        for adv in self.advisories:
            if adv.severity != AgentSeverity.NORMAL or self.overall_severity == AgentSeverity.NORMAL:
                lines.append("─" * 60)
                lines.append(adv.to_text())
                lines.append("")
        lines.append("─" * 60)
        lines.append(
            "IMPORTANT: All NOVA advisories are for qualified engineer review only. "
            "No process control actions have been initiated."
        )
        return "\n".join(lines)


class AgentOrchestrator:
    """
    NOVA Agent Orchestrator — dispatches context to all four agents
    and assembles the final OrchestratedAdvisory.

    Usage:
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(context, risk_assessment)
        # result.to_full_text() → advisory text for NOVA response
    """

    def __init__(
        self,
        anomaly_agent: Optional[AnomalyIntelAgent] = None,
        fault_agent: Optional[FaultDiagnosisAgent] = None,
        cot_agent: Optional[COTMonitorAgent] = None,
        tube_agent: Optional[TubeIntegrityAgent] = None,
    ) -> None:
        self._agents = [
            anomaly_agent or AnomalyIntelAgent(),
            fault_agent or FaultDiagnosisAgent(),
            cot_agent or COTMonitorAgent(),
            tube_agent or TubeIntegrityAgent(),
        ]

    def run(
        self,
        context: OperationalContextSnapshot,
        risk_assessment: Optional[Any] = None,
    ) -> OrchestratedAdvisory:
        """
        Run all four agents against the operational context.

        Args:
            context:         Assembled OperationalContextSnapshot
            risk_assessment: Risk assessment from ContextRiskBridge (optional)

        Returns:
            OrchestratedAdvisory with all agent outputs and overall severity.
        """
        t0 = datetime.now(timezone.utc)
        advisories: List[AgentAdvisory] = []
        warnings: List[str] = []

        # Dispatch to all agents
        for agent in self._agents:
            try:
                advisory = agent.analyze(context, risk_assessment)
                advisories.append(advisory)
            except Exception as exc:
                logger.error(
                    "AgentOrchestrator: agent %s failed for %s: %s",
                    agent.name, context.asset_id, exc, exc_info=True,
                )
                warnings.append(f"Agent {agent.name} failed: {exc}")

        # Determine overall severity
        overall_severity = self._compute_overall_severity(advisories)
        is_safety_critical = any(a.is_safety_critical for a in advisories)

        # Extract risk score from risk_assessment or highest advisory
        risk_score = None
        risk_tier = None
        if risk_assessment and hasattr(risk_assessment, "risk_score"):
            risk_score = risk_assessment.risk_score
            risk_tier = getattr(risk_assessment, "risk_tier", None)
            if risk_tier is not None:
                risk_tier = str(risk_tier.value if hasattr(risk_tier, "value") else risk_tier)

        # Build headline from most severe advisory
        headline = self._compute_headline(advisories, overall_severity, context.asset_id)

        t1 = datetime.now(timezone.utc)
        duration_ms = (t1 - t0).total_seconds() * 1000.0

        result = OrchestratedAdvisory(
            asset_id=context.asset_id,
            timestamp=t0,
            overall_severity=overall_severity,
            is_safety_critical=is_safety_critical,
            advisories=advisories,
            headline=headline,
            risk_score=risk_score,
            risk_tier=risk_tier,
            context_id=context.context_id,
            agent_names=[a.agent_name for a in advisories],
            orchestration_duration_ms=round(duration_ms, 2),
            providers_used=context.providers_used,
            warnings=warnings + context.warnings,
        )

        logger.info(
            "AgentOrchestrator.run: asset=%s severity=%s safety_critical=%s duration=%.1fms",
            context.asset_id, overall_severity.value, is_safety_critical, duration_ms,
        )
        return result

    def _compute_overall_severity(
        self,
        advisories: List[AgentAdvisory],
    ) -> AgentSeverity:
        """Return the highest severity across all advisories."""
        if not advisories:
            return AgentSeverity.NORMAL
        return max(
            (a.severity for a in advisories),
            key=lambda s: _SEVERITY_ORDER.index(s) if s in _SEVERITY_ORDER else 0,
        )

    def _compute_headline(
        self,
        advisories: List[AgentAdvisory],
        overall_severity: AgentSeverity,
        asset_id: str,
    ) -> str:
        """Extract headline from the most severe advisory."""
        if not advisories:
            return f"[{asset_id}] No advisory output"
        most_severe = max(
            advisories,
            key=lambda a: _SEVERITY_ORDER.index(a.severity) if a.severity in _SEVERITY_ORDER else 0,
        )
        return most_severe.headline


# Module-level singleton
agent_orchestrator = AgentOrchestrator()
