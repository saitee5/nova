"""
backend/operational_context — NOVA Operational Intelligence Context Layer.

Provides structured, traceable operational case construction unifying:
- Process observations (measured telemetry)
- ML model assessments across 4 models
- Active alarms and process episodes
- Multi-domain RAG evidence (documents, safety, maintenance, permits, incidents, equipment)
- Plant topology and design envelopes
- Transparent risk indicators
- Deterministic case priority evaluation
- Explicit synthetic provenance and operational limitations
"""

from .builder import (
    KNOWN_EQUIPMENT_REGISTRY,
    OperationalContextBuilder,
    build_operational_case,
)
from .models import (
    CasePriority,
    CaseStatus,
    EquipmentDetailContext,
    MLAssessmentSummary,
    Observation,
    ObservationQuality,
    OperationalCase,
    RiskIndicator,
)
from .scenarios import (
    OperationalScenario,
    ScenarioBuilder,
    create_high_cot_scenario,
    create_maintenance_scenario,
    create_process_anomaly_scenario,
    create_safety_event_scenario,
)

__all__ = [
    # Models
    "OperationalCase",
    "Observation",
    "ObservationQuality",
    "RiskIndicator",
    "MLAssessmentSummary",
    "EquipmentDetailContext",
    "CaseStatus",
    "CasePriority",
    # Builder
    "OperationalContextBuilder",
    "build_operational_case",
    "KNOWN_EQUIPMENT_REGISTRY",
    # Scenarios
    "OperationalScenario",
    "ScenarioBuilder",
    "create_high_cot_scenario",
    "create_process_anomaly_scenario",
    "create_maintenance_scenario",
    "create_safety_event_scenario",
]
