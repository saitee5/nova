"""
backend/ml/inference/pipeline.py — Industrial ML Inference Orchestration Pipeline.

Orchestrates inference across:
1. Process Anomaly Detection (PCA + Isolation Forest)
2. Process Fault Diagnosis (XGBoost Multiclass)
3. Furnace COT Prediction (CNN + BiLSTM + Attention / XGBoost Baseline)
4. Tube Temperature Soft Sensor (LSTM-AE + ANN)

Accepts:
- PlantState snapshot
- FeatureWindow temporal window
- Raw telemetry parameter dict

Always returns structured, typed MLAssessment results with accurate status (OK, MODEL_NOT_AVAILABLE, etc.).
Never fabricates predictions if model files do not exist.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from backend.ml.anomaly.detector import ProcessAnomalyDetector
from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.features.extractor import FeatureExtractor, FeatureWindow
from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor
from backend.ml.furnace.tube_temp_predictor import TubeTemperaturePredictor
from backend.models.industrial_domain import MLAssessment, PlantState

logger = logging.getLogger("nova.ml.inference")


class MLPipeline:
    """Unified ML inference pipeline for industrial process assessments."""

    def __init__(
        self,
        anomaly_detector: Optional[ProcessAnomalyDetector] = None,
        fault_classifier: Optional[ProcessFaultClassifier] = None,
        cot_predictor: Optional[FurnaceCOTPredictor] = None,
        tube_temp_predictor: Optional[TubeTemperaturePredictor] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
    ) -> None:
        self.anomaly_detector = anomaly_detector or ProcessAnomalyDetector()
        self.fault_classifier = fault_classifier or ProcessFaultClassifier()
        self.cot_predictor = cot_predictor or FurnaceCOTPredictor()
        self.furnace_cot_predictor = self.cot_predictor
        self.tube_temp_predictor = tube_temp_predictor or TubeTemperaturePredictor()
        self.feature_extractor = feature_extractor or FeatureExtractor()


    def run_pipeline(
        self,
        input_data: Union[PlantState, FeatureWindow, Dict[str, float]],
        asset_id: Optional[str] = None,
    ) -> Dict[str, MLAssessment]:
        """
        Execute full ML inference suite against PlantState, FeatureWindow, or raw telemetry vector.

        Returns a dictionary of MLAssessment objects keyed by model category:
        - anomaly_detection
        - fault_diagnosis
        - furnace_cot_prediction
        - tube_temperature_soft_sensor
        """
        resolved_asset_id = asset_id or "F-201A"
        telemetry_vector: Dict[str, float] = {}

        if isinstance(input_data, PlantState):
            # Extract features from current plant state
            window = self.feature_extractor.build_window(plant_state=input_data)
            telemetry_vector = self.feature_extractor.transform(window)
            # Add direct raw readings
            for key, t in input_data.telemetry.items():
                param = t.parameter or t.tag or key
                telemetry_vector[param] = t.value
            if not asset_id and input_data.telemetry:
                first_telem = next(iter(input_data.telemetry.values()))
                resolved_asset_id = first_telem.asset_id
        elif isinstance(input_data, FeatureWindow):
            telemetry_vector = self.feature_extractor.transform(input_data)
            if input_data.asset_id:
                resolved_asset_id = input_data.asset_id

        elif isinstance(input_data, dict):
            telemetry_vector = {str(k): float(v) for k, v in input_data.items()}

        active_cot = getattr(self, "furnace_cot_predictor", None) or self.cot_predictor

        results: Dict[str, MLAssessment] = {
            "anomaly_detection": self.anomaly_detector.detect_anomaly(telemetry_vector),
            "fault_diagnosis": self.fault_classifier.classify_fault(telemetry_vector),
            "furnace_cot_prediction": active_cot.predict_cot(telemetry_vector, asset_id=resolved_asset_id),
            "tube_temperature_soft_sensor": self.tube_temp_predictor.predict_tube_temperature(telemetry_vector),
        }

        statuses = [r.status for r in results.values()]
        logger.info("Executed MLPipeline for asset %s | model statuses: %s", resolved_asset_id, statuses)
        return results

    def run_inference_suite(self, asset_id: str, telemetry: Dict[str, float]) -> Dict[str, MLAssessment]:
        """Backward-compatible API for legacy callers."""
        return self.run_pipeline(input_data=telemetry, asset_id=asset_id)


# Backward-compatible alias
IndustrialMLInferencePipeline = MLPipeline

# Global singleton instance
ml_pipeline = MLPipeline()
