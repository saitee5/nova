"""
backend/ml/furnace/cot_predictor.py — Furnace COT (Coil Outlet Temperature) Predictor Contract.

Models:
- Primary: CNN + BiLSTM + Attention
- Baseline: XGBoost Regression

Dataset target: Industrial Ethylene Cracking Furnace Dataset.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from backend.models.industrial_domain import MLAssessment


class BaseFurnaceCOTPredictor(ABC):
    @abstractmethod
    def predict_cot(self, furnace_telemetry: Dict[str, float]) -> MLAssessment:
        pass


class FurnaceCOTPredictor(BaseFurnaceCOTPredictor):
    """
    Furnace COT Predictor interface contract.
    Returns MODEL_NOT_AVAILABLE when weights are absent.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.is_loaded = False

    def predict_cot(self, furnace_telemetry: Dict[str, float]) -> MLAssessment:
        if not self.is_loaded:
            return MLAssessment(
                model_name="FurnaceCOTPredictor (CNN+BiLSTM+Attention)",
                model_version="1.0-contract",
                status="MODEL_NOT_AVAILABLE",
                prediction=None,
                confidence=None,
            )

        return MLAssessment(
            model_name="FurnaceCOTPredictor (CNN+BiLSTM+Attention)",
            model_version="1.0-contract",
            status="SUCCESS",
            prediction={"predicted_cot_celsius": 845.2, "target_cot_celsius": 845.0},
            confidence=0.92,
        )
