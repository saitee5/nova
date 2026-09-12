"""
backend/services/providers/default_providers.py — Default / In-Memory Provider Implementations.

These lightweight providers satisfy the provider interfaces using:
  - PlantStateService (live in-memory state)
  - Static reference plant configuration

They are suitable for:
  - Unit tests
  - Integration tests
  - Simulator-driven development

Arushi's PostgreSQL / RAG / Knowledge Graph implementations will
replace these through the same provider interfaces without requiring
changes to Context, Risk, Episode, or Agent logic.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config_reference_plant import REFERENCE_ASSETS
from backend.services.providers.interfaces import (
    AlarmProvider,
    AssetProvider,
    HistoricalEpisodeProvider,
    KnowledgeProvider,
    MaintenanceProvider,
    OperationsProvider,
    PermitProvider,
    TelemetryProvider,
)

logger = logging.getLogger("nova.providers.default")

# ---------------------------------------------------------------------------
# Asset criticality / status lookup maps from reference plant config
# ---------------------------------------------------------------------------
_ASSET_CRITICALITY: Dict[str, str] = {
    a["asset_id"]: a.get("criticality", "MEDIUM") for a in REFERENCE_ASSETS
}
_ASSET_METADATA: Dict[str, Dict[str, Any]] = {
    a["asset_id"]: a for a in REFERENCE_ASSETS
}


# ---------------------------------------------------------------------------
# Telemetry Provider (PlantState-backed)
# ---------------------------------------------------------------------------

class PlantStateTelemetryProvider(TelemetryProvider):
    """Read telemetry from the live in-memory PlantStateService."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_latest(self, asset_id: str) -> Dict[str, Any]:
        state = self._svc.get_current_state()
        readings: Dict[str, Any] = {}
        for key, t in state.telemetry.items():
            if t.asset_id == asset_id:
                param = t.parameter or t.tag or key
                readings[param] = {
                    "value": t.value,
                    "unit": t.unit,
                    "timestamp": t.timestamp.isoformat(),
                    "quality": t.quality.value,
                    "source": t.source,
                    "asset_id": t.asset_id,
                }
        return readings

    def get_window(
        self,
        asset_id: str,
        parameter: str,
        since: datetime,
    ) -> List[Dict[str, Any]]:
        # In-memory provider only holds the latest snapshot.
        # Return the latest point if it exists and is not stale.
        latest = self.get_latest(asset_id)
        point = latest.get(parameter)
        if not point:
            return []
        ts = datetime.fromisoformat(point["timestamp"])
        if ts >= since:
            return [point]
        return []

    def get_sensor_health(self, asset_id: str) -> Dict[str, str]:
        state = self._svc.get_current_state()
        health: Dict[str, str] = {}
        for key, t in state.telemetry.items():
            if t.asset_id == asset_id:
                param = t.parameter or t.tag or key
                health[param] = t.quality.value
        return health


# ---------------------------------------------------------------------------
# Alarm Provider (PlantState-backed)
# ---------------------------------------------------------------------------

class PlantStateAlarmProvider(AlarmProvider):
    """Read alarms from the live in-memory PlantStateService."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_active_alarms(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._svc.get_current_state()
        alarms = [a.model_dump() for a in state.active_alarms]
        if asset_id:
            alarms = [a for a in alarms if a.get("asset_id") == asset_id]
        return alarms

    def get_alarm_history(self, asset_id: str, since: datetime) -> List[Dict[str, Any]]:
        # In-memory: return currently active alarms as history proxy
        return self.get_active_alarms(asset_id)


# ---------------------------------------------------------------------------
# Asset Provider (Reference Plant-backed)
# ---------------------------------------------------------------------------

class PlantStateAssetProvider(AssetProvider):
    """Asset topology from reference plant config + live equipment status."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        return _ASSET_METADATA.get(asset_id)

    def get_assets_for_unit(self, unit_id: str) -> List[Dict[str, Any]]:
        return [a for a in REFERENCE_ASSETS if a.get("unit_id") == unit_id]

    def get_equipment_status(self, asset_id: str) -> str:
        state = self._svc.get_current_state()
        return state.equipment_status.get(asset_id, "UNKNOWN")

    def get_asset_criticality(self, asset_id: str) -> str:
        return _ASSET_CRITICALITY.get(asset_id, "MEDIUM")


# ---------------------------------------------------------------------------
# Maintenance Provider (PlantState-backed)
# ---------------------------------------------------------------------------

class PlantStateMaintenanceProvider(MaintenanceProvider):
    """Read maintenance records from the live in-memory PlantStateService."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_active_maintenance(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._svc.get_current_state()
        records = [m.model_dump() for m in state.active_maintenance]
        if asset_id:
            records = [r for r in records if r.get("asset_id") == asset_id]
        return records

    def get_maintenance_history(self, asset_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.get_active_maintenance(asset_id)[:limit]


# ---------------------------------------------------------------------------
# Permit Provider (PlantState-backed)
# ---------------------------------------------------------------------------

class PlantStatePermitProvider(PermitProvider):
    """Read active permits from the live in-memory PlantStateService."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_active_permits(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._svc.get_current_state()
        permits: List[Dict[str, Any]] = []
        for p in state.active_permits:
            d = p.model_dump() if hasattr(p, "model_dump") else (p if isinstance(p, dict) else vars(p))
            if asset_id is None or d.get("asset_id") == asset_id:
                permits.append(d)
        return permits

    def is_simops_active(self, asset_id: str) -> bool:
        state = self._svc.get_current_state()
        return bool(state.metadata.get("simops_active", False))


# ---------------------------------------------------------------------------
# Operations Provider (PlantState-backed)
# ---------------------------------------------------------------------------

class PlantStateOperationsProvider(OperationsProvider):
    """Read operating mode and occupancy from the live PlantStateService."""

    def __init__(self, plant_state_service=None) -> None:
        if plant_state_service is None:
            from backend.services.plant_state_service import plant_state_service as _svc
            plant_state_service = _svc
        self._svc = plant_state_service

    def get_operating_mode(self, plant_id: str = "PLANT-ETH-01") -> str:
        return self._svc.get_current_state().operating_mode.value

    def get_occupancy(self, zone_id: Optional[str] = None) -> Dict[str, int]:
        state = self._svc.get_current_state()
        occ = state.occupancy
        if zone_id is not None:
            return {zone_id: occ.get(zone_id, 0)}
        return dict(occ)

    def is_personnel_in_zone(self, zone_id: str) -> bool:
        occ = self.get_occupancy(zone_id)
        return occ.get(zone_id, 0) > 0


# ---------------------------------------------------------------------------
# Historical Episode Provider (In-memory stub)
# ---------------------------------------------------------------------------

class InMemoryHistoricalEpisodeProvider(HistoricalEpisodeProvider):
    """
    Stub implementation. Returns empty or seeded historical episodes.

    Arushi will replace this with a Qdrant/Knowledge-Graph implementation
    that retrieves semantically similar historical incidents.
    """

    def __init__(self, episodes: Optional[List[Dict[str, Any]]] = None) -> None:
        self._episodes: List[Dict[str, Any]] = episodes or []

    def seed(self, episodes: List[Dict[str, Any]]) -> None:
        """Seed with historical episode records for testing."""
        self._episodes = list(episodes)

    def search_similar_episodes(
        self,
        query: str,
        asset_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        results = list(self._episodes)
        if asset_id:
            results = [e for e in results if e.get("asset_id") == asset_id]
        # Simple keyword overlap scoring
        query_tokens = set(query.lower().split())
        scored = []
        for ep in results:
            text = " ".join([
                ep.get("title", ""),
                ep.get("summary", ""),
                " ".join(ep.get("root_causes", [])),
            ]).lower()
            score = sum(1 for tok in query_tokens if tok in text) / max(len(query_tokens), 1)
            scored.append({**ep, "similarity_score": round(score, 3)})
        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_k]

    def get_episode_by_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        for ep in self._episodes:
            if ep.get("episode_id") == episode_id:
                return ep
        return None


# ---------------------------------------------------------------------------
# Knowledge Provider (Stub)
# ---------------------------------------------------------------------------

class StubKnowledgeProvider(KnowledgeProvider):
    """
    Stub knowledge provider. Returns empty results.

    Arushi will replace this with a RAG / Knowledge Base / Knowledge Graph
    implementation once her knowledge infrastructure is ready.
    """

    def search_knowledge(
        self,
        query: str,
        asset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        logger.debug(
            "StubKnowledgeProvider.search_knowledge called (no KB available yet): query=%s", query
        )
        return []

    def get_operating_limits(
        self,
        asset_id: str,
        parameter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return empty dict — limits not configured in stub.

        IMPORTANT: Returns {} rather than silently fabricating limits.
        The Risk Engine must handle NOT_CONFIGURED explicitly.
        """
        logger.debug(
            "StubKnowledgeProvider.get_operating_limits: no limits configured for %s", asset_id
        )
        return {}
