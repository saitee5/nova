"""
backend/agents/industrial/anomaly_agent.py — Anomaly Intelligence Agent.

Analyzes ML anomaly evidence in the operational context and produces
a structured advisory for the process engineer.

Advisory scope:
  - Anomaly score interpretation
  - Sensor health assessment
  - Correlation with active alarms
  - Operating mode context
  - Historical episode matching
  - Recommended monitoring actions (advisory only)

Zero-Actuation Rule: NEVER issues process control commands.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.agents.industrial.base import AgentAdvisory, AgentSeverity, BaseIndustrialAgent
from backend.services.context_engine import DataProvenance, OperationalContextSnapshot

logger = logging.getLogger("nova.agents.anomaly")

# Anomaly score thresholds
_THRESH_WARNING = 0.40
_THRESH_ALERT = 0.65
_THRESH_CRITICAL = 0.80


class AnomalyIntelAgent(BaseIndustrialAgent):
    """
    Anomaly Intelligence Agent.

    Interprets ML anomaly scores (from Process Anomaly Detector) in
    operational context: alarms, equipment status, operating mode,
    and historical similar episodes.
    """

    def __init__(self) -> None:
        super().__init__(name="AnomalyIntelAgent")

    def analyze(
        self,
        context: OperationalContextSnapshot,
        risk_assessment: Optional[Any] = None,
    ) -> AgentAdvisory:
        asset_id = context.asset_id
        ml = context.ml_summary
        findings: List[str] = []
        recommendations: List[str] = []
        evidence: dict = {}
        model_sources: List[str] = []

        # ── Anomaly Score ─────────────────────────────────────────────────
        score = None
        anomaly_detected = False
        score_provenance = DataProvenance.MISSING

        if ml and ml.anomaly_score.value is not None:
            score = float(ml.anomaly_score.value)
            score_provenance = ml.anomaly_score.provenance
            anomaly_detected = bool(ml.anomaly_detected.value)
            evidence["anomaly_score"] = score
            evidence["anomaly_detected"] = anomaly_detected

            if score_provenance == DataProvenance.PREDICTED:
                model_sources.append(ml.model_versions.get("anomaly", "ProcessAnomalyDetector"))

        # ── Severity determination ────────────────────────────────────────
        if score is None or score_provenance == DataProvenance.MISSING:
            severity = AgentSeverity.NORMAL
            headline = f"[{asset_id}] Anomaly assessment unavailable — model not loaded"
            findings.append("Anomaly score not available — Process Anomaly Detector not yet deployed.")
            findings.append("Monitoring based on alarm state and equipment status only.")
            recommendations.append(
                "Alert Arushi (ML team) to deploy Process Anomaly Detector artifacts."
            )
        elif score >= _THRESH_CRITICAL:
            severity = AgentSeverity.CRITICAL
            headline = f"[{asset_id}] CRITICAL process anomaly — score={score:.2f}"
            findings.append(f"Anomaly score {score:.3f} exceeds critical threshold ({_THRESH_CRITICAL}).")
            recommendations.append(f"Immediately notify unit shift supervisor for {asset_id}.")
            recommendations.append("Verify all critical process instruments are functional.")
            recommendations.append("Review operating mode and process constraints with senior engineer.")
        elif score >= _THRESH_ALERT:
            severity = AgentSeverity.ALERT
            headline = f"[{asset_id}] Process anomaly ALERT — score={score:.2f}"
            findings.append(f"Anomaly score {score:.3f} is in alert range.")
            recommendations.append(f"Senior engineer review of {asset_id} required.")
            recommendations.append("Inspect critical sensors for abnormal readings.")
        elif score >= _THRESH_WARNING:
            severity = AgentSeverity.WARNING
            headline = f"[{asset_id}] Process anomaly WARNING — score={score:.2f}"
            findings.append(f"Anomaly score {score:.3f} indicates developing deviation.")
            recommendations.append("Increase monitoring frequency for key process parameters.")
        else:
            severity = AgentSeverity.NORMAL
            headline = f"[{asset_id}] Normal — anomaly score={score:.2f}"
            findings.append(f"Anomaly score {score:.3f} within normal range.")

        # ── Fault context (from FaultDiagnosisAgent) ──────────────────────
        if ml and ml.predicted_fault.value and ml.predicted_fault.value not in ("NORMAL", "None"):
            fault = ml.predicted_fault.value
            conf = ml.fault_confidence.value
            findings.append(
                f"Fault classifier indicates: '{fault}' (confidence={conf:.2f})"
                if conf else f"Fault classifier indicates: '{fault}'"
            )
            evidence["predicted_fault"] = fault

        # ── Sensor health assessment ───────────────────────────────────────
        bad_sensors = [
            p for p, q in context.sensor_health.items()
            if q.upper() in ("BAD", "UNCERTAIN", "SUBSTITUTED")
        ]
        if bad_sensors:
            findings.append(f"Degraded sensor readings on: {', '.join(bad_sensors[:5])}.")
            if len(bad_sensors) > 5:
                findings.append(f"  ... and {len(bad_sensors) - 5} additional sensors.")
            recommendations.append("Investigate and calibrate degraded sensors before relying on anomaly scores.")
            evidence["bad_sensors"] = bad_sensors[:10]

        # ── Alarm correlation ─────────────────────────────────────────────
        if context.active_alarms:
            alarm_sev = context.highest_alarm_severity.value or "UNKNOWN"
            findings.append(
                f"{len(context.active_alarms)} active alarm(s); highest severity: {alarm_sev}."
            )

        # ── Operating mode context ─────────────────────────────────────────
        mode = context.operating_mode.value or "UNKNOWN"
        findings.append(f"Current operating mode: {mode}.")
        if mode in ("STARTUP", "SHUTDOWN", "RAMP_UP", "RAMP_DOWN"):
            findings.append("Anomaly thresholds may be elevated during transient operating modes.")

        # ── Historical episodes ────────────────────────────────────────────
        if context.similar_episodes:
            top = context.similar_episodes[0]
            title = top.get("title", "Unknown incident")
            sim = top.get("similarity_score", 0)
            findings.append(f"Most similar historical episode: '{title}' (similarity={sim:.2f}).")
            recommendations.append(f"Review historical episode '{title}' for diagnostic guidance.")

        # ── Risk Score ────────────────────────────────────────────────────
        risk_score = None
        if risk_assessment and hasattr(risk_assessment, "risk_score"):
            risk_score = risk_assessment.risk_score
            evidence["risk_score"] = risk_score
            evidence["risk_tier"] = getattr(risk_assessment, "risk_tier", None)

        # ── Analysis narrative ────────────────────────────────────────────
        analysis = self._build_analysis(asset_id, score, severity, mode, bad_sensors, context)

        return AgentAdvisory(
            agent_name=self.name,
            asset_id=asset_id,
            severity=severity,
            headline=headline,
            analysis=analysis,
            key_findings=findings,
            recommendations=recommendations,
            supporting_evidence=evidence,
            context_id=context.context_id,
            risk_score=risk_score,
            model_sources=model_sources,
            is_safety_critical=severity in (AgentSeverity.ALERT, AgentSeverity.CRITICAL),
            provenance={
                "anomaly_score_provenance": score_provenance.value,
                "context_providers": context.providers_used,
            },
        )

    def _build_analysis(
        self,
        asset_id: str,
        score: Optional[float],
        severity: AgentSeverity,
        mode: str,
        bad_sensors: list,
        context: OperationalContextSnapshot,
    ) -> str:
        parts = []
        if score is not None:
            parts.append(
                f"The Process Anomaly Detector reports a score of {score:.3f} for {asset_id}. "
            )
        else:
            parts.append(
                f"Anomaly detection model is not available for {asset_id}. "
                f"Assessment is based on alarm state and equipment status only. "
            )

        alarms = len(context.active_alarms)
        if alarms:
            parts.append(f"There are {alarms} active alarm(s) on this asset. ")
        else:
            parts.append("No active alarms on this asset. ")

        if bad_sensors:
            parts.append(
                f"{len(bad_sensors)} sensor(s) show degraded quality, which may affect anomaly score reliability. "
            )

        parts.append(
            f"All findings are advisory only. No process control actions have been initiated. "
            f"All recommendations require review by a qualified process engineer."
        )
        return "".join(parts)
