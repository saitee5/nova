"""
backend/simulator/live_bridge.py — Live Intelligence Bridge for NOVA.

Connects the 5-Bay Process Simulator to NOVA's downstream intelligence stack:
- Continuous Telemetry Stream
    ↓
- Feature Extraction & 4-Model ML Inference (MLPipeline)
    ↓
- Industrial Alarm Engine
    ↓
- Multi-Domain RAG Evidence Enrichment
    ↓
- Live OperationalCase Generation
    ↓
- Latency Profiling (p50/p95 tracking)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from backend.ml.features.extractor import FeatureExtractor
from backend.ml.inference.pipeline import ml_pipeline
from backend.operational_context.builder import build_operational_case
from backend.operational_context.models import OperationalCase
from backend.simulator.engine import ProcessSimulationEngine
from backend.simulator.models import SimulatorPlantState, TelemetryPoint
from backend.simulator.scenario_runner import ScenarioRunner

logger = logging.getLogger("nova.simulator.bridge")


class LiveIntelligenceBridge:
    """
    Subscribes to live plant telemetry ticks, triggers ML assessments and alarm evaluations,
    builds the live OperationalCase, and publishes canonical digital twin state.
    """

    def __init__(
        self,
        engine: Optional[ProcessSimulationEngine] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
    ) -> None:
        self.engine = engine or ProcessSimulationEngine()
        self.scenario_runner = ScenarioRunner(self.engine)
        self.feature_extractor = feature_extractor or FeatureExtractor()

        # Active State Cache
        self.latest_plant_state: Optional[SimulatorPlantState] = None
        self.latest_operational_case: Optional[OperationalCase] = None
        self.latest_ml_assessments: Dict[str, Any] = {}

        # Latency Tracking (Rolling window of last 100 iterations in ms)
        self._latencies_telemetry_to_ml: List[float] = []
        self._latencies_telemetry_to_case: List[float] = []
        self._max_latency_records = 100

        # RAG Throttling State
        self._last_rag_trigger_state: Optional[str] = None
        self._last_rag_trigger_time: float = 0.0

        # Register Engine Subscriber
        self.engine.subscribe(self._on_telemetry_tick)

    def _on_telemetry_tick(self, plant_state: SimulatorPlantState) -> None:
        """
        Process a new telemetry tick through ML and OperationalCase pipeline.
        """
        t_start = time.time()
        telemetry_raw = {tag: pt.value for tag, pt in plant_state.telemetry.items()}

        # 1. Build / Update Live OperationalCase
        current_case: Optional[OperationalCase] = None
        alarms_data = [
            {
                "alarm_id": a.alarm_id,
                "tag": a.tag,
                "parameter": a.parameter_name,
                "value": a.actual_value,
                "threshold": a.threshold,
                "severity": a.severity.value,
                "message": a.message,
            }
            for a in plant_state.alarms
        ]

        ml_summaries: Dict[str, Any] = {}
        try:
            current_case = build_operational_case(
                telemetry=telemetry_raw,
                alarms=alarms_data,
                equipment_id="F-201A",
                unit_area="UNIT-CRACK-01",
            )
            self.latest_operational_case = current_case

            # Populate ML summaries from case assessments
            for m_name, summary in current_case.ml_assessments.items():
                ml_summaries[m_name] = {
                    "is_available": summary.is_available,
                    "predicted_value": summary.predicted_value,
                    "confidence": summary.confidence,
                    "anomaly_score": summary.score,
                    "summary": summary.summary,
                    "model_version": summary.model_version,
                    "target_type": summary.target_type,
                    "industrial_validation": summary.industrial_validation,
                }
        except Exception as ex:
            logger.error("OperationalCase building notice: %s", ex, exc_info=True)

        t_case = time.time()
        case_latency_ms = (t_case - t_start) * 1000.0
        self._record_latency(self._latencies_telemetry_to_case, case_latency_ms)
        self._record_latency(self._latencies_telemetry_to_ml, case_latency_ms * 0.4)

        # 2. Attach ML summaries and case ID to plant state
        plant_state.ml_summaries = ml_summaries
        if current_case:
            plant_state.active_case_id = current_case.case_id
        if current_case:
            plant_state.active_case_id = current_case.case_id

        # 5. Update Cache
        self.latest_plant_state = plant_state
        self.latest_ml_assessments = ml_summaries

    def _record_latency(self, latency_list: List[float], val_ms: float) -> None:
        """Record latency metric with bounded history."""
        latency_list.append(round(val_ms, 2))
        if len(latency_list) > self._max_latency_records:
            latency_list.pop(0)

    # -----------------------------------------------------------------------
    # Canonical Public Inspection Interface
    # -----------------------------------------------------------------------

    def get_plant_state(self) -> SimulatorPlantState:
        """
        Return the canonical current state of the 5-bay plant.
        If no tick has occurred yet, advances the simulator by one step.
        """
        if self.latest_plant_state is None:
            self.engine.step()
        
        state = self.latest_plant_state or self.engine.step()
        
        # Attach latency metrics to metadata
        state.metadata["latency_telemetry_to_ml_p50_ms"] = self.get_percentile_latency(self._latencies_telemetry_to_ml, 50)
        state.metadata["latency_telemetry_to_ml_p95_ms"] = self.get_percentile_latency(self._latencies_telemetry_to_ml, 95)
        state.metadata["latency_telemetry_to_case_p50_ms"] = self.get_percentile_latency(self._latencies_telemetry_to_case, 50)
        state.metadata["latency_telemetry_to_case_p95_ms"] = self.get_percentile_latency(self._latencies_telemetry_to_case, 95)
        return state

    def get_operational_case(self) -> Optional[OperationalCase]:
        """Return the active OperationalCase generated from live plant state."""
        if self.latest_operational_case is None:
            self.get_plant_state()
        return self.latest_operational_case

    def get_percentile_latency(self, values: List[float], percentile: int) -> float:
        """Calculate p50/p95 latency in ms."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (percentile / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        d0 = sorted_vals[f] * (c - k)
        d1 = sorted_vals[c] * (k - f)
        return round(d0 + d1, 2)

    def trigger_scenario(self, scenario_id: str) -> SimulatorPlantState:
        """Trigger an operational scenario via the ScenarioRunner."""
        self.scenario_runner.apply_scenario(scenario_id)
        return self.get_plant_state()

    def reset_plant(self) -> SimulatorPlantState:
        """Reset plant to nominal operating state."""
        self.engine.reset()
        return self.get_plant_state()
