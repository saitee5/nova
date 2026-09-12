"""
backend/services/providers/interfaces.py — Provider Interface Contracts.

Defines abstract base classes for all data sources consumed by the
intelligence layer. The intelligence layer (Context, Risk, Episode, Agents)
depends ONLY on these interfaces, never on storage implementations directly.

Arushi will supply:
  - PostgreSQL-backed TelemetryProvider / AlarmProvider / etc.
  - RAG-based KnowledgeProvider
  - Knowledge-Graph-based HistoricalEpisodeProvider

Until those arrive, use the default_providers.py implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class TelemetryProvider(ABC):
    """Abstract interface for process telemetry data access."""

    @abstractmethod
    def get_latest(self, asset_id: str) -> Dict[str, Any]:
        """
        Return the most recent telemetry snapshot for the asset.

        Returns a dict: {parameter: {value, unit, timestamp, quality, ...}}
        """

    @abstractmethod
    def get_window(
        self,
        asset_id: str,
        parameter: str,
        since: datetime,
    ) -> List[Dict[str, Any]]:
        """Return historical telemetry points for a parameter in [since, now]."""

    @abstractmethod
    def get_sensor_health(self, asset_id: str) -> Dict[str, str]:
        """
        Return sensor health status per parameter.
        Values: GOOD | UNCERTAIN | BAD | MISSING
        """


class AlarmProvider(ABC):
    """Abstract interface for industrial alarm data access."""

    @abstractmethod
    def get_active_alarms(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all active (non-resolved) alarms, optionally filtered by asset."""

    @abstractmethod
    def get_alarm_history(
        self,
        asset_id: str,
        since: datetime,
    ) -> List[Dict[str, Any]]:
        """Return historical alarms for the asset since the given time."""


class AssetProvider(ABC):
    """Abstract interface for plant / unit / asset topology data."""

    @abstractmethod
    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific asset."""

    @abstractmethod
    def get_assets_for_unit(self, unit_id: str) -> List[Dict[str, Any]]:
        """Return all assets belonging to a unit."""

    @abstractmethod
    def get_equipment_status(self, asset_id: str) -> str:
        """
        Return equipment health string for the asset.
        Values: HEALTHY | OPERATIONAL | WARNING | DEGRADED | FAULT | UNKNOWN
        """

    @abstractmethod
    def get_asset_criticality(self, asset_id: str) -> str:
        """
        Return criticality tier string.
        Values: LOW | MEDIUM | HIGH | CRITICAL
        """


class MaintenanceProvider(ABC):
    """Abstract interface for maintenance work order and activity data."""

    @abstractmethod
    def get_active_maintenance(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all active maintenance records, optionally filtered by asset."""

    @abstractmethod
    def get_maintenance_history(
        self,
        asset_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return the N most recent completed maintenance records for the asset."""


class PermitProvider(ABC):
    """Abstract interface for Permit-to-Work (PTW) data access."""

    @abstractmethod
    def get_active_permits(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all active permits, optionally filtered by asset or zone."""

    @abstractmethod
    def is_simops_active(self, asset_id: str) -> bool:
        """
        Return True if simultaneous high-hazard operations (SIMOPS) are active
        for this asset — i.e. an active hot-work or confined-space permit overlaps
        with active maintenance.
        """


class OperationsProvider(ABC):
    """Abstract interface for operational state data (mode, shift, occupancy)."""

    @abstractmethod
    def get_operating_mode(self, plant_id: str = "PLANT-ETH-01") -> str:
        """
        Return current plant operating mode string.
        Values: NORMAL | STARTUP | SHUTDOWN | TURNDOWN | MAINTENANCE | DEGRADED |
                EMERGENCY | EMERGENCY_TRIP | STEADY_STATE | UNKNOWN
        """

    @abstractmethod
    def get_occupancy(self, zone_id: Optional[str] = None) -> Dict[str, int]:
        """Return zone_id → personnel count mapping, optionally for a specific zone."""

    @abstractmethod
    def is_personnel_in_zone(self, zone_id: str) -> bool:
        """Return True if any personnel are logged in the zone."""


class HistoricalEpisodeProvider(ABC):
    """
    Abstract interface for historical operational episode and incident retrieval.
    Arushi will implement this using the Knowledge Graph / Qdrant / PostgreSQL.
    """

    @abstractmethod
    def search_similar_episodes(
        self,
        query: str,
        asset_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the K most similar historical episodes to the query.

        Each result should include at minimum:
          - episode_id
          - title
          - asset_id
          - similarity_score
          - root_causes
          - outcome
          - summary
          - date
        """

    @abstractmethod
    def get_episode_by_id(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Return a specific historical episode by ID."""


class KnowledgeProvider(ABC):
    """
    Abstract interface for engineering knowledge retrieval.
    Arushi will implement this using RAG / Knowledge Base / Knowledge Graph.
    """

    @abstractmethod
    def search_knowledge(
        self,
        query: str,
        asset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the K most relevant knowledge references.

        Each result should include at minimum:
          - source (document title / procedure ID)
          - section
          - content or reference summary
          - relevance_score
          - asset_id or equipment_class (if applicable)
          - knowledge_type: SOP | DESIGN | LIMIT | PROCEDURE | MAINTENANCE
        """

    @abstractmethod
    def get_operating_limits(
        self,
        asset_id: str,
        parameter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return configured operating limits for the asset.

        Returns dict: {parameter: {low_low, low, high, high_high, unit, source}}
        Returns empty dict (not fake limits) when limits are not configured.
        """
