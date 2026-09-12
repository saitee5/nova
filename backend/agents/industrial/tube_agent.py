"""
backend/agents/industrial/tube_agent.py — Tube Integrity Intelligence Agent.

Monitors predicted tube skin temperature from the ML model and produces
advisory for the process engineer on tube metallurgical integrity.

Advisory scope:
  - Tube skin temperature prediction vs design limits
  - Coking risk assessment (based on temperature trends)
  - Operating mode correlation
  - Decoking run monitoring (advisory only)

Design note on coking_index:
  The coking_index is deliberately NOT included as an ML output field.
  Coking is assessed conservatively from tube temperature and residual
  trends rather than from an unvalidated model output.

Zero-Actuation Rule: NEVER issues decoking start commands or tube purge commands.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.agents.industrial.base import AgentAdvisory, AgentSeverity, BaseIndustrialAgent
from backend.services.context_engine import DataProvenance, OperationalContextSnapshot

logger = logging.getLogger("nova.agents.tube")

# Reference tube skin temperature limits (Celsius)
# Conservative advisory thresholds — actual design limits from KnowledgeProvider
# (Arushi's Knowledge Base) take precedence when available.
_TUBE_NOMINAL = 980.0
_TUBE_WARN_HIGH = 1010.0
_TUBE_ALERT_HIGH = 1040.0
_TUBE_CRIT_HIGH = 1065.0    # Metallurgical design limit for HP-modified alloys


class TubeIntegrityAgent(BaseIndustrialAgent):
    """
    Tube Integrity Intelligence Agent.

    Interprets ML tube skin temperature predictions and assesses
    tube metallurgical integrity risk.
    """

    def __init__(self) -> None:
        super().__init__(name="TubeIntegrityAgent")

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

        # ── Tube Temperature Prediction ───────────────────────────────────
        pred_tube_temp: Optional[float] = None
        tube_confidence: Optional[float] = None
        tube_prov = DataProvenance.MISSING

        if ml and ml.predicted_tube_temperature.value is not None:
            pred_tube_temp = float(ml.predicted_tube_temperature.value)
            tube_prov = ml.predicted_tube_temperature.provenance
            evidence["predicted_tube_temperature"] = pred_tube_temp

            for ev in context.ml_evidence:
                if ev.prediction_type.value == "tube_temperature" and ev.prediction:
                    tube_confidence = ev.prediction.get("confidence")
                    model_sources.append(ev.model_name)
                    if tube_confidence is not None:
                        evidence["confidence"] = tube_confidence
                    break

        # ── COT context for coking risk ───────────────────────────────────
        pred_cot: Optional[float] = None
        if ml and ml.predicted_cot.value is not None:
            pred_cot = float(ml.predicted_cot.value)
            evidence["predicted_cot"] = pred_cot

        # ── Severity determination ────────────────────────────────────────
        severity, headline, tube_finding = self._assess_tube(
            asset_id, pred_tube_temp, tube_confidence, tube_prov
        )
        findings.append(tube_finding)

        # ── Coking risk assessment ─────────────────────────────────────────
        # Conservative coking signal: high tube temp + high COT simultaneously
        if pred_tube_temp is not None and pred_cot is not None:
            if pred_tube_temp > _TUBE_WARN_HIGH and pred_cot > 860:
                findings.append(
                    f"Elevated tube temperature ({pred_tube_temp:.0f}°C) combined with high COT "
                    f"({pred_cot:.0f}°C) indicates potential accelerated coking conditions."
                )
                recommendations.append(
                    "Review tube skin temperature trend and decoking interval schedule with process engineering."
                )
                recommendations.append(
                    "Monitor CO concentration in flue gas for coking confirmation."
                )

        # ── Severity-specific recommendations ─────────────────────────────
        if severity == AgentSeverity.CRITICAL:
            recommendations.append(
                f"URGENT: Tube skin temperature approaching metallurgical limit on {asset_id}. "
                f"Senior engineer immediate review required."
            )
            recommendations.append(
                "Prepare for emergency decoking run per SOP — do not reduce firing without supervisor approval."
            )
        elif severity == AgentSeverity.ALERT:
            recommendations.append(
                f"Alert: Tube temperature on {asset_id} in alert range. "
                f"Notify shift supervisor and increase inspection frequency."
            )
            recommendations.append(
                "Verify tube skin temperature against multiple thermocouples."
            )
        elif severity == AgentSeverity.WARNING:
            recommendations.append(
                f"Monitor tube temperature trend on {asset_id} closely."
            )
            recommendations.append(
                "Check decoking schedule currency and tube inspection records."
            )

        # ── Operating mode context ─────────────────────────────────────────
        mode = context.operating_mode.value or "UNKNOWN"
        if mode in ("STARTUP", "RAMP_UP"):
            findings.append("During startup, tube temperatures typically lag COT recovery.")

        # ── Active alarm correlation ───────────────────────────────────────
        if context.active_alarms:
            for alarm in context.active_alarms[:5]:
                tag = alarm.get("tag") or alarm.get("alarm_tag", "")
                if any(t in tag.upper() for t in ("TUBE", "SKIN", "TI")):
                    findings.append(f"Active tube temperature alarm: {tag}")
                    break

        # ── Risk score ────────────────────────────────────────────────────
        risk_score = None
        if risk_assessment and hasattr(risk_assessment, "risk_score"):
            risk_score = risk_assessment.risk_score

        analysis = self._build_analysis(asset_id, pred_tube_temp, tube_confidence, mode)

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
                "tube_temp_provenance": tube_prov.value,
                "context_providers": context.providers_used,
                "coking_index_excluded": "not a validated model target",
            },
        )

    def _assess_tube(
        self,
        asset_id: str,
        pred_temp: Optional[float],
        confidence: Optional[float],
        prov: DataProvenance,
    ):
        if pred_temp is None or prov == DataProvenance.MISSING:
            return (
                AgentSeverity.NORMAL,
                f"[{asset_id}] Tube temperature predictor not available",
                "Tube Temperature Soft Sensor model not yet deployed. Using available sensor data only.",
            )

        conf_note = f" (confidence={confidence:.0%})" if confidence is not None else ""

        if pred_temp >= _TUBE_CRIT_HIGH:
            return (
                AgentSeverity.CRITICAL,
                f"[{asset_id}] CRITICAL: Tube temp={pred_temp:.0f}°C — metallurgical limit risk",
                f"Predicted tube skin temperature {pred_temp:.0f}°C approaching metallurgical design limit "
                f"({_TUBE_CRIT_HIGH}°C){conf_note}.",
            )
        elif pred_temp >= _TUBE_ALERT_HIGH:
            return (
                AgentSeverity.ALERT,
                f"[{asset_id}] Tube temperature ALERT: {pred_temp:.0f}°C",
                f"Predicted tube skin temperature {pred_temp:.0f}°C in alert range{conf_note}.",
            )
        elif pred_temp >= _TUBE_WARN_HIGH:
            return (
                AgentSeverity.WARNING,
                f"[{asset_id}] Tube temperature elevated: {pred_temp:.0f}°C",
                f"Predicted tube skin temperature {pred_temp:.0f}°C above nominal ({_TUBE_NOMINAL}°C){conf_note}.",
            )
        else:
            return (
                AgentSeverity.NORMAL,
                f"[{asset_id}] Tube temperature normal: {pred_temp:.0f}°C",
                f"Predicted tube skin temperature {pred_temp:.0f}°C within normal range{conf_note}.",
            )

    def _build_analysis(
        self,
        asset_id: str,
        pred_temp: Optional[float],
        confidence: Optional[float],
        mode: str,
    ) -> str:
        if pred_temp is None:
            return (
                f"Tube Temperature Soft Sensor is not available for {asset_id}. "
                f"Tube integrity advisory is based on available process alarms only. "
                f"Advisory output — no control actions initiated."
            )
        conf_str = f" (model confidence: {confidence:.0%})" if confidence is not None else ""
        return (
            f"Tube Temperature Soft Sensor predicts {pred_temp:.1f}°C tube skin temperature "
            f"for {asset_id}{conf_str}. Nominal target is {_TUBE_NOMINAL}°C. "
            f"Design limit reference: {_TUBE_CRIT_HIGH}°C (conservative HP alloy reference). "
            f"Operating mode: {mode}. "
            f"Advisory only — no decoking or control actions initiated. "
            f"All recommendations require qualified process engineer review and authorization."
        )
