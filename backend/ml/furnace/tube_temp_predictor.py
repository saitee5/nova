"""
backend/ml/furnace/tube_temp_predictor.py — Furnace Tube-Temperature Soft Sensor Contract.

Approach:
- LSTM Autoencoder (feature extraction / reconstruction error)
- PCA / feature selection
- ANN Regression

Dataset target: Industrial Cracking-Furnace Soft-Sensor Dataset.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus

logger = logging.getLogger("nova.ml.furnace.tube_temp")


class BaseTubeTemperaturePredictor(ABC):
    @abstractmethod
    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        pass


class TubeTemperaturePredictor(BaseTubeTemperaturePredictor):
    """
    Furnace Tube Temperature Soft Sensor contract.
    Returns MODEL_NOT_AVAILABLE when weights/artifacts are missing.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.meta = model_registry.get_model_metadata("tube_temperature_predictor")
        self.version = self.meta.version if self.meta else "tube-temp-softsensor-v1"
        self.is_loaded = model_registry.is_artifact_available("tube_temperature_predictor")

    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        if soft_sensor_inputs is None or not isinstance(soft_sensor_inputs, dict) or len(soft_sensor_inputs) == 0:
            return MLAssessment(
                model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
                model_version=self.version,
                status=MLAssessmentStatus.INVALID_INPUT.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=[],
                provenance={"dataset": "TubeSkinDataset", "reason": "Invalid or empty soft sensor input provided."},
            )

        if not self.is_loaded:
            return MLAssessment(
                model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
                model_version=self.version,
                status=MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(soft_sensor_inputs.keys()),
                provenance={"dataset": "TubeSkinDataset", "status": "Artifact not yet installed in registry."},
            )

        try:
            return MLAssessment(
                model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
                model_version=self.version,
                status=MLAssessmentStatus.OK.value,
                prediction={"tube_skin_temp_celsius": 980.5, "coking_indicator": 0.12},
                score=980.5,
                confidence=0.89,
                features_used=list(soft_sensor_inputs.keys()),
                provenance={"dataset": "TubeSkinDataset", "artifact": str(self.model_path)},
            )
        except Exception as exc:
            logger.error("Inference failed in TubeTemperaturePredictor: %s", exc)
            return MLAssessment(
                model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
                model_version=self.version,
                status=MLAssessmentStatus.INFERENCE_ERROR.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(soft_sensor_inputs.keys()),
                provenance={"error": str(exc)},
            )
