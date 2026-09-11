"""
backend/services/industrial_risk_service.py — Industrial Process Risk Evaluation Service.

Evaluates dynamic multi-factor process risk for high-hazard petrochemical assets:
Risk = f(process_anomaly, equipment_condition, operating_state, alarm_state,
          maintenance_state, permit_simops, personnel_exposure, asset_criticality)

Preserves existing security risk calculations in risk_service.py while providing
a separate, dedicated industrial process-risk model for NOVA.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from backend.models.industrial_domain import IndustrialRiskAssessment, RiskTier

logger = logging.getLogger("nova.industrial_risk")


class IndustrialRiskEngine:
    """Multi-factor industrial process risk evaluation engine."""

    def evaluate_asset_risk(
        self,
        asset_id: str,
        process_anomaly_score: float = 0.0,       # 0.0 to 1.0
        equipment_condition_score: float = 0.0,   # 0.0 to 1.0 (0=healthy, 1=degraded/fault)
        alarm_severity: str = "LOW",               # LOW, MEDIUM, HIGH, CRITICAL
        has_active_permit: bool = False,
        is_simops: bool = False,                   # Simultaneous operations
        personnel_count_in_zone: int = 0,
        asset_criticality: str = "MEDIUM",
    ) -> IndustrialRiskAssessment:
        """Calculate dynamic multi-factor industrial risk score [0.0, 1.0]."""
        alarm_weights = {"LOW": 0.05, "MEDIUM": 0.3, "HIGH": 0.6, "CRITICAL": 1.0}
        alarm_factor = alarm_weights.get(alarm_severity.upper(), 0.05)

        permit_factor = 0.4 if (has_active_permit and is_simops) else (0.2 if has_active_permit else 0.0)
        personnel_factor = min(0.3, personnel_count_in_zone * 0.05)

        crit_weights = {"LOW": 0.7, "MEDIUM": 1.0, "HIGH": 1.25, "CRITICAL": 1.5}
        crit_multiplier = crit_weights.get(asset_criticality.upper(), 1.0)

        raw_score = (
            process_anomaly_score * 0.35 +
            equipment_condition_score * 0.25 +
            alarm_factor * 0.20 +
            permit_factor * 0.10 +
            personnel_factor * 0.10
        ) * crit_multiplier

        final_score = round(max(0.0, min(1.0, raw_score)), 3)

        if final_score >= 0.75:
            tier = RiskTier.CRITICAL
        elif final_score >= 0.50:
            tier = RiskTier.HIGH
        elif final_score >= 0.25:
            tier = RiskTier.MEDIUM
        else:
            tier = RiskTier.LOW

        recommendations = []
        if tier in (RiskTier.HIGH, RiskTier.CRITICAL):
            recommendations.append(f"Notify unit shift supervisor for asset {asset_id}.")
            if has_active_permit:
                recommendations.append("Review active Permit-to-Work for SIMOPS conflict.")
            if personnel_count_in_zone > 0:
                recommendations.append("Verify personnel safety distance and PPE requirements.")
        else:
            recommendations.append("Maintain standard process monitoring.")

        return IndustrialRiskAssessment(
            assessment_id=f"IRA-{uuid.uuid4().hex[:8]}",
            asset_id=asset_id,
            timestamp=datetime.now(timezone.utc),
            risk_score=final_score,
            risk_tier=tier,
            process_anomaly_factor=process_anomaly_score,
            equipment_condition_factor=equipment_condition_score,
            alarm_state_factor=alarm_factor,
            permit_simops_factor=permit_factor,
            personnel_exposure_factor=personnel_factor,
            explanation=f"Industrial risk evaluated at {final_score:.2f} ({tier.value}) for {asset_id}.",
            recommended_actions=recommendations,
        )


# Global singleton instance
industrial_risk_engine = IndustrialRiskEngine()
