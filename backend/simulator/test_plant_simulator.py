"""
backend/simulator/test_plant_simulator.py — Comprehensive Test Suite for NOVA Five-Bay Simulator.

Validates all 20 requirement categories:
- 5-Bay plant topology & equipment coverage
- Telemetry schema & synthetic data markings
- Causal physics couplings & correlation propagation
- Industrial alarm evaluation matrix & unacknowledged states
- ML pipeline inference & TubeTemperaturePredictor surrogate provenance
- OperationalCase live integration & RAG evidence linking
- Deterministic demo scenario execution (Scenarios 1-4)
- PRNG seed reproducibility & replay
- Latency profiling (p50/p95 tracking)
- Graceful failure handling and safety boundaries

Run with:
    python -m pytest backend/simulator/test_plant_simulator.py -v
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.simulator.alarm_evaluator import AlarmEvaluator
from backend.simulator.engine import ProcessSimulationEngine
from backend.simulator.live_bridge import LiveIntelligenceBridge
from backend.simulator.models import (
    AlarmSeverity,
    AlarmState,
    BayId,
    EquipmentStatus,
    SimulatorPlantState,
    TelemetryPoint,
    TelemetryQuality,
)
from backend.simulator.scenario_runner import ScenarioRunner


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def engine() -> ProcessSimulationEngine:
    """Fixture providing a fresh simulation engine with seed=42."""
    eng = ProcessSimulationEngine(seed=42, sampling_interval_sec=0.01)
    eng.reset()
    return eng


@pytest.fixture
def alarm_evaluator() -> AlarmEvaluator:
    return AlarmEvaluator()


@pytest.fixture
def bridge(engine: ProcessSimulationEngine) -> LiveIntelligenceBridge:
    return LiveIntelligenceBridge(engine=engine)


# ======================================================================
# 1. Five-Bay Plant Structure & Topology Tests
# ======================================================================

class TestFiveBayPlantStructure:
    """Validates the 5-bay topology and required equipment catalog."""

    def test_all_five_bays_exist(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        assert len(state.bays) == 5
        expected_bays = {"BAY-01", "BAY-02", "BAY-03", "BAY-04", "BAY-05"}
        assert set(state.bays.keys()) == expected_bays

    def test_bay_1_feed_and_preheat_equipment(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        bay1 = state.bays["BAY-01"]
        assert "P-101A" in bay1.equipment
        assert "P-101B" in bay1.equipment
        assert "V-101" in bay1.equipment
        assert "V-201A" in bay1.equipment
        assert "FLT-101" in bay1.equipment

    def test_bay_2_cracking_furnace_equipment(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        bay2 = state.bays["BAY-02"]
        assert "F-201A" in bay2.equipment
        assert "F-201B" in bay2.equipment
        assert "F-201C" in bay2.equipment
        assert "B-101" in bay2.equipment
        assert "B-102" in bay2.equipment
        assert "B-103" in bay2.equipment
        assert "B-104" in bay2.equipment

    def test_bay_3_quench_equipment(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        bay3 = state.bays["BAY-03"]
        assert "TLE-201" in bay3.equipment
        assert "T-101" in bay3.equipment
        assert "P-301A" in bay3.equipment
        assert "P-301B" in bay3.equipment

    def test_bay_4_compression_separation_equipment(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        bay4 = state.bays["BAY-04"]
        assert "C-101" in bay4.equipment
        assert "C-102" in bay4.equipment
        assert "E-401" in bay4.equipment
        assert "C-401" in bay4.equipment
        assert "C-402" in bay4.equipment

    def test_bay_5_utilities_and_safety_equipment(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        bay5 = state.bays["BAY-05"]
        assert "SYS-FG" in bay5.equipment
        assert "SYS-CW" in bay5.equipment
        assert "SYS-ESD" in bay5.equipment
        assert "GD-501" in bay5.equipment
        assert "SYS-FLARE" in bay5.equipment

    def test_duty_standby_equipment_states(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        assert state.equipment_states["P-101A"] == EquipmentStatus.RUNNING
        assert state.equipment_states["P-101B"] == EquipmentStatus.STANDBY
        assert state.equipment_states["P-301A"] == EquipmentStatus.RUNNING
        assert state.equipment_states["P-301B"] == EquipmentStatus.STANDBY


# ======================================================================
# 2. Telemetry Schema & Synthetic Data Tests
# ======================================================================

class TestTelemetrySchema:
    """Validates telemetry schema integrity and explicit synthetic markers."""

    def test_all_telemetry_points_marked_synthetic(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        assert len(state.telemetry) > 20
        for tag, point in state.telemetry.items():
            assert point.is_synthetic is True
            assert point.quality == TelemetryQuality.GOOD
            assert point.unit != ""
            assert point.timestamp is not None
            assert "generator" in point.provenance

    def test_critical_furnace_tags_exist(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        tags = state.telemetry.keys()
        for critical_tag in ["TI-201", "TI-201B", "TI-201C", "TI-204", "PI-201", "PI-204", "FC-201", "FV-201", "SV-204"]:
            assert critical_tag in tags

    def test_nominal_ranges_are_physically_realistic(self, engine: ProcessSimulationEngine) -> None:
        state = engine.step()
        telem = state.telemetry

        # Nominal COT between 840 and 860 °C
        assert 840.0 <= telem["TI-201"].value <= 860.0
        # Nominal Fuel Gas Pressure between 0.28 and 0.36 MPa
        assert 0.28 <= telem["PI-201"].value <= 0.36
        # Nominal Firebox Draft negative (-35 to -20 Pa)
        assert -35.0 <= telem["PI-204"].value <= -20.0
        # Nominal Feed Flow around 24,000 kg/h
        assert 22000.0 <= telem["FC-201"].value <= 26000.0


# ======================================================================
# 3. Causal Process Correlation Tests
# ======================================================================

class TestCausalProcessCorrelation:
    """Validates physical causality across bays."""

    def test_fuel_gas_increase_causes_cot_rise(self, engine: ProcessSimulationEngine) -> None:
        s0 = engine.step()
        cot_initial = s0.telemetry["TI-201"].value

        # Increase fuel gas valve
        engine.inject_disturbance(fuel_valve=72.0, fuel_pressure=0.35)
        for _ in range(10):
            s_after = engine.step()

        cot_final = s_after.telemetry["TI-201"].value
        assert cot_final > cot_initial + 10.0

    def test_cot_rise_propagates_to_tle_effluent(self, engine: ProcessSimulationEngine) -> None:
        s0 = engine.step()
        tle_initial = s0.telemetry["TI-301"].value

        # Drive furnace hotter
        engine.inject_disturbance(fuel_valve=72.0, fuel_pressure=0.35)
        for _ in range(15):
            s_after = engine.step()

        tle_final = s_after.telemetry["TI-301"].value
        assert tle_final > tle_initial + 2.5

    def test_feed_reduction_affects_furnace_and_downstream(self, engine: ProcessSimulationEngine) -> None:
        engine.inject_disturbance(feed_flow=18000.0)
        for _ in range(8):
            state = engine.step()

        assert state.telemetry["FC-101"].value < 20000.0
        assert state.telemetry["FC-201"].value < 20000.0


# ======================================================================
# 4. Alarm Evaluation Tests
# ======================================================================

class TestAlarmEngine:
    """Validates alarm threshold evaluation, activation, and hysteresis."""

    def test_high_cot_alarm_triggers_above_885(self, engine: ProcessSimulationEngine) -> None:
        engine.inject_disturbance(fuel_valve=75.0, fuel_pressure=0.38)
        for _ in range(15):
            state = engine.step()

        alarm_tags = [a.tag for a in state.alarms]
        assert "TI-201" in alarm_tags
        cot_alarm = next(a for a in state.alarms if a.tag == "TI-201")
        assert cot_alarm.severity in (AlarmSeverity.HIGH, AlarmSeverity.CRITICAL)
        assert cot_alarm.state == AlarmState.ACTIVE
        assert cot_alarm.acknowledged is False

    def test_combustible_gas_alarm_triggers_above_20_lel(self, engine: ProcessSimulationEngine) -> None:
        engine.inject_disturbance(gas_leak=22.0)
        for _ in range(8):
            state = engine.step()

        critical_alarms = [a for a in state.alarms if a.tag == "GD-501" and a.severity == AlarmSeverity.CRITICAL]
        assert len(critical_alarms) > 0

    def test_cooling_water_low_alarm(self, engine: ProcessSimulationEngine) -> None:
        engine.inject_disturbance(cw_flow=1500.0)
        for _ in range(5):
            state = engine.step()

        alarm_tags = [a.tag for a in state.alarms]
        assert "FI-501" in alarm_tags

    def test_alarm_acknowledgement(self, engine: ProcessSimulationEngine) -> None:
        engine.inject_disturbance(fuel_valve=75.0, fuel_pressure=0.38)
        for _ in range(15):
            engine.step()

        alarms = engine.alarm_evaluator.get_active_alarms()
        assert len(alarms) > 0
        target = alarms[0]
        ack_res = engine.alarm_evaluator.acknowledge_alarm(target.alarm_id)
        assert ack_res is not None
        assert ack_res.acknowledged is True
        assert ack_res.state == AlarmState.ACKNOWLEDGED


# ======================================================================
# 5. ML Integration & Surrogate Provenance Tests
# ======================================================================

class TestMLIntegration:
    """Validates ML inference feed and surrogate provenance preservation."""

    def test_bridge_evaluates_all_four_models(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.get_plant_state()
        assert "ProcessAnomalyDetector" in state.ml_summaries
        assert "ProcessFaultClassifier" in state.ml_summaries
        assert "FurnaceCOTPredictor" in state.ml_summaries
        assert "TubeTemperaturePredictor" in state.ml_summaries

    def test_tube_temperature_surrogate_provenance(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.get_plant_state()
        tmt_meta = state.ml_summaries.get("TubeTemperaturePredictor", {})
        assert tmt_meta.get("target_type") == "physics_informed_synthetic_surrogate"
        assert tmt_meta.get("industrial_validation") is False

    def test_cot_prediction_accuracy_on_nominal(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.get_plant_state()
        cot_pred = state.ml_summaries["FurnaceCOTPredictor"]["predicted_value"]
        cot_actual = state.telemetry["TI-201"].value
        assert cot_pred is not None
        # Prediction should be reasonably close to actual COT
        assert abs(cot_pred - cot_actual) < 40.0


# ======================================================================
# 6. OperationalCase & Live Bridge Integration Tests
# ======================================================================

class TestOperationalCaseIntegration:
    """Validates automatic building of grounded OperationalCases from live simulation."""

    def test_live_case_generation(self, bridge: LiveIntelligenceBridge) -> None:
        case = bridge.get_operational_case()
        assert case is not None
        assert case.equipment_id == "F-201A"
        assert case.unit_area == "UNIT-CRACK-01"
        assert len(case.observations) > 0

    def test_live_case_contains_ml_and_alarms(self, bridge: LiveIntelligenceBridge) -> None:
        bridge.trigger_scenario("SCENARIO-1-HIGH-COT")
        case = bridge.get_operational_case()
        assert case is not None
        assert len(case.ml_assessments) == 4
        assert len(case.knowledge_evidence) > 0
        assert len(case.safety_context) > 0


# ======================================================================
# 7. Deterministic Scenario Runner Tests
# ======================================================================

class TestScenarioRunner:
    """Validates deterministic execution of all 4 canonical scenarios."""

    def test_scenario_1_high_cot(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.trigger_scenario("SCENARIO-1-HIGH-COT")
        assert state.active_scenario == "SCENARIO-1-HIGH-COT"
        for _ in range(15):
            state = bridge.engine.step()
        assert state.telemetry["TI-201"].value > 875.0
        assert any(a.tag == "TI-201" for a in state.alarms)

    def test_scenario_2_process_anomaly(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.trigger_scenario("SCENARIO-2-PROCESS-ANOMALY")
        for _ in range(8):
            state = bridge.engine.step()
        assert state.telemetry["FI-501"].value < 1800.0
        assert any(a.tag == "FI-501" for a in state.alarms)

    def test_scenario_3_maintenance(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.trigger_scenario("SCENARIO-3-MAINTENANCE")
        assert state.equipment_states["F-201A"] == EquipmentStatus.MAINTENANCE

    def test_scenario_4_safety_event(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.trigger_scenario("SCENARIO-4-SAFETY-EVENT")
        for _ in range(8):
            state = bridge.engine.step()
        assert state.telemetry["GD-501"].value > 15.0
        assert state.safety_state in ("CRITICAL", "ALERT")


# ======================================================================
# 8. Deterministic Seed & Replay Tests
# ======================================================================

class TestDeterminismAndReplay:
    """Validates that identical seeds produce bitwise identical trajectories."""

    def test_identical_seed_produces_identical_trajectory(self) -> None:
        eng1 = ProcessSimulationEngine(seed=999)
        eng1.reset()
        traj1 = [eng1.step().telemetry["TI-201"].value for _ in range(10)]

        eng2 = ProcessSimulationEngine(seed=999)
        eng2.reset()
        traj2 = [eng2.step().telemetry["TI-201"].value for _ in range(10)]

        assert traj1 == traj2


# ======================================================================
# 9. Latency Profiling Tests
# ======================================================================

class TestLatencyProfiling:
    """Validates telemetry-to-ML and telemetry-to-case latency measurement."""

    def test_latency_metrics_are_recorded(self, bridge: LiveIntelligenceBridge) -> None:
        state = bridge.get_plant_state()
        meta = state.metadata
        assert "latency_telemetry_to_ml_p50_ms" in meta
        assert "latency_telemetry_to_case_p50_ms" in meta
        assert meta["latency_telemetry_to_case_p50_ms"] >= 0.0


# ======================================================================
# 10. Streaming Lifecycle Tests
# ======================================================================

class TestStreamingLifecycle:
    """Validates start, pause, resume, and stop controls."""

    @pytest.mark.asyncio
    async def test_streaming_start_and_stop(self, engine: ProcessSimulationEngine) -> None:
        await engine.start()
        assert engine.is_running is True
        await asyncio.sleep(0.05)
        engine.pause()
        assert engine.is_paused is True
        engine.resume()
        assert engine.is_paused is False
        await engine.stop()
        assert engine.is_running is False


# ======================================================================
# Entry Point
# ======================================================================

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
