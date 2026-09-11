"""
backend/ml/inference/pipeline.py — Industrial ML Inference Orchestration Pipeline.

Orchestrates inference across:
1. Process Anomaly Detection (PCA + Isolation Forest)
2. Process Fault Diagnosis (XGBoost Multiclass)
3. Furnace COT Prediction (CNN + BiLSTM + Attention)
4. Tube Temperature Soft Sensor (LSTM-AE + ANN)

Returns structured MLAssessment results. Never fabricates predictions if model files do not exist.
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from backend.ml.anomaly.detector import ProcessAnomalyDetector
from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor
from backend.ml.furnace.tube_temp_predictor import TubeTemperaturePredictor
from backend.models.industrial_domain import MLAssessment

logger = logging.getLogger("nova.ml.inference")


class IndustrialMLInferencePipeline:
    """Unified ML inference pipeline for industrial process assessments."""

    def __init__(self) -> None:
        self.anomaly_detector = ProcessAnomalyDetector()
        self.fault_classifier = ProcessFaultClassifier()
        self.cot_predictor = FurnaceCOTPredictor()
        self.tube_temp_predictor = TubeTemperaturePredictor()

    def run_inference_suite(self, asset_id: str, telemetry: Dict[str, float]) -> Dict[str, MLAssessment]:
        """Run all 4 ML inference models on asset telemetry vector."""
        results = {
            "anomaly_detection": self.anomaly_detector.detect_anomaly(telemetry),
            "fault_diagnosis": self.fault_classifier.classify_fault(telemetry),
            "furnace_cot_prediction": self.cot_predictor.predict_cot(telemetry),
            "tube_temperature_soft_sensor": self.tube_temp_predictor.predict_tube_temperature(telemetry),
        }
        logger.info("Executed ML inference suite for asset %s | status: %s", asset_id, [r.status for r in results.values()])
        return results


# Global singleton instance
ml_pipeline = IndustrialMLInferencePipeline()
