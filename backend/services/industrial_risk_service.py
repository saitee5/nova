"""
backend/services/industrial_risk_service.py — Industrial Process Risk Evaluation Service.

Evaluates dynamic multi-factor process risk for high-hazard petrochemical assets:
Risk = f(process_anomaly, equipment_condition, operating_state, alarm_state,
          maintenance_state, permit_simops, personnel_exposure, asset_criticality)

Deterministic, fully explainable, safety-instrumented advisory architecture.
Preserves existing security risk calculations in risk_service.py while providing
a separate, dedicated industrial process-risk model for NOVA.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config_reference_plant import REFERENCE_ASSETS
from backend.models.industrial_domain import (
    IndustrialRiskAssessment,
    MLAssessment,
    OperatingMode,
    PlantState,
    RiskTier,
)

logger = logging.getLogger("nova.industrial_risk")


class IndustrialRiskEngine:
    """Multi-factor industrial process risk evaluation engine."""

    def __init__(self, policy_version: str = "1.0") -> None:
        self.policy_version = policy_version
        self._asset_criticality_map: Dict[str, str] = {
            a["asset_id"]: a.get("criticality", "MEDIUM") for a in REFERENCE_ASSETS
        }

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
        model_versions: Optional[Dict[str, str]] = None,
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

        recommendations: List[str] = []
        if tier in (RiskTier.HIGH, RiskTier.CRITICAL):
            recommendations.append(f"Notify unit shift supervisor for asset {asset_id}.")
            if has_active_permit or is_simops:
                recommendations.append("Review active Permit-to-Work for SIMOPS conflict.")
            if personnel_count_in_zone > 0:
                recommendations.append("Verify personnel safety distance and PPE requirements.")
        else:
            recommendations.append("Maintain standard process monitoring.")

        factors_dict = {
            "process_anomaly": round(process_anomaly_score, 4),
            "equipment_condition": round(equipment_condition_score, 4),
            "alarm_state": round(alarm_factor, 4),
            "permit_simops": round(permit_factor, 4),
            "personnel_exposure": round(personnel_factor, 4),
            "criticality_multiplier": crit_multiplier,
        }

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
            factors=factors_dict,
            policy_version=self.policy_version,
            model_versions=model_versions or {},
            advisory_only=True,
            explanation=f"Industrial risk evaluated at {final_score:.2f} ({tier.value}) for {asset_id}.",
            recommended_actions=recommendations,
        )

    def evaluate_plant_state(
        self,
        plant_state: PlantState,
        ml_assessments: Optional[Dict[str, MLAssessment]] = None,
        target_asset_id: Optional[str] = None,
    ) -> IndustrialRiskAssessment:
        """Evaluate deterministic industrial risk directly from a PlantState context snapshot."""
        asset_id = target_asset_id or "F-201A"
        criticality = self._asset_criticality_map.get(asset_id, "MEDIUM")

        # Process anomaly factor from ML assessment if available
        anomaly_score = 0.0
        model_versions: Dict[str, str] = {}
        if ml_assessments:
            anom = ml_assessments.get("anomaly_detection")
            if anom and anom.status in ("OK", "SUCCESS") and anom.score is not None:
                anomaly_score = float(anom.score)
                model_versions["anomaly_detection"] = anom.model_version
            elif anom and anom.status == "MODEL_NOT_AVAILABLE":
                model_versions["anomaly_detection"] = f"{anom.model_version} (UNAVAILABLE)"

        # Equipment condition factor
        eq_status = plant_state.equipment_status.get(asset_id, "HEALTHY").upper()
        eq_score_map = {"HEALTHY": 0.0, "OPERATIONAL": 0.0, "WARNING": 0.35, "DEGRADED": 0.70, "FAULT": 1.0}
        equipment_condition_score = eq_score_map.get(eq_status, 0.2)

        # Alarm severity factor
        highest_alarm = "LOW"
        for alarm in plant_state.active_alarms:
            if alarm.asset_id == asset_id or not alarm.asset_id:
                if alarm.severity == RiskTier.CRITICAL:
                    highest_alarm = "CRITICAL"
                    break
                elif alarm.severity == RiskTier.HIGH and highest_alarm != "CRITICAL":
                    highest_alarm = "HIGH"
                elif alarm.severity == RiskTier.MEDIUM and highest_alarm in ("LOW",):
                    highest_alarm = "MEDIUM"

        has_active_permit = len(plant_state.active_permits) > 0
        is_simops = plant_state.metadata.get("simops_active", False) or (
            has_active_permit and len(plant_state.active_maintenance) > 0
        )
        personnel_count = sum(plant_state.occupancy.values()) if plant_state.occupancy else 0

        # Adjust for high-hazard operating modes
        if plant_state.operating_mode in (OperatingMode.EMERGENCY, OperatingMode.EMERGENCY_TRIP):
            highest_alarm = "CRITICAL"
            equipment_condition_score = max(equipment_condition_score, 0.9)

        return self.evaluate_asset_risk(
            asset_id=asset_id,
            process_anomaly_score=anomaly_score,
            equipment_condition_score=equipment_condition_score,
            alarm_severity=highest_alarm,
            has_active_permit=has_active_permit,
            is_simops=is_simops,
            personnel_count_in_zone=personnel_count,
            asset_criticality=criticality,
            model_versions=model_versions,
        )


# Global singleton instance
industrial_risk_engine = IndustrialRiskEngine()
