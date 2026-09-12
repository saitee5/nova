"""
backend/agents/industrial/cot_agent.py — Furnace COT Monitor Agent.

Monitors predicted Coil Outlet Temperature (COT) from the ML model
and produces advisory for the process engineer on furnace health.

Advisory scope:
  - Predicted vs nominal COT analysis
  - COT residual (actual - predicted) monitoring
  - Operating limit cross-reference (from KnowledgeProvider if available)
  - Tube temperature correlation
  - Decoking run recommendations (advisory only)

Zero-Actuation Rule: NEVER issues process control commands or COT setpoint changes.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.agents.industrial.base import AgentAdvisory, AgentSeverity, BaseIndustrialAgent
from backend.services.context_engine import DataProvenance, OperationalContextSnapshot

logger = logging.getLogger("nova.agents.cot")

# Reference nominal limits (Celsius) — conservative bounds for advisory
# These are conservative advisory thresholds; operating limits from
# KnowledgeProvider (Arushi's KB) take precedence when available.
_COT_NOMINAL = 845.0        # Normal target COT
_COT_WARN_HIGH = 860.0      # Advisory threshold
_COT_ALERT_HIGH = 875.0     # Alert threshold
_COT_CRIT_HIGH = 890.0      # Critical high — tube damage risk
_COT_WARN_LOW = 820.0       # Advisory threshold low
_COT_ALERT_LOW = 805.0      # Alert threshold low


class COTMonitorAgent(BaseIndustrialAgent):
    """
    Furnace Coil Outlet Temperature (COT) Monitor Agent.

    Interprets ML COT predictions and compares against operating limits
    to produce advisory for furnace heat management.
    """

    def __init__(self) -> None:
        super().__init__(name="COTMonitorAgent")

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

        # ── COT Prediction ────────────────────────────────────────────────
        pred_cot: Optional[float] = None
        actual_cot: Optional[float] = None
        residual: Optional[float] = None
        cot_prov = DataProvenance.MISSING

        if ml and ml.predicted_cot.value is not None:
            pred_cot = float(ml.predicted_cot.value)
            cot_prov = ml.predicted_cot.provenance
            evidence["predicted_cot"] = pred_cot

            # Extract actual COT and residual from evidence records
            for ev in context.ml_evidence:
                if ev.prediction_type.value == "cot_prediction" and ev.prediction:
                    actual_cot = ev.prediction.get("actual_cot")
                    residual = ev.prediction.get("residual")
                    model_sources.append(ev.model_name)
                    if actual_cot is not None:
                        evidence["actual_cot"] = actual_cot
                    if residual is not None:
                        evidence["residual"] = residual
                    break

        # ── Tube temperature context ───────────────────────────────────────
        pred_tube_temp: Optional[float] = None
        if ml and ml.predicted_tube_temperature.value is not None:
            pred_tube_temp = float(ml.predicted_tube_temperature.value)
            evidence["predicted_tube_temperature"] = pred_tube_temp

        # ── Severity determination ────────────────────────────────────────
        severity, headline, cot_finding = self._assess_cot(
            asset_id, pred_cot, actual_cot, residual, cot_prov
        )
        findings.append(cot_finding)

        # ── Residual analysis ─────────────────────────────────────────────
        if residual is not None:
            abs_residual = abs(residual)
            if abs_residual > 15:
                findings.append(
                    f"Large COT residual (actual - predicted = {residual:+.1f}°C). "
                    f"Sensor calibration or model drift may be occurring."
                )
                recommendations.append("Verify TI-20101/TI-20102 calibration against reference.")
            elif abs_residual > 5:
                findings.append(f"Moderate COT residual: {residual:+.1f}°C — monitor trend.")

        # ── Tube temperature cross-check ──────────────────────────────────
        if pred_tube_temp is not None:
            if pred_tube_temp > 1000:
                findings.append(
                    f"ALERT: Predicted tube skin temperature {pred_tube_temp:.0f}°C exceeds safe limit."
                )
                if severity.value < AgentSeverity.ALERT.value:
                    severity = AgentSeverity.ALERT
                recommendations.append(
                    "Verify tube skin temperatures at multiple thermocouple points. "
                    "Elevated tube temperatures risk tube metallurgical damage."
                )
            elif pred_tube_temp > 980:
                findings.append(
                    f"Predicted tube skin temperature {pred_tube_temp:.0f}°C is elevated."
                )

        # ── Operating mode context ─────────────────────────────────────────
        mode = context.operating_mode.value or "UNKNOWN"
        if mode in ("STARTUP", "RAMP_UP"):
            findings.append("COT limits during startup are expected to be below nominal target.")
        elif mode in ("SHUTDOWN", "RAMP_DOWN"):
            findings.append("COT should be decreasing in SHUTDOWN/RAMP_DOWN mode.")

        # ── COT-specific recommendations ──────────────────────────────────
        if severity in (AgentSeverity.WARNING, AgentSeverity.ALERT, AgentSeverity.CRITICAL):
            if pred_cot is not None and pred_cot > _COT_ALERT_HIGH:
                recommendations.append(
                    f"COT {pred_cot:.1f}°C exceeds alert threshold. "
                    f"Notify shift supervisor and review furnace firing rate."
                )
                recommendations.append(
                    "Check decoking schedule: high COT with elevated tube temp may indicate coking."
                )
            elif pred_cot is not None and pred_cot < _COT_ALERT_LOW:
                recommendations.append(
                    f"COT {pred_cot:.1f}°C is below alert threshold. "
                    f"Verify feed flow, firing rate, and steam supply."
                )

        # ── Alarm correlation ─────────────────────────────────────────────
        if context.active_alarms:
            for alarm in context.active_alarms[:3]:
                tag = alarm.get("tag") or alarm.get("alarm_tag", "")
                if any(t in tag.upper() for t in ("TI-201", "TEMP", "COT")):
                    findings.append(f"Active temperature alarm: {tag}")
                    break

        # ── Risk score ────────────────────────────────────────────────────
        risk_score = None
        if risk_assessment and hasattr(risk_assessment, "risk_score"):
            risk_score = risk_assessment.risk_score

        analysis = self._build_analysis(asset_id, pred_cot, actual_cot, residual, mode)

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
                "cot_provenance": cot_prov.value,
                "context_providers": context.providers_used,
            },
        )

    def _assess_cot(
        self,
        asset_id: str,
        pred_cot: Optional[float],
        actual_cot: Optional[float],
        residual: Optional[float],
        prov: DataProvenance,
    ):
        if pred_cot is None or prov == DataProvenance.MISSING:
            return (
                AgentSeverity.NORMAL,
                f"[{asset_id}] COT predictor not available",
                "Furnace COT Predictor model not yet deployed. COT monitoring uses available sensor data only.",
            )

        if pred_cot >= _COT_CRIT_HIGH:
            return (
                AgentSeverity.CRITICAL,
                f"[{asset_id}] CRITICAL: COT={pred_cot:.0f}°C — tube damage risk",
                f"Predicted COT {pred_cot:.1f}°C exceeds critical threshold ({_COT_CRIT_HIGH}°C).",
            )
        elif pred_cot >= _COT_ALERT_HIGH:
            return (
                AgentSeverity.ALERT,
                f"[{asset_id}] COT ALERT: {pred_cot:.0f}°C",
                f"Predicted COT {pred_cot:.1f}°C is in the alert range (>{_COT_ALERT_HIGH}°C).",
            )
        elif pred_cot >= _COT_WARN_HIGH:
            return (
                AgentSeverity.WARNING,
                f"[{asset_id}] COT elevated: {pred_cot:.0f}°C",
                f"Predicted COT {pred_cot:.1f}°C is above nominal target ({_COT_NOMINAL}°C).",
            )
        elif pred_cot <= _COT_ALERT_LOW:
            return (
                AgentSeverity.ALERT,
                f"[{asset_id}] COT LOW ALERT: {pred_cot:.0f}°C",
                f"Predicted COT {pred_cot:.1f}°C is significantly below nominal ({_COT_NOMINAL}°C).",
            )
        elif pred_cot <= _COT_WARN_LOW:
            return (
                AgentSeverity.WARNING,
                f"[{asset_id}] COT below target: {pred_cot:.0f}°C",
                f"Predicted COT {pred_cot:.1f}°C is below nominal target ({_COT_NOMINAL}°C).",
            )
        else:
            return (
                AgentSeverity.NORMAL,
                f"[{asset_id}] COT within target: {pred_cot:.0f}°C",
                f"Predicted COT {pred_cot:.1f}°C is within normal operating range.",
            )

    def _build_analysis(
        self,
        asset_id: str,
        pred_cot: Optional[float],
        actual_cot: Optional[float],
        residual: Optional[float],
        mode: str,
    ) -> str:
        if pred_cot is None:
            return (
                f"Furnace COT Predictor model is not available for {asset_id}. "
                f"COT advisory is unavailable. "
                f"Monitor TI-20101 and TI-20102 directly."
            )
        lines = [
            f"Furnace COT Predictor reports predicted COT of {pred_cot:.1f}°C for {asset_id} "
            f"(nominal target: {_COT_NOMINAL}°C)."
        ]
        if actual_cot is not None:
            lines.append(f" Measured COT: {actual_cot:.1f}°C. Residual: {residual:+.1f}°C." if residual is not None else f" Measured COT: {actual_cot:.1f}°C.")
        lines.append(
            f" Operating mode: {mode}. "
            f"Advisory only — no control system actions initiated. "
            f"All recommendations require qualified engineer review."
        )
        return "".join(lines)
