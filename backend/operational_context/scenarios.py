"""
backend/operational_context/scenarios.py — Deterministic Demo Scenario Generator for NOVA.

Provides reproducible, deterministic industrial operational scenarios:
- SCENARIO 1: High COT Thermal Upset on Cracking Furnace F-201A
- SCENARIO 2: Process Anomaly & Fault Diagnosis (Cooling Water Disturbance)
- SCENARIO 3: Scheduled Decoking & Pyrometer Calibration Maintenance
- SCENARIO 4: Process Safety Combustible Gas Alert & High-Heat Access
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.operational_context.builder import build_operational_case
from backend.operational_context.models import (
    CasePriority,
    Observation,
    ObservationQuality,
    OperationalCase,
)


class OperationalScenario(BaseModel):
    """
    Metadata and telemetry package defining a reproducible demo operational scenario.
    """
    scenario_id: str = Field(..., description="Unique scenario identifier (e.g. SCENARIO-HIGH-COT)")
    name: str = Field(..., description="Human-readable scenario title")
    description: str = Field(..., description="Detailed description of the plant condition")
    equipment_id: str = Field(default="F-201A", description="Primary target asset")
    equipment_type: str = Field(default="furnace", description="Primary target equipment classification")
    unit_area: str = Field(default="UNIT-CRACK-01", description="Plant operating area")
    expected_priority: CasePriority = Field(default=CasePriority.HIGH, description="Target priority classification")
    scenario_type: str = Field(default="synthetic_demo", description="Scenario lineage classification")
    observations: List[Observation] = Field(default_factory=list, description="Telemetry observations")
    alarms: List[Dict[str, Any]] = Field(default_factory=list, description="Associated alarm states")
    scenario_context: str = Field(default="", description="Domain-specific contextual cue for RAG retrieval")


# ---------------------------------------------------------------------------
# Pre-defined Canonical Scenarios
# ---------------------------------------------------------------------------

def create_high_cot_scenario() -> OperationalScenario:
    """
    SCENARIO 1 — HIGH COT THERMAL UPSET
    Furnace F-201A experiences elevated coil outlet temperature (888.5 °C) exceeding the high alarm limit (885.0 °C).
    Requires fuel gas throttling, draft inspection, and high COT alarm SOP activation.
    """
    observations = [
        Observation(tag="TI-201", value=888.5, unit="°C", description="Furnace Coil Outlet Temperature (COT)", is_synthetic=True),
        Observation(tag="TI-201B", value=887.8, unit="°C", description="Redundant COT Thermocouple B", is_synthetic=True),
        Observation(tag="TI-201C", value=889.1, unit="°C", description="Redundant COT Thermocouple C", is_synthetic=True),
        Observation(tag="TI-204", value=995.0, unit="°C", description="Tube Metal Temperature (TMT)", is_synthetic=True),
        Observation(tag="PI-201", value=0.34, unit="MPa", description="Fuel Gas Header Pressure", is_synthetic=True),
        Observation(tag="PI-204", value=-28.0, unit="Pa", description="Firebox Draft Pressure", is_synthetic=True),
        Observation(tag="FC-201", value=24000.0, unit="kg/h", description="Total Hydrocarbon Feed Rate", is_synthetic=True),
        Observation(tag="FV-201", value=68.5, unit="%", description="Fuel Gas Control Valve Output", is_synthetic=True),
        Observation(tag="SV-204", value=0.40, unit="kg/kg", description="Steam-to-Hydrocarbon Ratio", is_synthetic=True),
    ]

    alarms = [
        {
            "alarm_id": "ALM-TI-201-AH",
            "tag": "TI-201",
            "parameter": "Furnace Coil Outlet Temperature High",
            "value": 888.5,
            "threshold": 885.0,
            "severity": "HIGH",
            "message": "High COT Alarm annunciated on Cracking Furnace F-201A (888.5 °C > 885.0 °C limit).",
        }
    ]

    return OperationalScenario(
        scenario_id="SCENARIO-1-HIGH-COT",
        name="High COT Thermal Excursion on Cracking Furnace F-201A",
        description="Coil outlet temperature exceeds high alarm threshold (885.0 °C) with elevated firing rate and potential coking progression.",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        expected_priority=CasePriority.HIGH,
        scenario_type="synthetic_demo",
        observations=observations,
        alarms=alarms,
        scenario_context="high COT alarm 885.0 C fuel gas throttling FV-201 draft inspection and emergency coil isolation",
    )


def create_process_anomaly_scenario() -> OperationalScenario:
    """
    SCENARIO 2 — PROCESS ANOMALY & FAULT DIAGNOSIS
    Process measurements exhibit multidimensional covariance drift corresponding to Reactor Cooling Water Step Decrease (Fault 4).
    """
    observations = [
        Observation(tag="XMEAS_1", value=0.2505, unit="kscfm", description="A Feed Stream Flow (Stream 1)", is_synthetic=True),
        Observation(tag="XMEAS_2", value=3664.0, unit="kg/h", description="D Feed Stream Flow (Stream 2)", is_synthetic=True),
        Observation(tag="XMEAS_9", value=120.4, unit="°C", description="Reactor Temperature", is_synthetic=True),
        Observation(tag="XMEAS_11", value=82.5, unit="°C", description="Product Separator Temperature", is_synthetic=True),
        Observation(tag="XMEAS_21", value=42.8, unit="°C", description="Reactor Cooling Water Outlet Temperature", is_synthetic=True),
        Observation(tag="XMV_10", value=45.2, unit="%", description="Reactor Cooling Water Flow Valve", is_synthetic=True),
        Observation(tag="TI-201", value=852.0, unit="°C", description="Coil Outlet Temperature (Normal baseline)", is_synthetic=True),
    ]

    alarms = [
        {
            "alarm_id": "ALM-TI-RCW-AH",
            "tag": "XMEAS_21",
            "parameter": "Reactor Cooling Water High Temperature",
            "value": 42.8,
            "threshold": 40.0,
            "severity": "MEDIUM",
            "message": "Cooling water temperature increase indicates reduced heat removal capacity.",
        }
    ]

    return OperationalScenario(
        scenario_id="SCENARIO-2-PROCESS-ANOMALY",
        name="Process Anomaly & Reactor Cooling Water Fault Diagnosis",
        description="Multivariate covariance shift detected by Isolation Forest with XGBoost classification to Reactor Cooling Water Step Decrease (Fault 4).",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        expected_priority=CasePriority.MEDIUM,
        scenario_type="synthetic_demo",
        observations=observations,
        alarms=alarms,
        scenario_context="process anomaly diagnosis fault 4 cooling water disturbance sensor drift and operating manual response",
    )


def create_maintenance_scenario() -> OperationalScenario:
    """
    SCENARIO 3 — SCHEDULED MAINTENANCE & HOT WORK PERMIT
    Furnace F-201A requires decoking and skin thermocouple pyrometer recalibration under open work order WO-2025-0882.
    """
    observations = [
        Observation(tag="TI-201", value=845.0, unit="°C", description="Coil Outlet Temperature (Turndown)", is_synthetic=True),
        Observation(tag="TI-204", value=980.0, unit="°C", description="Estimated Tube Metal Temperature", is_synthetic=True),
        Observation(tag="DP-201", value=0.18, unit="MPa", description="Coil Differential Pressure (Fouled)", is_synthetic=True),
        Observation(tag="FC-201", value=12000.0, unit="kg/h", description="Hydrocarbon Feed Rate (Turndown)", is_synthetic=True),
    ]

    alarms = []

    return OperationalScenario(
        scenario_id="SCENARIO-3-MAINTENANCE",
        name="Furnace F-201A Radiant Coil Decoking & Thermocouple Recalibration",
        description="Maintenance preparation for radiant coil decoking and pyrometer recalibration work order WO-2025-0882 with LOTO isolation.",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        expected_priority=CasePriority.MEDIUM,
        scenario_type="synthetic_demo",
        observations=observations,
        alarms=alarms,
        scenario_context="furnace decoking maintenance procedure work order WO-2025-0882 LOTO isolation standard and Class A hot work permit",
    )


def create_safety_event_scenario() -> OperationalScenario:
    """
    SCENARIO 4 — PROCESS SAFETY EVENT & COMBUSTIBLE GAS ALERT
    Area gas detector GD-201 triggers alert (22% LEL) near Cracking Furnace F-201A burner manifold.
    Requires immediate gas isolation, exclusion zone enforcement, PPE aluminized shields, and emergency SOP.
    """
    observations = [
        Observation(tag="GD-201", value=22.0, unit="% LEL", description="Area Combustible Gas Detection", is_synthetic=True),
        Observation(tag="TI-201", value=860.0, unit="°C", description="Coil Outlet Temperature", is_synthetic=True),
        Observation(tag="PI-201", value=0.31, unit="MPa", description="Fuel Gas Pressure", is_synthetic=True),
    ]

    alarms = [
        {
            "alarm_id": "ALM-GD-201-AL",
            "tag": "GD-201",
            "parameter": "Combustible Gas Detection Alarm",
            "value": 22.0,
            "threshold": 20.0,
            "severity": "HIGH",
            "message": "Combustible gas level exceeded 20% LEL in UNIT-CRACK-01 burner bay.",
        }
    ]

    return OperationalScenario(
        scenario_id="SCENARIO-4-SAFETY-EVENT",
        name="Combustible Gas Release Alert & High-Heat Access Restriction",
        description="Area gas sensor detects flammable vapor release exceeding 20% LEL threshold near F-201A, triggering gas isolation and safety SOPs.",
        equipment_id="F-201A",
        equipment_type="furnace",
        unit_area="UNIT-CRACK-01",
        expected_priority=CasePriority.HIGH,
        scenario_type="synthetic_demo",
        observations=observations,
        alarms=alarms,
        scenario_context="combustible gas release 20% LEL safety procedure exclusion zone PPE aluminized shield and emergency shutdown",
    )


# ---------------------------------------------------------------------------
# Scenario Registry & Builder
# ---------------------------------------------------------------------------

SCENARIO_REGISTRY: Dict[str, Any] = {
    "SCENARIO-1-HIGH-COT": create_high_cot_scenario,
    "high_cot": create_high_cot_scenario,
    "1": create_high_cot_scenario,
    "SCENARIO-2-PROCESS-ANOMALY": create_process_anomaly_scenario,
    "process_anomaly": create_process_anomaly_scenario,
    "2": create_process_anomaly_scenario,
    "SCENARIO-3-MAINTENANCE": create_maintenance_scenario,
    "maintenance": create_maintenance_scenario,
    "3": create_maintenance_scenario,
    "SCENARIO-4-SAFETY-EVENT": create_safety_event_scenario,
    "safety_event": create_safety_event_scenario,
    "4": create_safety_event_scenario,
}


class ScenarioBuilder:
    """Helper for executing and building full OperationalCases from canonical scenarios."""

    @staticmethod
    def list_scenarios() -> List[str]:
        return ["SCENARIO-1-HIGH-COT", "SCENARIO-2-PROCESS-ANOMALY", "SCENARIO-3-MAINTENANCE", "SCENARIO-4-SAFETY-EVENT"]

    @staticmethod
    def get_scenario(name_or_id: str) -> OperationalScenario:
        normalized = str(name_or_id).strip()
        factory = SCENARIO_REGISTRY.get(normalized)
        if factory is None:
            raise KeyError(f"Unknown scenario '{name_or_id}'. Available: {ScenarioBuilder.list_scenarios()}")
        return factory()

    @staticmethod
    def build_case_from_scenario(
        name_or_id: str,
        kb: Optional[Any] = None,
        ml_pipeline: Optional[Any] = None,
    ) -> OperationalCase:
        scenario = ScenarioBuilder.get_scenario(name_or_id)
        return build_operational_case(
            telemetry=scenario.observations,
            equipment_id=scenario.equipment_id,
            equipment_type=scenario.equipment_type,
            unit_area=scenario.unit_area,
            alarms=scenario.alarms,
            scenario_context=scenario.scenario_context,
            kb=kb,
            ml_pipeline=ml_pipeline,
        )
