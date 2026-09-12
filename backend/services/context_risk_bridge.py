"""
backend/services/context_risk_bridge.py — Context → Risk Engine Bridge.

This module provides a thin, deterministic bridge that:
  1. Receives an OperationalContextSnapshot (from ContextEngine)
  2. Extracts the relevant risk factors
  3. Calls IndustrialRiskEngine.evaluate_asset_risk()
  4. Returns an IndustrialRiskAssessment enriched with context provenance

Design:
  ContextEngine  →  ContextRiskBridge  →  IndustrialRiskEngine
                                                    ↓
                                        IndustrialRiskAssessment

This preserves the IndustrialRiskEngine as a pure, deterministic function.
The bridge handles the mapping from rich context → risk factor scalars.

Zero-Actuation Rule:
  This bridge is read-only / advisory. Never issues commands.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.models.industrial_domain import IndustrialRiskAssessment
from backend.services.context_engine import DataProvenance, OperationalContextSnapshot
from backend.services.industrial_risk_service import IndustrialRiskEngine

logger = logging.getLogger("nova.context_risk_bridge")

# Severity → scalar mapping (matches IndustrialRiskEngine internal logic)
_ALARM_SEVERITY_MAP = {
    None: "LOW",
    "": "LOW",
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}


class ContextRiskBridge:
    """
    Bridges OperationalContextSnapshot → IndustrialRiskAssessment.

    Extracts risk factor scalars from the context snapshot and delegates
    scoring to the existing IndustrialRiskEngine.
    """

    def __init__(self, risk_engine: Optional[IndustrialRiskEngine] = None) -> None:
        self._risk_engine = risk_engine or IndustrialRiskEngine()

    def evaluate(
        self,
        context: OperationalContextSnapshot,
    ) -> IndustrialRiskAssessment:
        """
        Evaluate risk from the assembled operational context.

        Args:
            context: Assembled OperationalContextSnapshot from ContextEngine.

        Returns:
            IndustrialRiskAssessment with risk_score, tier, factors, recommendations.
        """
        asset_id = context.asset_id

        # ── ML anomaly score ──────────────────────────────────────────────
        # Use ML anomaly score when available; degrade to 0.0 (not fabricate)
        anomaly_score = 0.0
        if (
            context.ml_summary is not None
            and context.ml_summary.anomaly_score.provenance == DataProvenance.PREDICTED
            and context.ml_summary.anomaly_score.value is not None
        ):
            anomaly_score = float(context.ml_summary.anomaly_score.value)

        # ── Equipment condition ───────────────────────────────────────────
        equipment_condition = context.equipment_condition_score

        # ── Alarm severity ────────────────────────────────────────────────
        alarm_sev_raw = context.highest_alarm_severity.value
        alarm_severity = _ALARM_SEVERITY_MAP.get(
            str(alarm_sev_raw).upper() if alarm_sev_raw else None,
            "LOW",
        )

        # ── Permit / SIMOPS ───────────────────────────────────────────────
        has_active_permit = len(context.active_permits) > 0
        is_simops = bool(context.is_simops.value)

        # ── Personnel ─────────────────────────────────────────────────────
        personnel_count = 0
        if (
            context.personnel_count.value is not None
            and context.personnel_count.provenance != DataProvenance.MISSING
        ):
            personnel_count = int(context.personnel_count.value)

        # ── Asset criticality ─────────────────────────────────────────────
        criticality = "MEDIUM"
        if (
            context.asset_criticality.value is not None
            and context.asset_criticality.provenance != DataProvenance.MISSING
        ):
            criticality = str(context.asset_criticality.value).upper()

        # ── Model versions from ML evidence ───────────────────────────────
        model_versions: Dict[str, str] = {}
        if context.ml_summary:
            model_versions = dict(context.ml_summary.model_versions)

        logger.debug(
            "ContextRiskBridge.evaluate: asset=%s anomaly=%.3f equipment=%.3f alarm=%s "
            "simops=%s personnel=%d criticality=%s",
            asset_id, anomaly_score, equipment_condition, alarm_severity,
            is_simops, personnel_count, criticality,
        )

        assessment = self._risk_engine.evaluate_asset_risk(
            asset_id=asset_id,
            process_anomaly_score=anomaly_score,
            equipment_condition_score=equipment_condition,
            alarm_severity=alarm_severity,
            has_active_permit=has_active_permit,
            is_simops=is_simops,
            personnel_count_in_zone=personnel_count,
            asset_criticality=criticality,
            model_versions=model_versions,
        )

        # Annotate assessment with context traceability
        assessment.factors["context_id"] = context.context_id
        assessment.factors["context_warnings"] = len(context.warnings)
        assessment.factors["context_providers"] = ",".join(context.providers_used)
        assessment.factors["anomaly_provenance"] = (
            context.ml_summary.anomaly_score.provenance.value
            if context.ml_summary
            else "MISSING"
        )

        return assessment


# Module-level singleton
context_risk_bridge = ContextRiskBridge()
