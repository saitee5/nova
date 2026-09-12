"""
backend/simulator/engine.py — Causal Five-Bay Industrial Process Simulation Engine for NOVA.

Features:
- Physics-correlated state evolution across all 5 physical equipment bays
- First-order lag dynamics and causal inter-bay coupling
- Natural process noise and stochastic variations
- Duty/standby equipment transitions (P-101A/B, P-301A/B)
- Deterministic random seed support for reproducible scenarios
- Live subscription callbacks and state inspection
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from backend.simulator.alarm_evaluator import AlarmEvaluator
from backend.simulator.models import (
    AlarmEvent,
    BayId,
    BayState,
    EquipmentModel,
    EquipmentStatus,
    SimulatorPlantState,
    TelemetryPoint,
    TelemetryQuality,
)

logger = logging.getLogger("nova.simulator.engine")


class ProcessSimulationEngine:
    """
    Continuous Five-Bay Chemical Process Simulation Engine.
    Maintains causal physical state correlations across Feed, Furnaces, Quench,
    Compression, Separation, Utilities, and Safety systems.
    """

    def __init__(
        self,
        seed: Optional[int] = 42,
        sampling_interval_sec: float = 1.0,
        alarm_evaluator: Optional[AlarmEvaluator] = None,
    ) -> None:
        self.seed = seed
        self.sampling_interval_sec = sampling_interval_sec
        self.rng = random.Random(seed)
        self.alarm_evaluator = alarm_evaluator or AlarmEvaluator()

        # Engine Lifecycle
        self.is_running = False
        self.is_paused = False
        self.tick_count = 0
        self._subscribers: List[Callable[[SimulatorPlantState], None]] = []
        self._async_task: Optional[asyncio.Task] = None

        # Active Process Disturbance Modifiers
        self.active_scenario_id: Optional[str] = None
        self.fuel_valve_override: Optional[float] = None
        self.fuel_pressure_override: Optional[float] = None
        self.feed_flow_override: Optional[float] = None
        self.cw_flow_override: Optional[float] = None
        self.gas_leak_override: Optional[float] = None
        self.equipment_overrides: Dict[str, EquipmentStatus] = {}

        # Internal State Variables
        self._initialize_base_state()

    def _initialize_base_state(self) -> None:
        """Initialize nominal steady-state operating parameters."""
        # Bay 1: Feed & Preheat
        self.feed_flow = 24000.0  # kg/h
        self.feed_temp_in = 45.0  # °C
        self.feed_preheat_out = 165.0  # °C
        self.feed_pressure = 2.85  # MPa
        self.surge_level = 58.0  # %
        self.steam_flow = 9600.0  # kg/h
        self.steam_ratio = 0.40  # kg/kg

        # Bay 2: Cracking Furnaces
        self.furnace_cot = 848.5  # °C (normal envelope 840-860)
        self.furnace_cot_b = 848.2
        self.furnace_cot_c = 848.9
        self.furnace_tmt_surrogate = 945.0  # °C
        self.fuel_valve = 64.5  # %
        self.fuel_pressure = 0.32  # MPa
        self.firebox_draft = -28.5  # Pa
        self.stack_temp = 220.0  # °C

        # Bay 3: Transfer & Quench
        self.tle_effluent_temp = 395.0  # °C
        self.tle_inlet_press = 0.18  # MPa
        self.quench_flow = 320.0  # m³/h
        self.quench_bottom_temp = 112.0  # °C
        self.quench_overhead_temp = 82.5  # °C
        self.quench_drum_level = 52.0  # %

        # Bay 4: Compression & Separation
        self.comp_suction_p = 0.045  # MPa
        self.comp_discharge_p = 3.45  # MPa
        self.comp_flow = 72000.0  # kg/h
        self.comp_vibration = 1.85  # mm/s
        self.comp_bearing_temp = 72.5  # °C
        self.cooler_outlet_temp = 38.0  # °C
        self.demeth_overhead_temp = -98.0  # °C
        self.deeth_overhead_temp = 6.5  # °C

        # Bay 5: Utilities & Safety
        self.cw_supply_flow = 2400.0  # m³/h
        self.cw_supply_temp = 28.5  # °C
        self.cw_return_temp = 38.2  # °C
        self.gas_detector_bay2 = 0.2  # % LEL
        self.gas_detector_bay1 = 0.1  # % LEL
        self.inst_air_p = 0.68  # MPa
        self.flame_status = 1.0  # 1.0 = normal flame
        self.esd_status = "NORMAL"

        # Initialize canonical equipment
        self._initialize_equipment_catalog()

    def _initialize_equipment_catalog(self) -> None:
        """Create the 5-bay equipment directory."""
        self.equipment: Dict[str, EquipmentModel] = {
            # Bay 1
            "V-101": EquipmentModel(equipment_id="V-101", name="Feed Surge Drum", equipment_type="drum", bay_id=BayId.BAY_1, primary_tags=["LC-101", "PC-101"]),
            "P-101A": EquipmentModel(equipment_id="P-101A", name="Hydrocarbon Feed Pump A (Duty)", equipment_type="pump", bay_id=BayId.BAY_1, status=EquipmentStatus.RUNNING, is_standby_capable=True, primary_tags=["FC-101", "PI-101"]),
            "P-101B": EquipmentModel(equipment_id="P-101B", name="Hydrocarbon Feed Pump B (Standby)", equipment_type="pump", bay_id=BayId.BAY_1, status=EquipmentStatus.STANDBY, is_standby_capable=True, primary_tags=["FC-101B", "PI-101B"]),
            "FLT-101": EquipmentModel(equipment_id="FLT-101", name="Feed Filter Separator", equipment_type="filter", bay_id=BayId.BAY_1, primary_tags=["DP-101"]),
            "V-201A": EquipmentModel(equipment_id="V-201A", name="Feed Preheater Heat Exchanger", equipment_type="preheater", bay_id=BayId.BAY_1, primary_tags=["TI-101", "TI-102"]),

            # Bay 2
            "F-201A": EquipmentModel(equipment_id="F-201A", name="Cracking Furnace F-201A", equipment_type="furnace", bay_id=BayId.BAY_2, primary_tags=["TI-201", "TI-201B", "TI-201C", "TI-204", "PI-201", "PI-204", "FC-201", "FV-201", "SV-204"]),
            "F-201B": EquipmentModel(equipment_id="F-201B", name="Cracking Furnace F-201B", equipment_type="furnace", bay_id=BayId.BAY_2, primary_tags=["TI-202", "FC-202"]),
            "F-201C": EquipmentModel(equipment_id="F-201C", name="Cracking Furnace F-201C", equipment_type="furnace", bay_id=BayId.BAY_2, primary_tags=["TI-203", "FC-203"]),
            "B-101": EquipmentModel(equipment_id="B-101", name="Furnace Radiant Burner 101", equipment_type="burner", bay_id=BayId.BAY_2, primary_tags=["FLAME-101"]),
            "B-102": EquipmentModel(equipment_id="B-102", name="Furnace Radiant Burner 102", equipment_type="burner", bay_id=BayId.BAY_2, primary_tags=["FLAME-102"]),
            "B-103": EquipmentModel(equipment_id="B-103", name="Furnace Radiant Burner 103", equipment_type="burner", bay_id=BayId.BAY_2, primary_tags=["FLAME-103"]),
            "B-104": EquipmentModel(equipment_id="B-104", name="Furnace Radiant Burner 104", equipment_type="burner", bay_id=BayId.BAY_2, primary_tags=["FLAME-104"]),

            # Bay 3
            "TLE-201": EquipmentModel(equipment_id="TLE-201", name="Transfer-Line Exchanger", equipment_type="exchanger", bay_id=BayId.BAY_3, primary_tags=["TI-301", "PI-301", "FC-302"]),
            "T-101": EquipmentModel(equipment_id="T-101", name="Quench Tower", equipment_type="column", bay_id=BayId.BAY_3, primary_tags=["TI-302", "TI-303", "FC-301"]),
            "P-301A": EquipmentModel(equipment_id="P-301A", name="Quench Circulation Pump A (Duty)", equipment_type="pump", bay_id=BayId.BAY_3, status=EquipmentStatus.RUNNING, is_standby_capable=True),
            "P-301B": EquipmentModel(equipment_id="P-301B", name="Quench Circulation Pump B (Standby)", equipment_type="pump", bay_id=BayId.BAY_3, status=EquipmentStatus.STANDBY, is_standby_capable=True),
            "V-301": EquipmentModel(equipment_id="V-301", name="Quench Separator Drum", equipment_type="drum", bay_id=BayId.BAY_3, primary_tags=["LC-301"]),

            # Bay 4
            "C-101": EquipmentModel(equipment_id="C-101", name="Cracked Gas Compressor (Stages 1-3)", equipment_type="compressor", bay_id=BayId.BAY_4, primary_tags=["PI-401", "PI-402", "FC-401", "VI-401", "TI-401"]),
            "C-102": EquipmentModel(equipment_id="C-102", name="Cracked Gas Compressor (Stages 4-5)", equipment_type="compressor", bay_id=BayId.BAY_4, primary_tags=["PI-403", "VI-402"]),
            "E-401": EquipmentModel(equipment_id="E-401", name="Compressor Discharge Cooler", equipment_type="cooler", bay_id=BayId.BAY_4, primary_tags=["TI-403"]),
            "C-401": EquipmentModel(equipment_id="C-401", name="Demethanizer Column", equipment_type="column", bay_id=BayId.BAY_4, primary_tags=["PI-404", "TI-404"]),
            "C-402": EquipmentModel(equipment_id="C-402", name="Deethanizer Column", equipment_type="column", bay_id=BayId.BAY_4, primary_tags=["PI-405", "TI-405"]),

            # Bay 5
            "SYS-FG": EquipmentModel(equipment_id="SYS-FG", name="Fuel Gas Header System", equipment_type="utility", bay_id=BayId.BAY_5, primary_tags=["PI-501"]),
            "SYS-CW": EquipmentModel(equipment_id="SYS-CW", name="Cooling Water Circulation System", equipment_type="utility", bay_id=BayId.BAY_5, primary_tags=["FI-501", "TI-501", "TI-503"]),
            "SYS-ESD": EquipmentModel(equipment_id="SYS-ESD", name="Emergency Shutdown Loop", equipment_type="safety", bay_id=BayId.BAY_5, primary_tags=["ESD-STATUS"]),
            "GD-501": EquipmentModel(equipment_id="GD-501", name="Combustible Gas Detector Bay 2", equipment_type="sensor", bay_id=BayId.BAY_5, primary_tags=["GD-501"]),
            "SYS-FLARE": EquipmentModel(equipment_id="SYS-FLARE", name="Elevated Flare System", equipment_type="safety", bay_id=BayId.BAY_5, primary_tags=["PI-506"]),
        }

    # -----------------------------------------------------------------------
    # Causal Process Evolution Step
    # -----------------------------------------------------------------------

    def step(self) -> SimulatorPlantState:
        """
        Advance the chemical process state by one time step ($\Delta t$).
        Calculates causal physics couplings, applies noise, and evaluates alarms.
        """
        self.tick_count += 1
        noise = lambda sigma: self.rng.gauss(0.0, sigma)

        # 1. Evaluate Bay 1 (Feed & Preheat)
        target_feed = self.feed_flow_override if self.feed_flow_override is not None else 24000.0
        self.feed_flow += 0.2 * (target_feed - self.feed_flow) + noise(15.0)
        self.feed_preheat_out = 165.0 + 0.001 * (self.feed_flow - 24000.0) + noise(0.2)
        self.feed_pressure = 2.85 + (self.feed_flow / 24000.0 - 1.0) * 0.15 + noise(0.01)
        self.steam_flow = self.feed_flow * self.steam_ratio + noise(10.0)

        # 2. Evaluate Bay 2 (Cracking Furnaces)
        target_fuel_valve = self.fuel_valve_override if self.fuel_valve_override is not None else 64.5
        target_fuel_pressure = self.fuel_pressure_override if self.fuel_pressure_override is not None else 0.32
        
        self.fuel_valve += 0.25 * (target_fuel_valve - self.fuel_valve) + noise(0.1)
        self.fuel_pressure += 0.2 * (target_fuel_pressure - self.fuel_pressure) + noise(0.002)

        # First-Principles Causal Coupling: Firing Duty → COT
        # Heat flux is a function of fuel gas valve opening, header pressure, and feed cooling capacity
        firing_duty_factor = (self.fuel_valve / 64.5) * (self.fuel_pressure / 0.32)
        feed_cooling_factor = self.feed_flow / 24000.0
        target_cot = 848.5 + (firing_duty_factor - 1.0) * 310.0 - (feed_cooling_factor - 1.0) * 35.0

        # Thermal inertia (First-order lag response)
        self.furnace_cot += 0.22 * (target_cot - self.furnace_cot) + noise(0.12)
        self.furnace_cot_b = self.furnace_cot - 0.35 + noise(0.08)
        self.furnace_cot_c = self.furnace_cot + 0.42 + noise(0.08)

        # TMT Physics-informed synthetic surrogate (NOT measured telemetry)
        self.furnace_tmt_surrogate = self.furnace_cot + 96.5 + (self.fuel_valve - 64.5) * 0.45 + noise(0.25)
        self.firebox_draft = -28.5 + (self.fuel_valve - 64.5) * 0.18 + noise(0.12)
        self.stack_temp = 220.0 + (self.furnace_cot - 848.5) * 0.35 + noise(0.3)

        # 3. Evaluate Bay 3 (Transfer & Quench)
        # TLE effluent temperature is causally driven by furnace effluent COT
        target_tle_temp = 395.0 + 0.65 * (self.furnace_cot - 848.5)
        self.tle_effluent_temp += 0.35 * (target_tle_temp - self.tle_effluent_temp) + noise(0.15)
        self.quench_flow = 320.0 + 0.42 * (self.tle_effluent_temp - 395.0) + noise(1.2)
        self.quench_bottom_temp = 112.0 + 0.12 * (self.tle_effluent_temp - 395.0) + noise(0.15)

        # 4. Evaluate Bay 4 (Compression & Separation)
        # Cooling water disturbance (Fault 4) impact
        target_cw_flow = self.cw_flow_override if self.cw_flow_override is not None else 2400.0
        self.cw_supply_flow += 0.3 * (target_cw_flow - self.cw_supply_flow) + noise(5.0)

        # If cooling water is reduced, discharge cooler outlet temp rises
        cw_deficit = max(0.0, 2400.0 - self.cw_supply_flow)
        self.cooler_outlet_temp = 38.0 + (cw_deficit / 500.0) * 8.5 + noise(0.1)

        # Compressor suction conditions and load
        self.comp_suction_p = 0.045 + (self.furnace_cot - 848.5) * 0.0002 + noise(0.0005)
        self.comp_flow = 3.0 * self.feed_flow + noise(25.0)
        self.comp_vibration = 1.85 + (self.furnace_cot - 848.5) * 0.008 + (cw_deficit / 500.0) * 0.4 + noise(0.04)
        self.comp_bearing_temp = 72.5 + (cw_deficit / 500.0) * 12.0 + (self.comp_vibration - 1.85) * 3.5 + noise(0.2)

        # 5. Evaluate Bay 5 (Utilities & Safety)
        target_gas_leak = self.gas_leak_override if self.gas_leak_override is not None else 0.2
        self.gas_detector_bay2 += 0.3 * (target_gas_leak - self.gas_detector_bay2) + noise(0.05)
        self.gas_detector_bay2 = max(0.0, self.gas_detector_bay2)
        self.gas_detector_bay1 = max(0.0, 0.1 + noise(0.02))

        # 6. Apply Equipment Overrides
        for eq_id, status in self.equipment_overrides.items():
            if eq_id in self.equipment:
                self.equipment[eq_id].status = status

        # 7. Build Telemetry Points
        telemetry = self._assemble_telemetry_points()

        # 8. Evaluate Alarms
        alarms = self.alarm_evaluator.evaluate_telemetry(telemetry)

        # 9. Determine Overall Safety & Utility States
        safety_state = "CRITICAL" if any(a.severity.value == "CRITICAL" for a in alarms) else ("ALERT" if alarms else "NORMAL")
        utility_state = "DEGRADED" if self.cw_supply_flow < 2000.0 else "NORMAL"

        # 10. Assemble Bay States
        bays = self._assemble_bay_states(telemetry, alarms)

        state = SimulatorPlantState(
            timestamp=datetime.now(timezone.utc),
            bays=bays,
            equipment_states={k: v.status for k, v in self.equipment.items()},
            telemetry=telemetry,
            alarms=alarms,
            active_scenario=self.active_scenario_id,
            safety_state=safety_state,
            utility_state=utility_state,
            operating_mode="SCENARIO" if self.active_scenario_id else "NORMAL",
            is_running=self.is_running,
            metadata={
                "tick_count": self.tick_count,
                "seed": self.seed,
                "sampling_interval_sec": self.sampling_interval_sec,
            }
        )

        # Notify active subscribers
        for callback in self._subscribers:
            try:
                callback(state)
            except Exception as ex:
                logger.error("Subscriber callback failed: %s", ex)

        return state

    # -----------------------------------------------------------------------
    # Telemetry Assembly
    # -----------------------------------------------------------------------

    def _assemble_telemetry_points(self) -> Dict[str, TelemetryPoint]:
        """Convert current internal physical state variables into canonical TelemetryPoints."""
        now = datetime.now(timezone.utc)
        pts: Dict[str, TelemetryPoint] = {}

        def add_pt(tag: str, val: float, unit: str, eq_id: str, eq_type: str, bay: BayId) -> None:
            pts[tag] = TelemetryPoint(
                tag=tag,
                value=round(val, 3),
                unit=unit,
                timestamp=now,
                quality=TelemetryQuality.GOOD,
                equipment_id=eq_id,
                equipment_type=eq_type,
                unit_area="UNIT-CRACK-01",
                bay_id=bay,
                source="synthetic_stream",
                is_synthetic=True,
                provenance={
                    "generator": "NOVA_FiveBay_Process_Simulator",
                    "tick": self.tick_count,
                    "model_lineage": "physics_correlated_synthetic",
                },
            )

        # BAY 1
        add_pt("FC-101", self.feed_flow, "kg/h", "P-101A", "pump", BayId.BAY_1)
        add_pt("PI-101", self.feed_pressure, "MPa", "P-101A", "pump", BayId.BAY_1)
        add_pt("LC-101", self.surge_level, "%", "V-101", "drum", BayId.BAY_1)
        add_pt("TI-101", self.feed_temp_in, "°C", "V-201A", "preheater", BayId.BAY_1)
        add_pt("TI-102", self.feed_preheat_out, "°C", "V-201A", "preheater", BayId.BAY_1)
        add_pt("FC-102", self.steam_flow, "kg/h", "V-201A", "valve", BayId.BAY_1)
        add_pt("SV-101", self.steam_ratio, "kg/kg", "V-201A", "valve", BayId.BAY_1)

        # BAY 2 (Primary Intelligence Bay)
        add_pt("TI-201", self.furnace_cot, "°C", "F-201A", "furnace", BayId.BAY_2)
        add_pt("TI-201B", self.furnace_cot_b, "°C", "F-201A", "furnace", BayId.BAY_2)
        add_pt("TI-201C", self.furnace_cot_c, "°C", "F-201A", "furnace", BayId.BAY_2)
        add_pt("TI-204", self.furnace_tmt_surrogate, "°C", "F-201A", "furnace", BayId.BAY_2)
        add_pt("PI-201", self.fuel_pressure, "MPa", "F-201A", "furnace", BayId.BAY_2)
        add_pt("PI-204", self.firebox_draft, "Pa", "F-201A", "furnace", BayId.BAY_2)
        add_pt("FC-201", self.feed_flow, "kg/h", "F-201A", "furnace", BayId.BAY_2)
        add_pt("FV-201", self.fuel_valve, "%", "F-201A", "furnace", BayId.BAY_2)
        add_pt("SV-204", self.steam_ratio, "kg/kg", "F-201A", "furnace", BayId.BAY_2)
        add_pt("TI-205", self.stack_temp, "°C", "STK-201", "stack", BayId.BAY_2)

        # BAY 3
        add_pt("TI-301", self.tle_effluent_temp, "°C", "TLE-201", "exchanger", BayId.BAY_3)
        add_pt("PI-301", self.tle_inlet_press, "MPa", "TLE-201", "exchanger", BayId.BAY_3)
        add_pt("FC-301", self.quench_flow, "m³/h", "T-101", "column", BayId.BAY_3)
        add_pt("TI-302", self.quench_bottom_temp, "°C", "T-101", "column", BayId.BAY_3)
        add_pt("LC-301", self.quench_drum_level, "%", "V-301", "drum", BayId.BAY_3)

        # BAY 4
        add_pt("PI-401", self.comp_suction_p, "MPa", "C-101", "compressor", BayId.BAY_4)
        add_pt("PI-402", self.comp_discharge_p, "MPa", "C-101", "compressor", BayId.BAY_4)
        add_pt("FC-401", self.comp_flow, "kg/h", "C-101", "compressor", BayId.BAY_4)
        add_pt("VI-401", self.comp_vibration, "mm/s", "C-101", "compressor", BayId.BAY_4)
        add_pt("TI-401", self.comp_bearing_temp, "°C", "C-101", "compressor", BayId.BAY_4)
        add_pt("TI-403", self.cooler_outlet_temp, "°C", "E-401", "cooler", BayId.BAY_4)
        add_pt("TI-404", self.demeth_overhead_temp, "°C", "C-401", "column", BayId.BAY_4)
        add_pt("TI-405", self.deeth_overhead_temp, "°C", "C-402", "column", BayId.BAY_4)

        # BAY 5
        add_pt("FI-501", self.cw_supply_flow, "m³/h", "SYS-CW", "utility", BayId.BAY_5)
        add_pt("TI-501", self.cw_supply_temp, "°C", "SYS-CW", "utility", BayId.BAY_5)
        add_pt("TI-503", self.cw_return_temp, "°C", "SYS-CW", "utility", BayId.BAY_5)
        add_pt("GD-501", self.gas_detector_bay2, "% LEL", "GD-501", "sensor", BayId.BAY_5)
        add_pt("GD-502", self.gas_detector_bay1, "% LEL", "GD-501", "sensor", BayId.BAY_5)
        add_pt("PI-503", self.inst_air_p, "MPa", "SYS-IA", "utility", BayId.BAY_5)

        # Sync standard Tennessee Eastman benchmark features (XMEAS_1..41, XMV_1..11) for TEP ML models
        self._sync_tep_benchmark_tags(pts)

        return pts

    def _sync_tep_benchmark_tags(self, pts: Dict[str, TelemetryPoint]) -> None:
        """Populate TEP benchmark measurement tags derived from process state."""
        now = datetime.now(timezone.utc)
        # XMEAS_9: Reactor Temperature (mirrors furnace COT)
        rx_temp = 120.4 + (self.furnace_cot - 848.5) * 0.15
        pts["XMEAS_9"] = TelemetryPoint(
            tag="XMEAS_9", value=round(rx_temp, 3), unit="°C", timestamp=now,
            equipment_id="F-201A", equipment_type="furnace", bay_id=BayId.BAY_2
        )
        # XMEAS_11: Product Separator Temp (mirrors cooler temp)
        pts["XMEAS_11"] = TelemetryPoint(
            tag="XMEAS_11", value=round(self.cooler_outlet_temp * 2.1, 3), unit="°C", timestamp=now,
            equipment_id="E-401", equipment_type="cooler", bay_id=BayId.BAY_4
        )
        # XMEAS_1: A Feed Flow
        pts["XMEAS_1"] = TelemetryPoint(
            tag="XMEAS_1", value=round(0.2505 + (self.feed_flow - 24000.0) * 0.00001, 4), unit="kscfm", timestamp=now,
            equipment_id="P-101A", equipment_type="pump", bay_id=BayId.BAY_1
        )
        # XMEAS_2: D Feed Flow
        pts["XMEAS_2"] = TelemetryPoint(
            tag="XMEAS_2", value=round(3664.0 + (self.feed_flow - 24000.0) * 0.1, 1), unit="kg/h", timestamp=now,
            equipment_id="P-101A", equipment_type="pump", bay_id=BayId.BAY_1
        )
        # XMV_1: D Feed Valve
        pts["XMV_1"] = TelemetryPoint(
            tag="XMV_1", value=round(63.0 + (self.feed_flow - 24000.0) * 0.001, 2), unit="%", timestamp=now,
            equipment_id="FV-101", equipment_type="valve", bay_id=BayId.BAY_1
        )
        # XMV_10: Cooling Water Valve
        cw_valve = 41.1 - (max(0.0, 2400.0 - self.cw_supply_flow) / 2400.0) * 20.0
        pts["XMV_10"] = TelemetryPoint(
            tag="XMV_10", value=round(cw_valve, 2), unit="%", timestamp=now,
            equipment_id="SYS-CW", equipment_type="utility", bay_id=BayId.BAY_5
        )

    def _assemble_bay_states(
        self,
        telemetry: Dict[str, TelemetryPoint],
        alarms: List[AlarmEvent],
    ) -> Dict[str, BayState]:
        """Aggregate equipment and telemetry into canonical BayStates."""
        bay_names = {
            BayId.BAY_1: ("BAY-01", "Feed & Preheat", "Hydrocarbon feed reception, pumping, filtration, and preheating"),
            BayId.BAY_2: ("BAY-02", "Cracking Furnaces", "High-temperature radiant cracking pyrolysis units F-201A/B/C"),
            BayId.BAY_3: ("BAY-03", "Transfer & Quench", "Rapid effluent quench, TLE heat recovery, and primary fractionation"),
            BayId.BAY_4: ("BAY-04", "Compression & Separation", "Cracked gas multi-stage compression and cryogenic distillation"),
            BayId.BAY_5: ("BAY-05", "Utilities & Safety", "Plant-wide cooling water, fuel gas, steam, and fire/gas safety networks"),
        }

        bays: Dict[str, BayState] = {}
        for bay_id, (code, name, desc) in bay_names.items():
            bay_eq = {eq_id: eq for eq_id, eq in self.equipment.items() if eq.bay_id == bay_id}
            bay_telem = {tag: pt for tag, pt in telemetry.items() if pt.bay_id == bay_id}
            bay_alarms = [a for a in alarms if a.bay_id == bay_id]
            bay_status = "CRITICAL" if any(a.severity.value == "CRITICAL" for a in bay_alarms) else ("ALARM" if bay_alarms else "NORMAL")

            bays[bay_id.value] = BayState(
                bay_id=bay_id,
                name=name,
                description=desc,
                equipment=bay_eq,
                telemetry=bay_telem,
                active_alarms=bay_alarms,
                status=bay_status,
            )
        return bays

    # -----------------------------------------------------------------------
    # Streaming Loop & Controls
    # -----------------------------------------------------------------------

    def subscribe(self, callback: Callable[[SimulatorPlantState], None]) -> None:
        """Register a callback for every generated plant state tick."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[SimulatorPlantState], None]) -> None:
        """Unregister a plant state callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def set_seed(self, seed: int) -> None:
        """Set simulation PRNG seed for deterministic replay."""
        self.seed = seed
        self.rng = random.Random(seed)

    def reset(self) -> SimulatorPlantState:
        """Reset simulator to nominal steady state."""
        self.tick_count = 0
        self.active_scenario_id = None
        self.fuel_valve_override = None
        self.fuel_pressure_override = None
        self.feed_flow_override = None
        self.cw_flow_override = None
        self.gas_leak_override = None
        self.equipment_overrides.clear()
        self.alarm_evaluator.clear_all()
        self._initialize_base_state()
        return self.step()

    def inject_disturbance(
        self,
        scenario_id: Optional[str] = None,
        fuel_valve: Optional[float] = None,
        fuel_pressure: Optional[float] = None,
        feed_flow: Optional[float] = None,
        cw_flow: Optional[float] = None,
        gas_leak: Optional[float] = None,
        equipment_status: Optional[Dict[str, EquipmentStatus]] = None,
    ) -> None:
        """Inject an intentional operational disturbance or scenario modifier."""
        if scenario_id is not None:
            self.active_scenario_id = scenario_id
        if fuel_valve is not None:
            self.fuel_valve_override = fuel_valve
        if fuel_pressure is not None:
            self.fuel_pressure_override = fuel_pressure
        if feed_flow is not None:
            self.feed_flow_override = feed_flow
        if cw_flow is not None:
            self.cw_flow_override = cw_flow
        if gas_leak is not None:
            self.gas_leak_override = gas_leak
        if equipment_status:
            self.equipment_overrides.update(equipment_status)

    async def start(self) -> None:
        """Start asynchronous continuous streaming loop."""
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self._async_task = asyncio.create_task(self._run_loop())
        logger.info("Five-Bay Process Simulation Engine started (Interval: %.2fs)", self.sampling_interval_sec)

    async def stop(self) -> None:
        """Stop streaming loop."""
        self.is_running = False
        if self._async_task and not self._async_task.done():
            self._async_task.cancel()
            try:
                await self._async_task
            except asyncio.CancelledError:
                pass
        logger.info("Five-Bay Process Simulation Engine stopped.")

    def pause(self) -> None:
        """Pause state evolution."""
        self.is_paused = True

    def resume(self) -> None:
        """Resume state evolution."""
        self.is_paused = False

    async def _run_loop(self) -> None:
        """Background streaming worker loop."""
        while self.is_running:
            try:
                if not self.is_paused:
                    self.step()
                await asyncio.sleep(self.sampling_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error("Simulation loop error: %s", ex, exc_info=True)
                await asyncio.sleep(1.0)
