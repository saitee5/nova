"""
backend/services/episode_engine.py — Operational Episode Lifecycle Engine.

Tracks, correlates, and persists multi-modal operational episodes across plant assets.
Manages the 7-stage state progression:
NORMAL → DEVIATION → ANOMALY → DIAGNOSIS → ELEVATED_RISK → MITIGATION_OBSERVATION → RESOLVED
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.db.db import get_connection
from backend.models.industrial_domain import (
    Alarm,
    EpisodeStatus,
    IndustrialRiskAssessment,
    MaintenanceRecord,
    MLAssessment,
    OccupancyRecord,
    OperatingMode,
    OperationalEpisode,
    Permit,
    PlantState,
    ProcessTelemetry,
    RiskTier,
)

logger = logging.getLogger("nova.episode_engine")


class OperationalEpisodeEngine:
    """Manages the end-to-end lifecycle of operational process episodes."""

    def __init__(self) -> None:
        self._active_episodes: Dict[str, OperationalEpisode] = {}

    def get_or_create_episode(
        self,
        asset_id: str,
        plant_id: str = "PLANT-ETH-01",
        unit_id: str = "UNIT-CRACK-01",
    ) -> OperationalEpisode:
        """Retrieve the currently open episode for the asset, or initialize a new one in NORMAL state."""
        if asset_id in self._active_episodes:
            return self._active_episodes[asset_id]

        episode_id = f"EP-{asset_id}-{uuid.uuid4().hex[:8]}"
        episode = OperationalEpisode(
            episode_id=episode_id,
            plant_id=plant_id,
            unit_id=unit_id,
            asset_id=asset_id,
            assets=[asset_id],
            operating_mode=OperatingMode.NORMAL,
            status=EpisodeStatus.NORMAL,
            title=f"Operational Monitoring for {asset_id}",
            start_time=datetime.now(timezone.utc),
            severity=RiskTier.LOW,
            provenance={"source": "OperationalEpisodeEngine", "genesis": "nominal_stream"},
        )
        self._active_episodes[asset_id] = episode
        logger.info("Created new operational episode %s for asset %s", episode_id, asset_id)
        return episode

    def transition_status(
        self,
        episode_id: str,
        new_status: EpisodeStatus | str,
        reason: str = "",
    ) -> Optional[OperationalEpisode]:
        """Transition episode along the 7-stage lifecycle progression."""
        target_episode = None
        for ep in self._active_episodes.values():
            if ep.episode_id == episode_id:
                target_episode = ep
                break

        if not target_episode:
            logger.warning("Episode %s not found for transition", episode_id)
            return None

        if isinstance(new_status, str):
            new_status = EpisodeStatus(new_status.upper())

        prev_status = target_episode.status
        target_episode.status = new_status
        logger.info(
            "Episode %s transitioned: %s -> %s | reason: %s",
            episode_id,
            prev_status.value,
            new_status.value,
            reason,
        )

        if new_status == EpisodeStatus.RESOLVED:
            target_episode.end_time = datetime.now(timezone.utc)
            target_episode.outcome = reason or "Resolved under normal operating parameters."
            self._persist_episode(target_episode)
            self._active_episodes.pop(target_episode.asset_id, None)

        return target_episode

    def correlate_observation(
        self,
        asset_id: str,
        telemetry: Optional[ProcessTelemetry] = None,
        ml_assessments: Optional[Dict[str, MLAssessment]] = None,
        alarms: Optional[List[Alarm]] = None,
        permits: Optional[List[Permit]] = None,
        maintenance: Optional[List[MaintenanceRecord]] = None,
        occupancy: Optional[OccupancyRecord] = None,
        risk: Optional[IndustrialRiskAssessment] = None,
    ) -> OperationalEpisode:
        """Correlate telemetry, ML evidence, alarms, SIMOPS, and risk into the asset's active episode."""
        ep = self.get_or_create_episode(asset_id)

        if telemetry:
            key = telemetry.parameter or telemetry.tag
            ep.telemetry_summary[key] = telemetry.value

        if ml_assessments:
            ep.ml_assessments = list(ml_assessments.values())
            # Check for anomaly progression
            anom = ml_assessments.get("anomaly_detection")
            if anom and anom.status in ("OK", "SUCCESS") and (anom.score or 0.0) > 0.5:
                if ep.status in (EpisodeStatus.NORMAL, EpisodeStatus.DEVIATION):
                    self.transition_status(ep.episode_id, EpisodeStatus.ANOMALY, "ML anomaly score exceeded 0.5")

            # Check for fault diagnosis progression
            fault = ml_assessments.get("fault_diagnosis")
            if fault and fault.status in ("OK", "SUCCESS") and fault.prediction:
                if ep.status in (EpisodeStatus.DEVIATION, EpisodeStatus.ANOMALY):
                    self.transition_status(ep.episode_id, EpisodeStatus.DIAGNOSIS, f"Fault diagnosed: {fault.prediction}")

        if alarms:
            ep.alarms = list(alarms)
            if any(a.severity in (RiskTier.HIGH, RiskTier.CRITICAL) for a in alarms):
                if ep.status in (EpisodeStatus.NORMAL, EpisodeStatus.DEVIATION):
                    self.transition_status(ep.episode_id, EpisodeStatus.DEVIATION, "High/Critical alarm active")

        if permits:
            ep.permits = list(permits)
        if maintenance:
            ep.maintenance = list(maintenance)
        if occupancy:
            ep.occupancy = occupancy

        if risk:
            ep.risk_assessment = risk
            ep.severity = risk.risk_tier
            if risk.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL):
                if ep.status not in (EpisodeStatus.ELEVATED_RISK, EpisodeStatus.MITIGATION_OBSERVATION, EpisodeStatus.RESOLVED):
                    self.transition_status(ep.episode_id, EpisodeStatus.ELEVATED_RISK, f"Risk tier escalated to {risk.risk_tier.value}")

        return ep

    def _persist_episode(self, episode: OperationalEpisode) -> None:
        """Persist resolved operational episode into operational_episodes database table."""
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO operational_episodes
                    (episode_id, plant_id, unit_id, asset_id, operating_mode, status, severity, title, start_time, end_time, trigger_json, telemetry_summary_json, risk_score, outcome, provenance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        episode.episode_id,
                        episode.plant_id,
                        episode.unit_id,
                        episode.asset_id,
                        episode.operating_mode.value,
                        episode.status.value,
                        episode.severity.value,
                        episode.title,
                        episode.start_time.isoformat(),
                        episode.end_time.isoformat() if episode.end_time else None,
                        json.dumps(episode.trigger),
                        json.dumps(episode.telemetry_summary),
                        episode.risk_assessment.risk_score if episode.risk_assessment else None,
                        episode.outcome,
                        json.dumps(episode.provenance),
                    ),
                )
            logger.info("Persisted operational episode %s to database", episode.episode_id)
        except Exception as exc:
            logger.warning("Failed to persist operational episode %s: %s", episode.episode_id, exc)

    def list_active_episodes(self) -> List[OperationalEpisode]:
        """Return list of all currently active operational episodes."""
        return list(self._active_episodes.values())

    def get_episode(self, episode_id: str) -> Optional[OperationalEpisode]:
        """Retrieve episode by ID."""
        for ep in self._active_episodes.values():
            if ep.episode_id == episode_id:
                return ep
        return None


# Global singleton instance
episode_engine = OperationalEpisodeEngine()
