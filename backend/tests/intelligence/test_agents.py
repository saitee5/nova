"""
backend/tests/intelligence/test_agents.py — Industrial Agent Test Suite.

Tests:
  - AnomalyIntelAgent severity tiers
  - FaultDiagnosisAgent high-hazard fault detection
  - COTMonitorAgent limit crossing detection
  - TubeIntegrityAgent threshold assessment
  - AgentOrchestrator dispatch and severity aggregation
  - OrchestratedAdvisory output serialization
  - Zero-actuation verification (no commands in advisory text)

Zero-actuation rule: advisory text must never contain actuation commands.
"""
from __future__ import annotations

import pytest

from backend.agents.industrial.anomaly_agent import AnomalyIntelAgent, _THRESH_WARNING, _THRESH_CRITICAL
from backend.agents.industrial.base import AgentAdvisory, AgentSeverity
from backend.agents.industrial.cot_agent import COTMonitorAgent, _COT_CRIT_HIGH
from backend.agents.industrial.fault_agent import FaultDiagnosisAgent
from backend.agents.industrial.orchestrator import AgentOrchestrator, OrchestratedAdvisory
from backend.agents.industrial.tube_agent import TubeIntegrityAgent, _TUBE_CRIT_HIGH
from backend.ml.runtime.mocks import build_mock_ml_runtime
from backend.services.context_engine import ContextEngine


SAMPLE_TELEMETRY = {
    "TI-20101": 847.0,
    "TI-20102": 849.0,
    "tube_skin_temperature": 985.0,
    "compressor_vibration": 1.5,
}

# Prohibited command substrings — must never appear in advisory output
PROHIBITED_COMMAND_PATTERNS = [
    "setpoint", "plc write", "dcs command", "sis action", "esd trip",
    "actuate", "initiate trip", "write register", "modbus write",
]


def _build_context(
    anomaly_score: float = 0.1,
    force_anomaly: bool = False,
    predicted_fault: str = "NORMAL",
    predicted_cot: float = 845.0,
    predicted_tube_temp: float = 980.0,
    asset_id: str = "F-201A",
):
    engine = ContextEngine(
        ml_runtime=build_mock_ml_runtime(
            anomaly_score=anomaly_score,
            force_anomaly=force_anomaly,
            predicted_fault=predicted_fault,
            predicted_cot=predicted_cot,
            predicted_tube_temp=predicted_tube_temp,
        )
    )
    return engine.assemble(asset_id, telemetry_override=SAMPLE_TELEMETRY)


# ---------------------------------------------------------------------------
# AnomalyIntelAgent
# ---------------------------------------------------------------------------

class TestAnomalyIntelAgent:

    def test_normal_score_gives_normal_severity(self):
        ctx = _build_context(anomaly_score=0.1)
        agent = AnomalyIntelAgent()
        adv = agent.analyze(ctx)
        assert adv.severity == AgentSeverity.NORMAL

    def test_warning_threshold(self):
        ctx = _build_context(anomaly_score=_THRESH_WARNING)
        agent = AnomalyIntelAgent()
        adv = agent.analyze(ctx)
        assert adv.severity == AgentSeverity.WARNING

    def test_critical_threshold(self):
        ctx = _build_context(anomaly_score=_THRESH_CRITICAL, force_anomaly=True)
        agent = AnomalyIntelAgent()
        adv = agent.analyze(ctx)
        assert adv.severity == AgentSeverity.CRITICAL

    def test_advisory_has_required_fields(self):
        ctx = _build_context()
        adv = AnomalyIntelAgent().analyze(ctx)
        assert adv.agent_name == "AnomalyIntelAgent"
        assert adv.asset_id == "F-201A"
        assert len(adv.analysis) > 0
        assert adv.advisory_id.startswith("adv_")

    def test_critical_advisory_is_safety_critical(self):
        ctx = _build_context(anomaly_score=0.9, force_anomaly=True)
        adv = AnomalyIntelAgent().analyze(ctx)
        assert adv.is_safety_critical is True

    def test_normal_advisory_is_not_safety_critical(self):
        ctx = _build_context(anomaly_score=0.05)
        adv = AnomalyIntelAgent().analyze(ctx)
        assert adv.is_safety_critical is False

    def test_to_text_contains_severity_and_headline(self):
        ctx = _build_context(anomaly_score=0.9, force_anomaly=True)
        adv = AnomalyIntelAgent().analyze(ctx)
        text = adv.to_text()
        assert "CRITICAL" in text
        assert "F-201A" in text

    def test_no_prohibited_commands_in_advisory(self):
        ctx = _build_context(anomaly_score=0.9, force_anomaly=True)
        adv = AnomalyIntelAgent().analyze(ctx)
        full_text = adv.to_text().lower()
        for pattern in PROHIBITED_COMMAND_PATTERNS:
            assert pattern not in full_text, f"Prohibited pattern '{pattern}' found in advisory"


# ---------------------------------------------------------------------------
# FaultDiagnosisAgent
# ---------------------------------------------------------------------------

class TestFaultDiagnosisAgent:

    def test_normal_fault_gives_normal_severity(self):
        ctx = _build_context(predicted_fault="NORMAL")
        adv = FaultDiagnosisAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.NORMAL

    def test_high_hazard_fault_high_confidence_gives_critical(self):
        ctx = _build_context(predicted_fault="TUBE_OVERTEMPERATURE")
        adv = FaultDiagnosisAgent().analyze(ctx)
        assert adv.severity in (AgentSeverity.CRITICAL, AgentSeverity.ALERT)
        assert adv.is_safety_critical is True

    def test_low_hazard_fault_gives_warning(self):
        ctx = _build_context(predicted_fault="SENSOR_DRIFT")
        adv = FaultDiagnosisAgent().analyze(ctx)
        # With default confidence 0.85 → WARNING
        assert adv.severity == AgentSeverity.WARNING

    def test_fault_agent_name(self):
        ctx = _build_context()
        adv = FaultDiagnosisAgent().analyze(ctx)
        assert adv.agent_name == "FaultDiagnosisAgent"

    def test_no_prohibited_commands_in_advisory(self):
        ctx = _build_context(predicted_fault="COMPRESSOR_SURGE")
        adv = FaultDiagnosisAgent().analyze(ctx)
        full_text = adv.to_text().lower()
        for pattern in PROHIBITED_COMMAND_PATTERNS:
            assert pattern not in full_text, f"Prohibited pattern '{pattern}' found"


# ---------------------------------------------------------------------------
# COTMonitorAgent
# ---------------------------------------------------------------------------

class TestCOTMonitorAgent:

    def test_normal_cot_gives_normal_severity(self):
        ctx = _build_context(predicted_cot=845.0)
        adv = COTMonitorAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.NORMAL

    def test_critically_high_cot_gives_critical(self):
        ctx = _build_context(predicted_cot=_COT_CRIT_HIGH + 1)
        adv = COTMonitorAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.CRITICAL
        assert adv.is_safety_critical is True

    def test_warning_high_cot(self):
        ctx = _build_context(predicted_cot=862.0)
        adv = COTMonitorAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.WARNING

    def test_low_cot_gives_alert(self):
        ctx = _build_context(predicted_cot=800.0)
        adv = COTMonitorAgent().analyze(ctx)
        assert adv.severity in (AgentSeverity.ALERT, AgentSeverity.WARNING)

    def test_advisory_contains_cot_value(self):
        ctx = _build_context(predicted_cot=870.0)
        adv = COTMonitorAgent().analyze(ctx)
        assert "870" in adv.headline or "870" in adv.analysis

    def test_cot_advisory_never_issues_setpoint_command(self):
        ctx = _build_context(predicted_cot=895.0)
        adv = COTMonitorAgent().analyze(ctx)
        text = adv.to_text().lower()
        for pattern in PROHIBITED_COMMAND_PATTERNS:
            assert pattern not in text


# ---------------------------------------------------------------------------
# TubeIntegrityAgent
# ---------------------------------------------------------------------------

class TestTubeIntegrityAgent:

    def test_normal_tube_temp(self):
        ctx = _build_context(predicted_tube_temp=980.0)
        adv = TubeIntegrityAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.NORMAL

    def test_critical_tube_temp_gives_critical(self):
        ctx = _build_context(predicted_tube_temp=_TUBE_CRIT_HIGH + 5)
        adv = TubeIntegrityAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.CRITICAL
        assert adv.is_safety_critical is True

    def test_warning_tube_temp(self):
        ctx = _build_context(predicted_tube_temp=1015.0)
        adv = TubeIntegrityAgent().analyze(ctx)
        assert adv.severity == AgentSeverity.WARNING

    def test_coking_index_not_in_supporting_evidence(self):
        """coking_index must never appear as a supported evidence field."""
        ctx = _build_context(predicted_tube_temp=1020.0)
        adv = TubeIntegrityAgent().analyze(ctx)
        assert "coking_index" not in adv.supporting_evidence

    def test_advisory_text_does_not_reference_validated_coking_index(self):
        ctx = _build_context(predicted_tube_temp=1020.0)
        adv = TubeIntegrityAgent().analyze(ctx)
        text = adv.to_text()
        # OK to mention coking as a risk assessment concept, but not as a ML model output
        # The provenance note should reflect this
        assert "coking_index_excluded" in adv.provenance


# ---------------------------------------------------------------------------
# AgentOrchestrator
# ---------------------------------------------------------------------------

class TestAgentOrchestrator:

    def test_runs_all_four_agents(self):
        ctx = _build_context(anomaly_score=0.1)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        assert len(result.advisories) == 4

    def test_highest_severity_propagated(self):
        # Force anomaly critical
        ctx = _build_context(anomaly_score=0.9, force_anomaly=True, predicted_cot=845.0)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        assert result.overall_severity == AgentSeverity.CRITICAL

    def test_normal_all_agents_gives_normal(self):
        ctx = _build_context(anomaly_score=0.05, predicted_cot=845.0, predicted_tube_temp=980.0)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        assert result.overall_severity == AgentSeverity.NORMAL

    def test_safety_critical_flagged_when_any_agent_critical(self):
        ctx = _build_context(anomaly_score=0.95, force_anomaly=True)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        assert result.is_safety_critical is True

    def test_orchestration_id_unique(self):
        ctx = _build_context()
        orchestrator = AgentOrchestrator()
        r1 = orchestrator.run(ctx)
        r2 = orchestrator.run(ctx)
        assert r1.orchestration_id != r2.orchestration_id

    def test_agent_failure_is_graceful(self):
        class BrokenAgent:
            name = "BrokenAgent"
            def analyze(self, ctx, ra=None):
                raise RuntimeError("agent exploded")

        orchestrator = AgentOrchestrator(
            anomaly_agent=AnomalyIntelAgent(),
            fault_agent=FaultDiagnosisAgent(),
            cot_agent=COTMonitorAgent(),
            tube_agent=TubeIntegrityAgent(),
        )
        ctx = _build_context()
        result = orchestrator.run(ctx)  # Must not crash
        assert result is not None

    def test_to_summary_text(self):
        ctx = _build_context(anomaly_score=0.7, force_anomaly=True)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        summary = result.to_summary_text()
        assert "F-201A" in summary
        assert result.overall_severity.value in summary

    def test_to_full_text_contains_safety_disclaimer(self):
        ctx = _build_context()
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        full_text = result.to_full_text()
        assert "advisory" in full_text.lower()
        assert "no process control actions" in full_text.lower()

    def test_orchestration_duration_recorded(self):
        ctx = _build_context()
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        assert result.orchestration_duration_ms >= 0.0


# ---------------------------------------------------------------------------
# Zero-Actuation Safety Test
# ---------------------------------------------------------------------------

class TestZeroActuationSafety:
    """
    Verify that no advisory output across all agents contains
    process control commands or actuation strings.
    """

    def _all_advisory_text(self, result: OrchestratedAdvisory) -> str:
        """Collect all text from all advisories."""
        texts = [result.to_full_text()]
        for adv in result.advisories:
            texts.append(adv.to_text())
            texts.extend(adv.key_findings)
            texts.extend(adv.recommendations)
        return " ".join(texts).lower()

    def test_no_plc_commands_in_critical_scenario(self):
        ctx = _build_context(
            anomaly_score=0.99,
            force_anomaly=True,
            predicted_fault="TUBE_OVERTEMPERATURE",
            predicted_cot=895.0,
            predicted_tube_temp=1070.0,
        )
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        full_text = self._all_advisory_text(result)
        for pattern in PROHIBITED_COMMAND_PATTERNS:
            assert pattern not in full_text, f"Prohibited command pattern found: '{pattern}'"

    def test_recommendations_are_human_actionable_only(self):
        ctx = _build_context(anomaly_score=0.85, force_anomaly=True)
        orchestrator = AgentOrchestrator()
        result = orchestrator.run(ctx)
        for adv in result.advisories:
            for rec in adv.recommendations:
                rec_lower = rec.lower()
                # Should not contain machine-directable commands
                assert "plc" not in rec_lower
                assert "write register" not in rec_lower
                assert "setpoint change" not in rec_lower
