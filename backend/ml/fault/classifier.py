"""
backend/ml/fault/classifier.py — Process Fault Diagnosis Interface Contract.

Model: XGBoost Multiclass Classifier
Dataset target: Tennessee Eastman Process (TEP) labeled fault scenarios (Faults 1 to 21).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from backend.models.industrial_domain import MLAssessment


class BaseFaultClassifier(ABC):
    """Abstract Base Class for Process Fault Diagnosis."""

    @abstractmethod
    def classify_fault(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        """Classify fault type and return MLAssessment."""
        pass


class ProcessFaultClassifier(BaseFaultClassifier):
    """
    Process Fault Classifier implementation contract.
    Returns MODEL_NOT_AVAILABLE if trained model is absent.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.is_loaded = False

    def classify_fault(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        if not self.is_loaded:
            return MLAssessment(
                model_name="ProcessFaultClassifier (XGBoost Multiclass)",
                model_version="1.0-contract",
                status="MODEL_NOT_AVAILABLE",
                prediction=None,
                confidence=None,
            )

        return MLAssessment(
            model_name="ProcessFaultClassifier (XGBoost Multiclass)",
            model_version="1.0-contract",
            status="SUCCESS",
            prediction={"fault_code": "NORMAL_OPERATION", "fault_probability": 0.98},
            confidence=0.98,
        )
