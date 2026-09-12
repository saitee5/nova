"""
backend/ml/runtime/mocks.py — Mock ML Model Implementations.

IMPORTANT: These are MOCK models for parallel development purposes only.
They are NOT trained on real industrial data.
They are NOT production-ready.
They must NEVER be presented as trained models.

Purpose:
  Allow backend intelligence development (Context, Risk, Episode, Agents)
  to proceed before Arushi delivers trained model artifacts.

Usage:
  runtime = build_mock_ml_runtime()
  evidence = runtime.run(asset_id="F-201A", telemetry={...})

Replacement:
  When Arushi delivers trained artifacts, configure MLRuntime to use
  ProcessAnomalyDetector / ProcessFaultClassifier / FurnaceCOTPredictor /
  TubeTemperaturePredictor instead of the mocks.
  Context / Risk / Episode / Agent code requires no changes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.ml.runtime.contracts import (
    AnomalyPayload,
    COTPredictionPayload,
    FaultPayload,
    MLEvidence,
    MLEvidenceQuality,
    MLEvidenceStatus,
    MLPredictionType,
    TubeTemperaturePayload,
)

logger = logging.getLogger("nova.ml.runtime.mocks")

_MOCK_LABEL = "[MOCK — NOT A TRAINED MODEL]"


class MockAnomalyModel:
    """
    MOCK process anomaly detector.
    Produces controllable anomaly scores for development / testing.
    NOT trained on industrial data. NOT production-ready.
    """

    MODEL_NAME = f"MockProcessAnomalyDetector {_MOCK_LABEL}"
    MODEL_VERSION = "mock-0.0.0"

    def __init__(self, force_anomaly: bool = False, anomaly_score: float = 0.1) -> None:
        """
        Args:
            force_anomaly: Always report anomaly = True when True.
            anomaly_score: Default anomaly score [0.0, 1.0].
        """
        self.force_anomaly = force_anomaly
        self._default_score = max(0.0, min(1.0, anomaly_score))

    def predict(
        self,
        telemetry: Dict[str, float],
        asset_id: str = "unknown",
    ) -> MLEvidence:
        if not isinstance(telemetry, dict) or len(telemetry) == 0:
            return MLEvidence(
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
                prediction_type=MLPredictionType.ANOMALY,
                asset_id=asset_id,
                status=MLEvidenceStatus.INVALID_INPUT,
                prediction=None,
                quality=MLEvidenceQuality.BAD,
                source="mock",
                provenance={"mock": True, "reason": "empty or invalid telemetry"},
            )

        score = self._default_score
        is_anomaly = self.force_anomaly or score >= 0.5
        payload = AnomalyPayload(
            is_anomaly=is_anomaly,
            anomaly_score=score,
            pca_score=score * 0.6,
            if_score=score * 0.4,
            confidence=0.5 + abs(score - 0.5),
        )
        return MLEvidence(
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            prediction_type=MLPredictionType.ANOMALY,
            asset_id=asset_id,
            status=MLEvidenceStatus.OK,
            prediction=payload.model_dump(),
            confidence=payload.confidence,
            quality=MLEvidenceQuality.GOOD,
            features_used=list(telemetry.keys())[:10],
            source="mock",
            provenance={
                "mock": True,
                "warning": "MOCK — not a trained model",
                "force_anomaly": self.force_anomaly,
            },
        )


class MockFaultModel:
    """
    MOCK process fault classifier.
    Returns a configurable predicted fault label for development / testing.
    NOT trained on industrial data. NOT production-ready.
    """

    MODEL_NAME = f"MockProcessFaultClassifier {_MOCK_LABEL}"
    MODEL_VERSION = "mock-0.0.0"

    def __init__(self, predicted_fault: str = "NORMAL", confidence: float = 0.85) -> None:
        self._fault = predicted_fault
        self._confidence = max(0.0, min(1.0, confidence))

    def predict(
        self,
        telemetry: Dict[str, float],
        asset_id: str = "unknown",
    ) -> MLEvidence:
        if not isinstance(telemetry, dict) or len(telemetry) == 0:
            return MLEvidence(
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
                prediction_type=MLPredictionType.FAULT_CLASSIFICATION,
                asset_id=asset_id,
                status=MLEvidenceStatus.INVALID_INPUT,
                prediction=None,
                quality=MLEvidenceQuality.BAD,
                source="mock",
                provenance={"mock": True, "reason": "empty or invalid telemetry"},
            )

        payload = FaultPayload(
            predicted_fault=self._fault,
            confidence=self._confidence,
            fault_probabilities={self._fault: self._confidence, "NORMAL": 1.0 - self._confidence},
            top_k_faults=[
                {"fault": self._fault, "probability": self._confidence},
                {"fault": "NORMAL", "probability": 1.0 - self._confidence},
            ],
        )
        return MLEvidence(
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            prediction_type=MLPredictionType.FAULT_CLASSIFICATION,
            asset_id=asset_id,
            status=MLEvidenceStatus.OK,
            prediction=payload.model_dump(),
            confidence=payload.confidence,
            quality=MLEvidenceQuality.GOOD,
            features_used=list(telemetry.keys())[:10],
            source="mock",
            provenance={
                "mock": True,
                "warning": "MOCK — not a trained model",
                "configured_fault": self._fault,
            },
        )


class MockCOTModel:
    """
    MOCK furnace COT predictor.
    Returns a configurable predicted COT value for development / testing.
    NOT trained on industrial data. NOT production-ready.
    """

    MODEL_NAME = f"MockFurnaceCOTPredictor {_MOCK_LABEL}"
    MODEL_VERSION = "mock-0.0.0"

    def __init__(self, predicted_cot: float = 845.0) -> None:
        self._cot = predicted_cot

    def predict(
        self,
        telemetry: Dict[str, float],
        asset_id: str = "unknown",
    ) -> MLEvidence:
        if not isinstance(telemetry, dict) or len(telemetry) == 0:
            return MLEvidence(
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
                prediction_type=MLPredictionType.COT_PREDICTION,
                asset_id=asset_id,
                status=MLEvidenceStatus.INVALID_INPUT,
                prediction=None,
                units="celsius",
                quality=MLEvidenceQuality.BAD,
                source="mock",
                provenance={"mock": True, "reason": "empty or invalid telemetry"},
            )

        # Check if actual COT supplied (allows residual tracking)
        actual_cot: Optional[float] = None
        for k, v in telemetry.items():
            if k.lower() in {"coil_outlet_temperature", "ti-20101", "actual_cot", "cot"}:
                try:
                    actual_cot = float(v)
                    break
                except (TypeError, ValueError):
                    pass

        payload = COTPredictionPayload(
            predicted_cot=self._cot,
            unit="celsius",
            actual_cot=actual_cot,
            residual=round(actual_cot - self._cot, 2) if actual_cot is not None else None,
        )
        return MLEvidence(
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            prediction_type=MLPredictionType.COT_PREDICTION,
            asset_id=asset_id,
            status=MLEvidenceStatus.OK,
            prediction=payload.model_dump(),
            confidence=None,  # COT regression: no calibrated probability
            units="celsius",
            quality=MLEvidenceQuality.GOOD,
            features_used=list(telemetry.keys())[:10],
            source="mock",
            provenance={
                "mock": True,
                "warning": "MOCK — not a trained model",
                "configured_cot": self._cot,
            },
        )


class MockTubeTemperatureModel:
    """
    MOCK tube temperature soft sensor.
    Returns a configurable predicted tube skin temperature for dev/testing.
    NOT trained on industrial data. NOT production-ready.
    NOTE: Does NOT include coking_index — that requires a separately validated model.
    """

    MODEL_NAME = f"MockTubeTemperaturePredictor {_MOCK_LABEL}"
    MODEL_VERSION = "mock-0.0.0"

    def __init__(self, predicted_temp: float = 980.0, confidence: Optional[float] = None) -> None:
        self._temp = predicted_temp
        self._confidence = confidence

    def predict(
        self,
        telemetry: Dict[str, float],
        asset_id: str = "unknown",
    ) -> MLEvidence:
        if not isinstance(telemetry, dict) or len(telemetry) == 0:
            return MLEvidence(
                model_name=self.MODEL_NAME,
                model_version=self.MODEL_VERSION,
                prediction_type=MLPredictionType.TUBE_TEMPERATURE,
                asset_id=asset_id,
                status=MLEvidenceStatus.INVALID_INPUT,
                prediction=None,
                units="celsius",
                quality=MLEvidenceQuality.BAD,
                source="mock",
                provenance={"mock": True, "reason": "empty or invalid telemetry"},
            )

        payload = TubeTemperaturePayload(
            predicted_tube_temperature=self._temp,
            unit="celsius",
            confidence=self._confidence,
        )
        return MLEvidence(
            model_name=self.MODEL_NAME,
            model_version=self.MODEL_VERSION,
            prediction_type=MLPredictionType.TUBE_TEMPERATURE,
            asset_id=asset_id,
            status=MLEvidenceStatus.OK,
            prediction=payload.model_dump(),
            confidence=self._confidence,
            units="celsius",
            quality=MLEvidenceQuality.GOOD,
            features_used=list(telemetry.keys())[:10],
            source="mock",
            provenance={
                "mock": True,
                "warning": "MOCK — not a trained model",
                "configured_temp": self._temp,
                "coking_index_excluded": "not a validated target",
            },
        )


def build_mock_ml_runtime(
    anomaly_score: float = 0.1,
    force_anomaly: bool = False,
    predicted_fault: str = "NORMAL",
    fault_confidence: float = 0.85,
    predicted_cot: float = 845.0,
    predicted_tube_temp: float = 980.0,
) -> "MLRuntime":  # type: ignore[name-defined]  # avoid circular import
    """
    Build an MLRuntime configured with all four mock models.

    This is the standard entry point for test and development scenarios.
    Adjust parameters to control mock model behavior per test scenario.
    """
    from backend.ml.runtime.runtime import MLRuntime

    return MLRuntime(
        anomaly_model=MockAnomalyModel(
            force_anomaly=force_anomaly,
            anomaly_score=anomaly_score,
        ),
        fault_model=MockFaultModel(
            predicted_fault=predicted_fault,
            confidence=fault_confidence,
        ),
        cot_model=MockCOTModel(predicted_cot=predicted_cot),
        tube_temp_model=MockTubeTemperatureModel(predicted_temp=predicted_tube_temp),
    )
