"""
backend/ml/furnace/tube_temp_predictor.py — Furnace Tube-Temperature Soft Sensor Contract.

Approach:
- LSTM Autoencoder (feature extraction / reconstruction error)
- PCA / feature selection
- ANN Regression

Dataset target: Industrial Cracking-Furnace Soft-Sensor Dataset.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from backend.models.industrial_domain import MLAssessment


class BaseTubeTemperaturePredictor(ABC):
    @abstractmethod
    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        pass


class TubeTemperaturePredictor(BaseTubeTemperaturePredictor):
    """
    Furnace Tube Temperature Soft Sensor contract.
    Returns MODEL_NOT_AVAILABLE when weights are missing.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.is_loaded = False

    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        if not self.is_loaded:
            return MLAssessment(
                model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
                model_version="1.0-contract",
                status="MODEL_NOT_AVAILABLE",
                prediction=None,
                confidence=None,
            )

        return MLAssessment(
            model_name="TubeTemperaturePredictor (LSTM-AE + ANN)",
            model_version="1.0-contract",
            status="SUCCESS",
            prediction={"tube_skin_temp_celsius": 980.5, "coking_indicator": 0.12},
            confidence=0.89,
        )
