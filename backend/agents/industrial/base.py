"""
backend/agents/industrial/base.py — Base Industrial Agent Contracts.

Defines:
  - AgentSeverity: severity classification for advisories
  - AgentAdvisory: the typed advisory output (read-only text for engineers)
  - BaseIndustrialAgent: abstract base for all four NOVA industrial agents

Zero-Actuation Rule:
  All agents produce ONLY text advisories for human review.
  No agent may generate output containing process control commands,
  setpoint changes, or control system actuation strings.
  The SafetyGuard enforces this at the policy boundary.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentSeverity(str, Enum):
    """Advisory severity level — for human triage and display prioritization."""
    NORMAL = "NORMAL"       # No actionable concern — informational
    ADVISORY = "ADVISORY"   # Low-priority advisory — operator awareness
    WARNING = "WARNING"     # Operator attention required
    ALERT = "ALERT"         # Senior engineer immediate review required
    CRITICAL = "CRITICAL"   # Emergency: immediate supervisor notification required


class AgentAdvisory(BaseModel):
    """
    Typed advisory output produced by a NOVA industrial agent.

    This is the sole output type of all industrial agents.
    It contains only TEXT for human review — never commands.

    Fields:
      advisory_id:      UUID for traceability
      agent_name:       Producing agent name
      asset_id:         Target asset
      severity:         Triage severity
      headline:         One-line summary (human-readable)
      analysis:         Structured analysis narrative
      key_findings:     Bullet-point key findings
      recommendations:  Advisory action items (for human review only)
      supporting_evidence: Key evidence items referenced
      context_id:       Reference to the OperationalContextSnapshot
      risk_score:       Risk score from RiskEngine (if available)
      model_sources:    Which ML models contributed evidence
      timestamp:        Advisory generation time
      is_safety_critical: True when advisory flags a potential safety concern
      provenance:       Provenance tags for traceability

    CRITICAL NOTE:
      recommendations must NEVER contain PLC/DCS commands,
      setpoint changes, or actuation instructions.
      They must always be human advisory text only.
    """
    advisory_id: str = Field(default_factory=lambda: f"adv_{uuid.uuid4().hex[:12]}")
    agent_name: str
    asset_id: str
    severity: AgentSeverity = AgentSeverity.NORMAL
    headline: str
    analysis: str
    key_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    context_id: Optional[str] = None
    risk_score: Optional[float] = None
    model_sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_safety_critical: bool = False
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def to_text(self) -> str:
        """Render advisory as human-readable text for the NOVA response."""
        lines = [
            f"[{self.severity.value}] {self.agent_name}: {self.headline}",
            "",
            self.analysis,
        ]
        if self.key_findings:
            lines += ["", "Key Findings:"]
            lines += [f"  • {f}" for f in self.key_findings]
        if self.recommendations:
            lines += ["", "Recommendations (Advisory — Human Review Required):"]
            lines += [f"  → {r}" for r in self.recommendations]
        if self.risk_score is not None:
            lines += [f"", f"Risk Score: {self.risk_score:.3f}"]
        return "\n".join(lines)


class BaseIndustrialAgent(ABC):
    """
    Abstract base class for NOVA industrial intelligence agents.

    Each agent specializes in one aspect of industrial intelligence:
      - AnomalyIntelAgent: anomaly detection analysis
      - FaultDiagnosisAgent: fault classification and root cause
      - COTMonitorAgent: furnace COT advisory
      - TubeIntegrityAgent: tube temperature / integrity advisory

    All agents share the same call interface:
      advisory = agent.analyze(context, risk_assessment)

    All agents produce only AgentAdvisory objects.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def analyze(
        self,
        context: Any,  # OperationalContextSnapshot
        risk_assessment: Optional[Any] = None,  # IndustrialRiskAssessment
    ) -> AgentAdvisory:
        """
        Analyze the operational context and produce an advisory.

        Args:
            context:         Assembled OperationalContextSnapshot
            risk_assessment: Risk assessment (may be None if risk engine skipped)

        Returns:
            AgentAdvisory — text advisory for human review ONLY.
        """

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert a value to float, returning default on error."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
