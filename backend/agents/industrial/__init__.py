"""
backend/agents/industrial — Industrial Agent Intelligence Layer.

This package provides:
  - BaseIndustrialAgent: common interface for all NOVA agents
  - AnomalyIntelAgent: anomaly analysis → advisory
  - FaultDiagnosisAgent: fault classification → root cause advisory
  - COTMonitorAgent: COT prediction → furnace advisory
  - TubeIntegrityAgent: tube temperature → integrity advisory

All agents are strictly ADVISORY — they produce text recommendations
for human review. They NEVER issue commands to process control systems.

Zero-Actuation Rule:
  NOVA agents NEVER write to PLC/DCS/SIS/ESD/safety systems.
  NOVA agents NEVER issue setpoint changes.
  NOVA agents NEVER initiate process actions.
  All output is advisory text for human engineer review only.
"""
from __future__ import annotations

from backend.agents.industrial.base import (
    AgentAdvisory,
    AgentSeverity,
    BaseIndustrialAgent,
)
from backend.agents.industrial.anomaly_agent import AnomalyIntelAgent
from backend.agents.industrial.fault_agent import FaultDiagnosisAgent
from backend.agents.industrial.cot_agent import COTMonitorAgent
from backend.agents.industrial.tube_agent import TubeIntegrityAgent
from backend.agents.industrial.orchestrator import (
    AgentOrchestrator,
    OrchestratedAdvisory,
    agent_orchestrator,
)

__all__ = [
    "AgentAdvisory",
    "AgentSeverity",
    "BaseIndustrialAgent",
    "AnomalyIntelAgent",
    "FaultDiagnosisAgent",
    "COTMonitorAgent",
    "TubeIntegrityAgent",
    "AgentOrchestrator",
    "OrchestratedAdvisory",
    "agent_orchestrator",
]
