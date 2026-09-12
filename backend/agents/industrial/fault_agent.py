"""
backend/agents/industrial/fault_agent.py — Fault Diagnosis Intelligence Agent.

Analyzes ML fault classification evidence in the operational context and produces
a structured root cause advisory for the process engineer.

Advisory scope:
  - Fault classification with confidence
  - Multi-fault probability analysis
  - Operating mode correlation
  - Historical incident matching
  - Recommended diagnostic actions (advisory only)

Zero-Actuation Rule: NEVER issues process control commands.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from backend.agents.industrial.base import AgentAdvisory, AgentSeverity, BaseIndustrialAgent
from backend.services.context_engine import DataProvenance, OperationalContextSnapshot

logger = logging.getLogger("nova.agents.fault")

# Known high-hazard fault classes for this plant
_HIGH_HAZARD_FAULTS = {
    "TUBE_OVERTEMPERATURE",
    "COKING",
    "FURNACE_TRIP",
    "COMPRESSOR_SURGE",
    "HIGH_VIBRATION",
    "SEAL_FAILURE",
    "VESSEL_OVERPRESSURE",
    "FIRE",
    "GAS_RELEASE",
}

_CONFIDENCE_THRESHOLDS = {
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}


class FaultDiagnosisAgent(BaseIndustrialAgent):
    """
    Fault Diagnosis Intelligence Agent.

    Interprets ML fault classification output (from Process Fault Classifier)
    and builds a structured root cause advisory referencing process context.
    """

    def __init__(self) -> None:
        super().__init__(name="FaultDiagnosisAgent")

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

        # ── Fault Classification ──────────────────────────────────────────
        predicted_fault: Optional[str] = None
        fault_conf: Optional[float] = None
        fault_probs: dict = {}
        fault_prov = DataProvenance.MISSING

        if ml and ml.predicted_fault.value is not None:
            predicted_fault = str(ml.predicted_fault.value)
            fault_prov = ml.predicted_fault.provenance
            fault_conf = ml.fault_confidence.value
            evidence["predicted_fault"] = predicted_fault
            evidence["fault_confidence"] = fault_conf

            # Extract top-k from evidence records
            for ev in context.ml_evidence:
                if ev.prediction_type.value == "fault_classification" and ev.prediction:
                    fault_probs = ev.prediction.get("fault_probabilities", {})
                    evidence["fault_probabilities"] = fault_probs
                    model_sources.append(ev.model_name)
                    break

        # ── Severity and findings ─────────────────────────────────────────
        if predicted_fault is None or fault_prov == DataProvenance.MISSING:
            severity = AgentSeverity.NORMAL
            headline = f"[{asset_id}] Fault classifier not available"
            findings.append("Process Fault Classifier model not yet deployed.")
            findings.append("Fault diagnosis is based on alarm state and equipment status only.")
            recommendations.append("Alert Arushi (ML team) to deploy Fault Classifier artifacts.")

        elif predicted_fault.upper() in ("NORMAL", "NONE", "NO_FAULT"):
            severity = AgentSeverity.NORMAL
            headline = f"[{asset_id}] No fault detected — process normal"
            conf_str = f" (confidence={fault_conf:.2f})" if fault_conf else ""
            findings.append(f"Fault Classifier predicts NORMAL operation{conf_str}.")

        else:
            # Determine severity by fault class and confidence
            is_hazard = predicted_fault.upper() in _HIGH_HAZARD_FAULTS
            conf_level = "uncertain" if not fault_conf else (
                "high" if fault_conf >= _CONFIDENCE_THRESHOLDS["high"]
                else "medium" if fault_conf >= _CONFIDENCE_THRESHOLDS["medium"]
                else "low"
            )

            if is_hazard and conf_level in ("high", "medium"):
                severity = AgentSeverity.CRITICAL
            elif is_hazard:
                severity = AgentSeverity.ALERT
            elif conf_level == "high":
                severity = AgentSeverity.WARNING
            else:
                severity = AgentSeverity.ADVISORY

            conf_str = f" (confidence={fault_conf:.2f})" if fault_conf else ""
            headline = f"[{asset_id}] Fault detected: {predicted_fault}{conf_str}"

            findings.append(
                f"Process Fault Classifier identifies: '{predicted_fault}'{conf_str}."
            )
            if is_hazard:
                findings.append(f"'{predicted_fault}' is classified as a HIGH-HAZARD fault type.")
                recommendations.append(f"Immediately notify shift supervisor regarding {predicted_fault} on {asset_id}.")

            # Top alternative faults
            if fault_probs:
                sorted_faults = sorted(fault_probs.items(), key=lambda x: x[1], reverse=True)
                alt_faults = [(f, p) for f, p in sorted_faults if f.upper() != predicted_fault.upper()][:3]
                if alt_faults:
                    alt_str = ", ".join(f"'{f}' ({p:.2f})" for f, p in alt_faults)
                    findings.append(f"Alternative fault hypotheses: {alt_str}.")

            # Generic diagnostic recommendations
            recommendations += self._fault_recommendations(predicted_fault, asset_id)

        # ── Operating mode context ─────────────────────────────────────────
        mode = context.operating_mode.value or "UNKNOWN"
        if mode in ("STARTUP", "SHUTDOWN", "RAMP_UP", "RAMP_DOWN"):
            findings.append(f"Operating mode '{mode}': some fault patterns are transient during mode transitions.")

        # ── Alarm cross-reference ─────────────────────────────────────────
        if context.active_alarms:
            alarm_count = len(context.active_alarms)
            alarm_sev = context.highest_alarm_severity.value or "UNKNOWN"
            findings.append(f"{alarm_count} active alarm(s), highest severity: {alarm_sev}.")

        # ── Historical episodes ────────────────────────────────────────────
        if context.similar_episodes:
            ep = context.similar_episodes[0]
            title = ep.get("title", "Unknown")
            rc = ep.get("root_causes", [])
            if rc:
                findings.append(f"Historical match '{title}' — root causes: {', '.join(rc[:3])}.")

        # ── Risk score ────────────────────────────────────────────────────
        risk_score = None
        if risk_assessment and hasattr(risk_assessment, "risk_score"):
            risk_score = risk_assessment.risk_score

        analysis = self._build_analysis(asset_id, predicted_fault, fault_conf, mode)

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
                "fault_provenance": fault_prov.value,
                "context_providers": context.providers_used,
            },
        )

    def _fault_recommendations(self, fault: str, asset_id: str) -> List[str]:
        """Return fault-type-specific advisory recommendations."""
        recs: List[str] = []
        fu = fault.upper()
        if "TUBE" in fu or "COKING" in fu:
            recs.append(f"Inspect tube skin temperatures and CO in flue gas for {asset_id}.")
            recs.append("Consider decoking schedule review with process engineering.")
        elif "COMPRESSOR" in fu or "VIBRATION" in fu or "SURGE" in fu:
            recs.append(f"Check vibration sensors and bearing temperatures for {asset_id}.")
            recs.append("Verify compressor suction and discharge pressure differential.")
        elif "SEAL" in fu:
            recs.append(f"Inspect mechanical seal system for {asset_id}.")
        elif "PRESSURE" in fu:
            recs.append(f"Check relief valve status and upstream pressure sources for {asset_id}.")
        else:
            recs.append(f"Initiate detailed inspection of {asset_id} with maintenance team.")
        return recs

    def _build_analysis(
        self,
        asset_id: str,
        fault: Optional[str],
        confidence: Optional[float],
        mode: str,
    ) -> str:
        if fault is None:
            return (
                f"Fault classification model is not available for {asset_id}. "
                f"All assessment is based on available alarm state and equipment status. "
                f"Advisory output only — no process actions initiated."
            )
        if fault.upper() in ("NORMAL", "NONE", "NO_FAULT"):
            return (
                f"The Process Fault Classifier indicates normal operation for {asset_id}. "
                f"No fault condition is predicted. Continue standard monitoring. "
                f"Advisory output only."
            )
        conf_str = f" at {confidence:.0%} confidence" if confidence else ""
        return (
            f"The Process Fault Classifier has identified fault pattern '{fault}'{conf_str} "
            f"for asset {asset_id} operating in mode '{mode}'. "
            f"This advisory is for review by a qualified process engineer only. "
            f"No process control actions have been initiated. "
            f"All recommendations require human authorization before any field action."
        )
