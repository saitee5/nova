"""
backend/ml/features/extractor.py — Industrial Process Feature Extraction Infrastructure.

Extracts dynamic feature representations from temporal windows of process telemetry:
- raw values
- delta (first-order difference)
- rate of change (delta / time)
- rolling statistical aggregates (mean, std, min, max)
- baseline deviation from nominal steady-state targets
- operating mode categorical/one-hot encoding
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.models.industrial_domain import OperatingMode, PlantState, ProcessTelemetry


@dataclass
class TelemetryPoint:
    timestamp: datetime
    value: float


@dataclass
class FeatureWindow:
    """Temporal sliding window containing time-ordered sensor observations."""
    window_size_seconds: float = 300.0  # 5-minute nominal window
    history: Dict[str, List[TelemetryPoint]] = field(default_factory=dict)
    operating_mode: OperatingMode = OperatingMode.NORMAL
    asset_id: Optional[str] = None

    def add_reading(self, parameter: str, value: float, timestamp: Optional[datetime] = None) -> None:
        """Add a sensor observation to the feature window and evict points outside window."""
        ts = timestamp or datetime.now(timezone.utc)
        if parameter not in self.history:
            self.history[parameter] = []
        self.history[parameter].append(TelemetryPoint(timestamp=ts, value=float(value)))

        # Evict older samples outside window duration
        cutoff_epoch = ts.timestamp() - self.window_size_seconds
        self.history[parameter] = [
            pt for pt in self.history[parameter] if pt.timestamp.timestamp() >= cutoff_epoch
        ]

    def get_series(self, parameter: str) -> List[float]:
        """Return list of historical float values in chronological order."""
        return [pt.value for pt in self.history.get(parameter, [])]

    def get_timestamps(self, parameter: str) -> List[datetime]:
        """Return list of historical timestamps in chronological order."""
        return [pt.timestamp for pt in self.history.get(parameter, [])]


class FeatureExtractor:
    """
    Standardized Feature Extractor for Industrial Machine Learning.

    Transforms raw multi-variate process time-series into normalized feature vectors
    ready for model inference (Process Anomaly, Fault Diagnosis, Furnace COT, Tube Temp).
    """

    def __init__(self, baselines: Optional[Dict[str, float]] = None) -> None:
        # Nominal steady-state baseline targets for key parameters
        self.baselines = baselines or {
            "coil_outlet_temperature": 845.0,
            "TI-20101": 845.0,
            "TI-20102": 846.5,
            "tube_skin_temperature": 980.0,
            "compressor_vibration": 1.5,
            "compressor_suction_pressure": 2.2,
            "tle_pressure_drop": 0.45,
        }

    def build_window(
        self,
        plant_state: Optional[PlantState] = None,
        raw_telemetry: Optional[List[ProcessTelemetry | Dict[str, Any]]] = None,
        window_size_seconds: float = 300.0,
    ) -> FeatureWindow:
        """Construct a FeatureWindow from PlantState or raw telemetry events."""
        window = FeatureWindow(window_size_seconds=window_size_seconds)
        if plant_state:
            window.operating_mode = plant_state.operating_mode
            for key, telem in plant_state.telemetry.items():
                param = telem.parameter or telem.tag or key
                window.add_reading(param, telem.value, telem.timestamp)
                window.asset_id = telem.asset_id

        if raw_telemetry:
            for item in raw_telemetry:
                if isinstance(item, dict):
                    item = ProcessTelemetry(**item)
                param = item.parameter or item.tag
                window.add_reading(param, item.value, item.timestamp)
                if not window.asset_id:
                    window.asset_id = item.asset_id

        return window

    def transform(self, window: FeatureWindow, selected_parameters: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Extract engineered feature vector from FeatureWindow.

        Features extracted per parameter:
        - raw: current most recent value
        - delta: change from first reading in window
        - rate_of_change: (last - first) / duration_seconds
        - rolling_mean: average across window
        - rolling_std: sample standard deviation across window
        - rolling_min: minimum observed value in window
        - rolling_max: maximum observed value in window
        - baseline_deviation: current value - nominal baseline
        """
        features: Dict[str, float] = {}
        parameters = selected_parameters or list(window.history.keys())

        for param in parameters:
            series = window.get_series(param)
            timestamps = window.get_timestamps(param)

            if not series:
                continue

            current_val = series[-1]
            features[f"{param}_raw"] = current_val

            if len(series) >= 2:
                delta = current_val - series[0]
                duration = max(1.0, (timestamps[-1] - timestamps[0]).total_seconds())
                rate_of_change = delta / duration

                mean = sum(series) / len(series)
                variance = sum((x - mean) ** 2 for x in series) / len(series)
                std = math.sqrt(variance)
                min_val = min(series)
                max_val = max(series)
            else:
                delta = 0.0
                rate_of_change = 0.0
                mean = current_val
                std = 0.0
                min_val = current_val
                max_val = current_val

            features[f"{param}_delta"] = round(delta, 4)
            features[f"{param}_rate_of_change"] = round(rate_of_change, 6)
            features[f"{param}_rolling_mean"] = round(mean, 4)
            features[f"{param}_rolling_std"] = round(std, 4)
            features[f"{param}_rolling_min"] = round(min_val, 4)
            features[f"{param}_rolling_max"] = round(max_val, 4)

            # Baseline deviation
            baseline = self.baselines.get(param, mean)
            features[f"{param}_baseline_deviation"] = round(current_val - baseline, 4)

        # Operating mode context features (one-hot indicator flag for active mode)
        for mode in OperatingMode:
            features[f"mode_{mode.value.lower()}"] = 1.0 if window.operating_mode == mode else 0.0

        return features
