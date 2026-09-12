"""
backend/models/industrial_domain.py — Petrochemical Industrial Domain Models.

Provides Pydantic models for plants, units, assets, equipment, sensors, tags,
alarms, maintenance records, permits, occupancy, operational episodes,
ML assessments, and industrial risk assessments.
"""
from __future__ import annotations

import uuid
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
    # Target canonical additions
    STEADY_STATE = "STEADY_STATE"
    RAMP_UP = "RAMP_UP"
    RAMP_DOWN = "RAMP_DOWN"
    EMERGENCY = "EMERGENCY"
    UNKNOWN = "UNKNOWN"


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


class EpisodeStatus(str, Enum):
    NORMAL = "NORMAL"
    DEVIATION = "DEVIATION"
    ANOMALY = "ANOMALY"
    DIAGNOSIS = "DIAGNOSIS"
    ELEVATED_RISK = "ELEVATED_RISK"
    MITIGATION_OBSERVATION = "MITIGATION_OBSERVATION"
    RESOLVED = "RESOLVED"


class MLAssessmentStatus(str, Enum):
    OK = "OK"
    SUCCESS = "SUCCESS"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    INVALID_INPUT = "INVALID_INPUT"
    INFERENCE_ERROR = "INFERENCE_ERROR"


class ProcessTelemetry(BaseModel):
    """Standardized industrial process telemetry record with canonical contract."""
    asset_id: str
    tag: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    value: float
    unit: str
    quality: SensorQuality = SensorQuality.GOOD
    source: str = "dcs"
    operating_mode: OperatingMode = OperatingMode.NORMAL
    # Canonical extensions
    event_id: str = Field(default_factory=lambda: f"telem_{uuid.uuid4().hex[:10]}")
    plant_id: str = "PLANT-ETH-01"
    unit_id: str = "UNIT-CRACK-01"
    asset_type: Optional[str] = None
    sensor_id: Optional[str] = None
    parameter: Optional[str] = None
    provenance: str = "SYNTHETIC_NOVA_DATA"

    def model_post_init(self, __context: Any) -> None:
        if not self.tag and self.sensor_id:
            self.tag = self.sensor_id
        elif not self.sensor_id and self.tag:
            self.sensor_id = self.tag
        if not self.parameter and self.tag:
            self.parameter = self.tag


class OperationalEvent(BaseModel):
    """Standardized operational event payload."""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    asset_id: str
    event_type: str
    source: str
    schema_version: str = "1.0"
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "SYNTHETIC_NOVA_DATA"


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
    tag: str = ""
    asset_id: str
    severity: RiskTier
    message: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    # Canonical fields
    parameter: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    state: str = "ACTIVE"


class MaintenanceRecord(BaseModel):
    record_id: str
    asset_id: str
    work_order: str = ""
    description: str = ""
    logged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "OPEN"
    # Canonical fields
    type: Optional[str] = "preventive"
    start_time: Optional[datetime] = None
    planned_end_time: Optional[datetime] = None
    crew: List[str] = Field(default_factory=list)


class Permit(BaseModel):
    permit_id: str
    permit_type: str  # e.g., "Hot Work", "Vessel Entry"
    asset_id: str
    issued_to: str = "Lead Operator"
    status: str = "ACTIVE"
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    # Canonical fields
    zone_id: Optional[str] = "Bay3"
    affected_assets: List[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class OccupancyRecord(BaseModel):
    zone_id: str
    personnel_count: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Canonical fields
    timestamp: Optional[datetime] = None
    source: str = "rfid_access_control"


class MLAssessment(BaseModel):
    model_name: str
    model_version: str
    status: str  # "OK", "SUCCESS", "MODEL_NOT_AVAILABLE", "INVALID_INPUT", "INFERENCE_ERROR"
    prediction: Optional[Dict[str, Any]] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    labels: List[str] = Field(default_factory=list)
    features_used: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp: Optional[datetime] = None


class IndustrialRiskAssessment(BaseModel):
    assessment_id: str
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_score: float  # 0.0 to 1.0
    risk_tier: RiskTier
    process_anomaly_factor: float = 0.0
    equipment_condition_factor: float = 0.0
    alarm_state_factor: float = 0.0
    permit_simops_factor: float = 0.0
    personnel_exposure_factor: float = 0.0
    factors: Dict[str, float] = Field(default_factory=dict)
    policy_version: str = "1.0"
    model_versions: Dict[str, str] = Field(default_factory=dict)
    advisory_only: bool = True
    explanation: str = ""
    recommended_actions: List[str] = Field(default_factory=list)


class OperationalEpisode(BaseModel):
    """Correlated operational episode tracking state progression across plant assets."""
    episode_id: str
    plant_id: str = "PLANT-ETH-01"
    unit_id: str = "UNIT-CRACK-01"
    asset_id: str
    assets: List[str] = Field(default_factory=list)
    operating_mode: OperatingMode = OperatingMode.NORMAL
    status: EpisodeStatus = EpisodeStatus.NORMAL
    title: str = "Operational Process Episode"
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    severity: RiskTier = RiskTier.LOW
    trigger: Dict[str, Any] = Field(default_factory=dict)
    telemetry_summary: Dict[str, Any] = Field(default_factory=dict)
    ml_assessments: List[MLAssessment] = Field(default_factory=list)
    alarms: List[Alarm] = Field(default_factory=list)
    maintenance: List[MaintenanceRecord] = Field(default_factory=list)
    permits: List[Permit] = Field(default_factory=list)
    occupancy: Optional[OccupancyRecord] = None
    risk_assessment: Optional[IndustrialRiskAssessment] = None
    summary: str = ""
    root_causes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)


class PlantState(BaseModel):
    """Primary context object consumed by downstream intelligence layers."""
    plant_id: str = "PLANT-ETH-01"
    unit_id: str = "UNIT-CRACK-01"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operating_mode: OperatingMode = OperatingMode.NORMAL
    telemetry: Dict[str, ProcessTelemetry] = Field(default_factory=dict)
    active_alarms: List[Alarm] = Field(default_factory=list)
    equipment_status: Dict[str, str] = Field(default_factory=dict)
    active_maintenance: List[MaintenanceRecord] = Field(default_factory=list)
    active_permits: List[Permit] = Field(default_factory=list)
    occupancy: Dict[str, int] = Field(default_factory=dict)
    recent_events: List[OperationalEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

