"""
backend/simulator/scenario_runner.py — Deterministic Scenario Scheduler for NOVA.

Executes and manages deterministic, reproducible operational scenarios:
- SCENARIO-1-HIGH-COT: Firing rate elevation, high COT alarm, and downstream thermal propagation
- SCENARIO-2-PROCESS-ANOMALY: Cooling water step decrease (TEP Fault 4) with covariance drift
- SCENARIO-3-MAINTENANCE: Scheduled pyrometer recalibration and burner decoking cycle
- SCENARIO-4-SAFETY-EVENT: Combustible vapor leak in Bay 2 exceeding 20% LEL critical threshold
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.simulator.engine import ProcessSimulationEngine
from backend.simulator.models import EquipmentStatus, SimulatorPlantState

logger = logging.getLogger("nova.simulator.scenarios")


class ScenarioRunner:
    """
    Manages scripted scenario playback and parameter injection into the simulation engine.
    """

    def __init__(self, engine: ProcessSimulationEngine) -> None:
        self.engine = engine
        self.active_scenario: Optional[str] = None
        self._scenario_task: Optional[asyncio.Task] = None

    def apply_scenario(self, scenario_id: str) -> SimulatorPlantState:
        """
        Apply a scenario instantaneously and advance the simulator by one step.
        """
        sc_id = scenario_id.upper()
        self.active_scenario = sc_id

        if "1" in sc_id or "COT" in sc_id or "HIGH-COT" in sc_id:
            self._apply_high_cot()
        elif "2" in sc_id or "ANOMALY" in sc_id or "FAULT" in sc_id:
            self._apply_process_anomaly()
        elif "3" in sc_id or "MAINTENANCE" in sc_id:
            self._apply_maintenance()
        elif "4" in sc_id or "SAFETY" in sc_id or "GAS" in sc_id:
            self._apply_safety_event()
        else:
            logger.warning("Unknown scenario ID '%s'. Applying nominal reset.", scenario_id)
            self.engine.reset()

        return self.engine.step()

    def _apply_high_cot(self) -> None:
        """Inject SCENARIO-1-HIGH-COT parameters."""
        logger.info("Injecting SCENARIO-1-HIGH-COT into process engine.")
        self.engine.inject_disturbance(
            scenario_id="SCENARIO-1-HIGH-COT",
            fuel_valve=69.5,
            fuel_pressure=0.35,
            feed_flow=24000.0,
            cw_flow=2400.0,
            gas_leak=0.2,
            equipment_status={"F-201A": EquipmentStatus.RUNNING},
        )

    def _apply_process_anomaly(self) -> None:
        """Inject SCENARIO-2-PROCESS-ANOMALY parameters (TEP Fault 4 CW disturbance)."""
        logger.info("Injecting SCENARIO-2-PROCESS-ANOMALY into process engine.")
        self.engine.inject_disturbance(
            scenario_id="SCENARIO-2-PROCESS-ANOMALY",
            fuel_valve=64.5,
            fuel_pressure=0.32,
            feed_flow=24000.0,
            cw_flow=1650.0,  # Below 1800.0 m³/h alarm threshold
            gas_leak=0.2,
            equipment_status={"SYS-CW": EquipmentStatus.FAULT},
        )

    def _apply_maintenance(self) -> None:
        """Inject SCENARIO-3-MAINTENANCE parameters."""
        logger.info("Injecting SCENARIO-3-MAINTENANCE into process engine.")
        self.engine.inject_disturbance(
            scenario_id="SCENARIO-3-MAINTENANCE",
            fuel_valve=60.0,
            fuel_pressure=0.30,
            feed_flow=22000.0,
            cw_flow=2400.0,
            gas_leak=0.1,
            equipment_status={
                "F-201A": EquipmentStatus.MAINTENANCE,
                "B-104": EquipmentStatus.MAINTENANCE,
            },
        )

    def _apply_safety_event(self) -> None:
        """Inject SCENARIO-4-SAFETY-EVENT parameters."""
        logger.info("Injecting SCENARIO-4-SAFETY-EVENT into process engine.")
        self.engine.inject_disturbance(
            scenario_id="SCENARIO-4-SAFETY-EVENT",
            fuel_valve=64.5,
            fuel_pressure=0.32,
            feed_flow=24000.0,
            cw_flow=2400.0,
            gas_leak=22.5,  # Exceeds 20.0% LEL critical threshold
            equipment_status={"SYS-ESD": EquipmentStatus.FAULT},
        )

    async def play_timeline(
        self,
        scenario_id: str,
        duration_seconds: int = 10,
        time_step_sec: float = 0.5,
    ) -> List[SimulatorPlantState]:
        """
        Play out a scenario dynamically over a time interval and capture state trajectories.
        """
        self.apply_scenario(scenario_id)
        states: List[SimulatorPlantState] = []
        steps = int(duration_seconds / time_step_sec)

        for _ in range(steps):
            state = self.engine.step()
            states.append(state)
            await asyncio.sleep(time_step_sec)

        return states
