"""backend.models — shared Pydantic data models for VIGIL.

Re-exports every model class so consumers can write::

    from backend.models import NormalizedEvent, RiskAssessment, Case
"""

from backend.models.action import ToolCall, ToolResult
from backend.models.audit import AuditEntry
from backend.models.case import (
    Case,
    EquipmentContext,
    MaintenanceRecord,
    OperationalContext,
    PermitRecord,
    ShiftState,
)
from backend.models.event import NormalizedEvent
from backend.models.evidence import EvidenceItem, HistoricalMatch, EvidencePackage
from backend.models.risk import RiskAssessment
from backend.models.industrial_domain import (
    OperatingMode,
    SensorQuality,
    RiskTier,
    EpisodeStatus,
    MLAssessmentStatus,
    ProcessTelemetry,
    OperationalEvent,
    Plant,
    Unit,
    Asset,
    Equipment,
    Sensor,
    ProcessTag,
    Alarm,
    MaintenanceRecord as IndustrialMaintenanceRecord,
    Permit as IndustrialPermit,
    OccupancyRecord,
    MLAssessment,
    IndustrialRiskAssessment,
    OperationalEpisode,
    PlantState,
)

__all__ = [
    # event.py
    "NormalizedEvent",
    # case.py
    "PermitRecord",
    "MaintenanceRecord",
    "ShiftState",
    "EquipmentContext",
    "OperationalContext",
    "Case",
    # evidence.py
    "EvidenceItem",
    "HistoricalMatch",
    "EvidencePackage",
    # risk.py
    "RiskAssessment",
    # action.py
    "ToolCall",
    "ToolResult",
    # audit.py
    "AuditEntry",
    # industrial_domain.py
    "OperatingMode",
    "SensorQuality",
    "RiskTier",
    "EpisodeStatus",
    "MLAssessmentStatus",
    "ProcessTelemetry",
    "OperationalEvent",
    "Plant",
    "Unit",
    "Asset",
    "Equipment",
    "Sensor",
    "ProcessTag",
    "Alarm",
    "IndustrialMaintenanceRecord",
    "IndustrialPermit",
    "OccupancyRecord",
    "MLAssessment",
    "IndustrialRiskAssessment",
    "OperationalEpisode",
    "PlantState",
]

