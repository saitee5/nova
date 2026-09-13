"""
backend/services/plant_state_service.py — Industrial Plant State Aggregation Service.

Maintains the authoritative in-memory current state snapshot of the industrial plant:
PlantState = f(telemetry, alarms, equipment_condition, maintenance, permits, occupancy, operating_mode, recent_events)

Primary context object consumed by downstream intelligence layers (Feature Engine, ML Pipeline,
Industrial Risk Engine, Operational Episode Engine, and Evidence Package).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.config_reference_plant import REFERENCE_PLANT, REFERENCE_ASSETS
from backend.models.industrial_domain import (
    Alarm,
    MaintenanceRecord,
    OccupancyRecord,
    OperatingMode,
    OperationalEvent,
    PlantState,
    ProcessTelemetry,
    RiskTier,
    SensorQuality,
)

logger = logging.getLogger("nova.plant_state")


class PlantStateService:
    """Singleton service managing dynamic, multi-modal industrial plant state."""

    def __init__(self, plant_id: str = "PLANT-ETH-01", unit_id: str = "UNIT-CRACK-01") -> None:
        self.plant_id = plant_id
        self.unit_id = unit_id
        self.operating_mode = OperatingMode.NORMAL
        self._telemetry: Dict[str, ProcessTelemetry] = {}
        self._active_alarms: Dict[str, Alarm] = {}
        self._equipment_status: Dict[str, str] = {}
        self._active_maintenance: Dict[str, MaintenanceRecord] = {}
        self._active_permits: Dict[str, Any] = {}
        self._occupancy: Dict[str, int] = {}
        self._recent_events: List[OperationalEvent] = []
        self._max_recent_events = 100

        # Seed initial equipment statuses from reference assets catalog
        for asset in REFERENCE_ASSETS:
            self._equipment_status[asset["asset_id"]] = "OPERATIONAL"

    def get_current_state(self) -> PlantState:
        """Construct and return the current snapshot of PlantState."""
        # Derive KPIs dynamically from active telemetry observations
        throughput_val = 0.0
        power_val = 0.0
        co2_val = 0.0
        for tel in self._telemetry.values():
            tag = (tel.tag or "").upper()
            param = (tel.parameter or "").upper()
            val = float(tel.value or 0.0)
            if "FC" in tag or "FLOW" in tag or "FEED" in param:
                throughput_val = round(val / 1000.0 if val > 1000 else val, 2)
            elif "PWR" in tag or "POWER" in tag or "KW" in param or "MW" in param:
                power_val = round(val / 1000.0 if val > 1000 else val, 2)
            elif "CO2" in tag or "EMISSION" in tag:
                co2_val = round(val, 2)

        return PlantState(
            plant_id=self.plant_id,
            unit_id=self.unit_id,
            timestamp=datetime.now(timezone.utc),
            operating_mode=self.operating_mode,
            telemetry=dict(self._telemetry),
            active_alarms=list(self._active_alarms.values()),
            equipment_status=dict(self._equipment_status),
            active_maintenance=list(self._active_maintenance.values()),
            active_permits=list(self._active_permits.values()),
            occupancy=dict(self._occupancy),
            recent_events=list(self._recent_events[-20:]),
            metadata={
                "total_telemetry_points": len(self._telemetry),
                "total_active_alarms": len(self._active_alarms),
                "simops_active": self.is_simops_active(),
                "throughput_tph": throughput_val,
                "power_mw": power_val,
                "co2_rate_tph": co2_val,
                "safety_status": (
                    "Alert" if any(a.severity == RiskTier.CRITICAL for a in self._active_alarms.values())
                    else ("Warning" if len(self._active_alarms) > 0 else "Normal")
                ),
            },
        )

    def update_telemetry(self, telemetry: ProcessTelemetry | Dict[str, Any]) -> ProcessTelemetry:
        """Update or ingest a canonical telemetry observation."""
        if isinstance(telemetry, dict):
            # Parse dict into canonical ProcessTelemetry
            telemetry = ProcessTelemetry(**telemetry)
        
        key = f"{telemetry.asset_id}:{telemetry.parameter or telemetry.tag}"
        self._telemetry[key] = telemetry
        logger.debug("Updated telemetry for %s = %.2f %s", key, telemetry.value, telemetry.unit)
        return telemetry

    def update_alarm(self, alarm: Alarm | Dict[str, Any]) -> Alarm:
        """Register or update an operational alarm."""
        if isinstance(alarm, dict):
            alarm = Alarm(**alarm)
        if alarm.state.upper() in ("RESOLVED", "CLEARED", "INACTIVE"):
            self._active_alarms.pop(alarm.alarm_id, None)
        else:
            self._active_alarms[alarm.alarm_id] = alarm
        return alarm

    def update_maintenance(self, record: MaintenanceRecord | Dict[str, Any]) -> MaintenanceRecord:
        """Update maintenance record state."""
        if isinstance(record, dict):
            record = MaintenanceRecord(**record)
        if record.status.upper() in ("COMPLETED", "CLOSED", "CANCELLED"):
            self._active_maintenance.pop(record.record_id, None)
        else:
            self._active_maintenance[record.record_id] = record
        return record

    def update_permit(self, permit: Any) -> Any:
        """Update active permit status."""
        permit_id = getattr(permit, "permit_id", None) or (permit.get("permit_id") if isinstance(permit, dict) else None)
        status = getattr(permit, "status", None) or (permit.get("status") if isinstance(permit, dict) else "ACTIVE")
        if permit_id:
            if str(status).upper() in ("CLOSED", "EXPIRED", "CANCELLED"):
                self._active_permits.pop(permit_id, None)
            else:
                self._active_permits[permit_id] = permit
        return permit

    def update_occupancy(self, zone_id: str, count: int) -> None:
        """Update zone personnel headcount."""
        self._occupancy[zone_id] = max(0, count)

    def update_operating_mode(self, mode: OperatingMode | str) -> None:
        """Set the global operating mode for the plant."""
        if isinstance(mode, str):
            mode = OperatingMode(mode.upper())
        self.operating_mode = mode

    def update_equipment_status(self, asset_id: str, status: str) -> None:
        """Update equipment health/availability status."""
        self._equipment_status[asset_id] = status.upper()

    def record_event(self, event: OperationalEvent | Dict[str, Any]) -> OperationalEvent:
        """Record an operational event in recent timeline history."""
        if isinstance(event, dict):
            event = OperationalEvent(**event)
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)
        return event

    def is_simops_active(self) -> bool:
        """Determine if simultaneous high-hazard operations are active."""
        has_permits = len(self._active_permits) > 0
        has_maint = len(self._active_maintenance) > 0
        return has_permits and has_maint

    def reset_state(self) -> None:
        """Reset state to baseline nominal defaults (used in testing)."""
        self.operating_mode = OperatingMode.NORMAL
        self._telemetry.clear()
        self._active_alarms.clear()
        self._active_maintenance.clear()
        self._active_permits.clear()
        self._occupancy.clear()
        self._recent_events.clear()
        for asset in REFERENCE_ASSETS:
            self._equipment_status[asset["asset_id"]] = "OPERATIONAL"


# Global singleton instance
plant_state_service = PlantStateService()
