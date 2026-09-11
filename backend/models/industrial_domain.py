"""
backend/models/industrial_domain.py — Petrochemical Industrial Domain Models.

Provides Pydantic models for plants, units, assets, equipment, sensors, tags,
alarms, maintenance records, permits, occupancy, operational episodes,
ML assessments, and industrial risk assessments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OperatingMode(str, Enum):
    NORMAL = "NORMAL"
    STARTUP = "STARTUP"
    SHUTDOWN = "SHUTDOWN"
    TURNDOWN = "TURNDOWN"
    HOT_STANDBY = "HOT_STANDBY"
    MAINTENANCE = "MAINTENANCE"
    DEGRADED = "DEGRADED"
    EMERGENCY_TRIP = "EMERGENCY_TRIP"


class SensorQuality(str, Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    SUBSTITUTED = "SUBSTITUTED"


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProcessTelemetry(BaseModel):
    """Standardized industrial process telemetry record."""
    asset_id: str
    tag: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    value: float
    unit: str
    quality: SensorQuality = SensorQuality.GOOD
    source: str = "dcs"
    operating_mode: OperatingMode = OperatingMode.NORMAL


class OperationalEvent(BaseModel):
    """Standardized operational event payload."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    asset_id: str
    event_type: str
    source: str
    schema_version: str = "1.0"
    payload: Dict[str, Any] = Field(default_factory=dict)


class Plant(BaseModel):
    plant_id: str
    name: str
    location: str
    units: List[str] = Field(default_factory=list)


class Unit(BaseModel):
    unit_id: str
    plant_id: str
    name: str
    unit_type: str  # e.g., "Ethylene Steam Cracking"
    assets: List[str] = Field(default_factory=list)


class Asset(BaseModel):
    asset_id: str
    unit_id: str
    name: str
    asset_class: str  # e.g. "Furnace", "Compressor", "Exchanger"
    criticality: RiskTier = RiskTier.MEDIUM
    operating_mode: OperatingMode = OperatingMode.NORMAL
    tags: List[str] = Field(default_factory=list)


class Equipment(BaseModel):
    equipment_id: str
    asset_id: str
    name: str
    equipment_type: str
    status: str = "HEALTHY"
    last_serviced: Optional[datetime] = None


class Sensor(BaseModel):
    sensor_id: str
    tag: str
    equipment_id: str
    sensor_type: str  # e.g. "Temperature", "Pressure", "Flow", "Vibration"
    unit: str
    min_range: float
    max_range: float
    alarm_high: float
    alarm_low: float


class ProcessTag(BaseModel):
    tag: str
    description: str
    unit: str
    current_value: Optional[float] = None
    quality: SensorQuality = SensorQuality.GOOD


class Alarm(BaseModel):
    alarm_id: str
    tag: str
    asset_id: str
    severity: RiskTier
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class MaintenanceRecord(BaseModel):
    record_id: str
    asset_id: str
    work_order: str
    description: str
    logged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "OPEN"


class Permit(BaseModel):
    permit_id: str
    permit_type: str  # e.g., "Hot Work", "Vessel Entry"
    asset_id: str
    issued_to: str
    status: str = "ACTIVE"
    valid_from: datetime
    valid_until: datetime


class OccupancyRecord(BaseModel):
    zone_id: str
    personnel_count: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OperationalEpisode(BaseModel):
    episode_id: str
    asset_id: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    severity: RiskTier
    summary: str
    root_causes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class MLAssessment(BaseModel):
    model_name: str
    model_version: str
    status: str  # "SUCCESS", "MODEL_NOT_AVAILABLE", "ERROR"
    prediction: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IndustrialRiskAssessment(BaseModel):
    assessment_id: str
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_score: float  # 0.0 to 1.0
    risk_tier: RiskTier
    process_anomaly_factor: float
    equipment_condition_factor: float
    alarm_state_factor: float
    permit_simops_factor: float
    personnel_exposure_factor: float
    explanation: str
    recommended_actions: List[str] = Field(default_factory=list)
