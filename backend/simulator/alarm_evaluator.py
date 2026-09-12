"""
backend/simulator/alarm_evaluator.py — Industrial Alarm Evaluation Engine for NOVA.

Evaluates process telemetry against threshold matrices, managing alarm states:
- High / High-High / Low / Low-Low limit thresholds
- Dynamic hysteresis and deadband handling
- Unacknowledged alarm tracking
- Severity classification (INFO, WARNING, HIGH, CRITICAL)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.simulator.models import (
    AlarmEvent,
    AlarmSeverity,
    AlarmState,
    BayId,
    TelemetryPoint,
)

logger = logging.getLogger("nova.simulator.alarms")


# ---------------------------------------------------------------------------
# Alarm Configuration Matrix
# ---------------------------------------------------------------------------

ALARM_DEFINITIONS: List[Dict[str, Any]] = [
    # BAY 2 — Furnaces
    {
        "alarm_id": "ALM-TI-201-AH",
        "tag": "TI-201",
        "equipment_id": "F-201A",
        "bay_id": BayId.BAY_2,
        "parameter_name": "Coil Outlet Temperature High",
        "type": "HIGH",
        "threshold": 885.0,
        "deadband": 2.0,
        "severity": AlarmSeverity.HIGH,
        "message": "F-201A Coil Outlet Temperature exceeds normal envelope (>885.0 °C). Firing trim required.",
    },
    {
        "alarm_id": "ALM-TI-201-AHH",
        "tag": "TI-201",
        "equipment_id": "F-201A",
        "bay_id": BayId.BAY_2,
        "parameter_name": "Coil Outlet Temperature High-High Emergency",
        "type": "HIGH",
        "threshold": 892.0,
        "deadband": 2.0,
        "severity": AlarmSeverity.CRITICAL,
        "message": "F-201A COT in critical thermal excursion (>892.0 °C). Immediate emergency trip condition.",
    },
    {
        "alarm_id": "ALM-PI-201-AH",
        "tag": "PI-201",
        "equipment_id": "F-201A",
        "bay_id": BayId.BAY_2,
        "parameter_name": "Fuel Gas Header Pressure High",
        "type": "HIGH",
        "threshold": 0.38,
        "deadband": 0.01,
        "severity": AlarmSeverity.WARNING,
        "message": "Fuel Gas Header Pressure elevated (>0.38 MPa). Check header pressure controller PC-201.",
    },
    {
        "alarm_id": "ALM-PI-204-AH",
        "tag": "PI-204",
        "equipment_id": "F-201A",
        "bay_id": BayId.BAY_2,
        "parameter_name": "Firebox Draft Pressure High (Loss of Draft)",
        "type": "HIGH",
        "threshold": -5.0,  # Positive/near-zero draft is hazardous (normal is -25 to -35 Pa)
        "deadband": 3.0,
        "severity": AlarmSeverity.HIGH,
        "message": "Firebox Draft Loss (>-5.0 Pa). Risk of positive pressure blowback and flame rollout.",
    },
    {
        "alarm_id": "ALM-SV-204-AL",
        "tag": "SV-204",
        "equipment_id": "F-201A",
        "bay_id": BayId.BAY_2,
        "parameter_name": "Steam-to-Hydrocarbon Ratio Low",
        "type": "LOW",
        "threshold": 0.35,
        "deadband": 0.02,
        "severity": AlarmSeverity.HIGH,
        "message": "Dilution Steam ratio low (<0.35 kg/kg). Severe risk of rapid radiant coil coking.",
    },

    # BAY 3 — Transfer & Quench
    {
        "alarm_id": "ALM-TI-301-AH",
        "tag": "TI-301",
        "equipment_id": "TLE-201",
        "bay_id": BayId.BAY_3,
        "parameter_name": "TLE Effluent Outlet Temperature High",
        "type": "HIGH",
        "threshold": 450.0,
        "deadband": 5.0,
        "severity": AlarmSeverity.WARNING,
        "message": "TLE-201 effluent outlet temperature elevated (>450.0 °C). Check BFW flow and fouling.",
    },

    # BAY 4 — Compression & Separation
    {
        "alarm_id": "ALM-VI-401-AH",
        "tag": "VI-401",
        "equipment_id": "C-101",
        "bay_id": BayId.BAY_4,
        "parameter_name": "Compressor Stage 1 Vibration High",
        "type": "HIGH",
        "threshold": 4.5,
        "deadband": 0.3,
        "severity": AlarmSeverity.WARNING,
        "message": "Cracked Gas Compressor C-101 vibration high (>4.5 mm/s RMS). Check surge margin.",
    },
    {
        "alarm_id": "ALM-TI-401-AH",
        "tag": "TI-401",
        "equipment_id": "C-101",
        "bay_id": BayId.BAY_4,
        "parameter_name": "Compressor Drive End Bearing Temperature High",
        "type": "HIGH",
        "threshold": 95.0,
        "deadband": 2.0,
        "severity": AlarmSeverity.HIGH,
        "message": "C-101 Drive End bearing temperature elevated (>95.0 °C). Check lube oil cooling.",
    },

    # BAY 5 — Utilities & Safety
    {
        "alarm_id": "ALM-GD-501-AH",
        "tag": "GD-501",
        "equipment_id": "GD-501",
        "bay_id": BayId.BAY_5,
        "parameter_name": "Furnace Bay 2 Combustible Gas Alert",
        "type": "HIGH",
        "threshold": 10.0,
        "deadband": 1.0,
        "severity": AlarmSeverity.HIGH,
        "message": "Combustible hydrocarbon gas detected in Bay 2 (>10.0% LEL). LOTO & hot work suspended.",
    },
    {
        "alarm_id": "ALM-GD-501-AHH",
        "tag": "GD-501",
        "equipment_id": "GD-501",
        "bay_id": BayId.BAY_5,
        "parameter_name": "Combustible Gas Critical Lower Explosive Limit",
        "type": "HIGH",
        "threshold": 20.0,
        "deadband": 1.0,
        "severity": AlarmSeverity.CRITICAL,
        "message": "CRITICAL GAS CONCENTRATION (>20.0% LEL) in Bay 2. Automatic Emergency Isolation / ESD armed.",
    },
    {
        "alarm_id": "ALM-FI-501-AL",
        "tag": "FI-501",
        "equipment_id": "SYS-CW",
        "bay_id": BayId.BAY_5,
        "parameter_name": "Cooling Water Header Supply Flow Low",
        "type": "LOW",
        "threshold": 1800.0,
        "deadband": 50.0,
        "severity": AlarmSeverity.HIGH,
        "message": "Cooling Water header supply flow low (<1800.0 m³/h). CW pump disturbance detected.",
    },
]


class AlarmEvaluator:
    """
    Evaluates real-time synthetic telemetry against the alarm configuration matrix.
    Maintains unacknowledged alarm states and handles clearing with hysteresis.
    """

    def __init__(self, definitions: Optional[List[Dict[str, Any]]] = None) -> None:
        self.definitions = definitions or ALARM_DEFINITIONS
        self.active_alarms: Dict[str, AlarmEvent] = {}
        self.alarm_history: List[AlarmEvent] = []

    def evaluate_telemetry(self, telemetry: Dict[str, TelemetryPoint]) -> List[AlarmEvent]:
        """
        Evaluate current telemetry points and update active alarms.
        """
        now = datetime.now(timezone.utc)

        for rule in self.definitions:
            alarm_id = rule["alarm_id"]
            tag = rule["tag"]
            rule_type = rule["type"]
            threshold = float(rule["threshold"])
            deadband = float(rule.get("deadband", 0.0))

            point = telemetry.get(tag)
            if not point:
                continue

            val = float(point.value)
            is_active = alarm_id in self.active_alarms

            # Check threshold condition
            if rule_type == "HIGH":
                triggered = val >= threshold
                cleared = val < (threshold - deadband)
            elif rule_type == "LOW":
                triggered = val <= threshold
                cleared = val > (threshold + deadband)
            else:
                continue

            if triggered and not is_active:
                # Trigger new alarm
                alarm = AlarmEvent(
                    alarm_id=alarm_id,
                    timestamp=now,
                    equipment_id=rule["equipment_id"],
                    tag=tag,
                    parameter_name=rule["parameter_name"],
                    severity=rule["severity"],
                    state=AlarmState.ACTIVE,
                    message=rule["message"],
                    threshold=threshold,
                    actual_value=val,
                    acknowledged=False,
                    source="alarm_engine",
                    bay_id=rule["bay_id"],
                )
                self.active_alarms[alarm_id] = alarm
                self.alarm_history.append(alarm)
                logger.info("ALARM ACTIVATED: %s on %s = %.2f (Threshold: %.2f)", alarm_id, tag, val, threshold)

            elif triggered and is_active:
                # Update ongoing alarm actual value
                existing = self.active_alarms[alarm_id]
                existing.actual_value = val
                existing.timestamp = now

            elif cleared and is_active:
                # Clear alarm
                alarm = self.active_alarms.pop(alarm_id)
                alarm.state = AlarmState.CLEARED
                alarm.actual_value = val
                alarm.timestamp = now
                self.alarm_history.append(alarm)
                logger.info("ALARM CLEARED: %s on %s = %.2f", alarm_id, tag, val)

        return list(self.active_alarms.values())

    def acknowledge_alarm(self, alarm_id: str) -> Optional[AlarmEvent]:
        """Mark an active alarm as acknowledged by an operator."""
        if alarm_id in self.active_alarms:
            alarm = self.active_alarms[alarm_id]
            alarm.acknowledged = True
            alarm.state = AlarmState.ACKNOWLEDGED
            return alarm
        return None

    def get_active_alarms(self) -> List[AlarmEvent]:
        """Return list of all currently active alarms."""
        return list(self.active_alarms.values())

    def clear_all(self) -> None:
        """Reset all active alarms."""
        self.active_alarms.clear()
