"""
backend/ml/runtime/runtime.py — MLRuntime Orchestrator.

MLRuntime is the standardized runtime integration layer that:
  1. Accepts a telemetry dict for a given asset_id
  2. Dispatches to all four ML models (or their mocks)
  3. Returns a list of MLEvidence records (canonical, typed)

Design:
  - Protocol-based model interface: any object with .predict(telemetry, asset_id) → MLEvidence
  - Graceful degradation: model failure → MLEvidence with status=INFERENCE_ERROR (never crashes)
  - Real-model adapter: wraps existing MLPipeline / MLAssessment → MLEvidence translation
  - Mock adapter: wraps MockAnomalyModel / MockFaultModel / MockCOTModel / MockTubeTemp → MLEvidence

Swapping from mock to real models requires only changing the constructor arguments
of MLRuntime — no changes to Context, Risk, Episode, or Agent logic.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from backend.ml.runtime.contracts import (
    MLEvidence,
    MLEvidenceQuality,
    MLEvidenceStatus,
    MLPredictionType,
)

logger = logging.getLogger("nova.ml.runtime")


# ---------------------------------------------------------------------------
# Model Protocol (structural typing — no inheritance required)
# ---------------------------------------------------------------------------

@runtime_checkable
class MLModelProtocol(Protocol):
    """
    Structural protocol for all ML model adapters.

    Any object implementing predict(telemetry, asset_id) → MLEvidence
    satisfies this protocol — works for mock models, real model adapters,
    and future Arushi-trained model wrappers without inheritance.
    """
    def predict(
        self,
        telemetry: Dict[str, float],
        asset_id: str,
    ) -> MLEvidence: ...


# ---------------------------------------------------------------------------
# Real Model Adapters (MLAssessment → MLEvidence)
# ---------------------------------------------------------------------------

class RealAnomalyModelAdapter:
    """
    Adapter wrapping the real ProcessAnomalyDetector → MLEvidence.
    Uses the existing MLPipeline from backend.ml.inference.pipeline.
    """

    def predict(self, telemetry: Dict[str, float], asset_id: str) -> MLEvidence:
        try:
            from backend.ml.inference.pipeline import ml_pipeline
            from backend.models.industrial_domain import MLAssessmentStatus

            assessment = ml_pipeline.run_anomaly_detection(telemetry)

            status_map = {
                MLAssessmentStatus.OK.value: MLEvidenceStatus.OK,
                MLAssessmentStatus.MODEL_NOT_AVAILABLE.value: MLEvidenceStatus.MODEL_NOT_AVAILABLE,
                MLAssessmentStatus.INVALID_INPUT.value: MLEvidenceStatus.INVALID_INPUT,
                MLAssessmentStatus.INFERENCE_ERROR.value: MLEvidenceStatus.INFERENCE_ERROR,
            }
            ev_status = status_map.get(assessment.status, MLEvidenceStatus.INFERENCE_ERROR)

            prediction = None
            if ev_status == MLEvidenceStatus.OK and assessment.prediction:
                p = assessment.prediction
                prediction = {
                    "is_anomaly": bool(p.get("is_anomaly", False)),
                    "anomaly_score": float(p.get("anomaly_score") or p.get("score") or 0.0),
                    "pca_score": p.get("pca_score"),
                    "if_score": p.get("if_score"),
                    "confidence": assessment.confidence,
                }

            return MLEvidence(
                model_name=assessment.model_name,
                model_version=assessment.model_version,
                prediction_type=MLPredictionType.ANOMALY,
                asset_id=asset_id,
                status=ev_status,
                prediction=prediction,
                confidence=assessment.confidence if ev_status == MLEvidenceStatus.OK else None,
                quality=MLEvidenceQuality.GOOD if ev_status == MLEvidenceStatus.OK else MLEvidenceQuality.NOT_AVAILABLE,
                features_used=assessment.features_used or [],
                provenance=assessment.provenance or {},
                source="runtime",
            )
        except Exception as exc:
            logger.error("RealAnomalyModelAdapter.predict failed: %s", exc, exc_info=True)
            return MLEvidence(
                model_name="ProcessAnomalyDetector (real)",
                model_version="unknown",
                prediction_type=MLPredictionType.ANOMALY,
                asset_id=asset_id,
                status=MLEvidenceStatus.INFERENCE_ERROR,
                prediction=None,
                quality=MLEvidenceQuality.NOT_AVAILABLE,
                source="runtime",
                provenance={"error": str(exc)},
            )


class RealFaultModelAdapter:
    """Adapter wrapping the real ProcessFaultClassifier → MLEvidence."""

    def predict(self, telemetry: Dict[str, float], asset_id: str) -> MLEvidence:
        try:
            from backend.ml.inference.pipeline import ml_pipeline
            from backend.models.industrial_domain import MLAssessmentStatus

            assessment = ml_pipeline.run_fault_classification(telemetry)

            status_map = {
                MLAssessmentStatus.OK.value: MLEvidenceStatus.OK,
                MLAssessmentStatus.MODEL_NOT_AVAILABLE.value: MLEvidenceStatus.MODEL_NOT_AVAILABLE,
                MLAssessmentStatus.INVALID_INPUT.value: MLEvidenceStatus.INVALID_INPUT,
                MLAssessmentStatus.INFERENCE_ERROR.value: MLEvidenceStatus.INFERENCE_ERROR,
            }
            ev_status = status_map.get(assessment.status, MLEvidenceStatus.INFERENCE_ERROR)

            prediction = None
            if ev_status == MLEvidenceStatus.OK and assessment.prediction:
                p = assessment.prediction
                prediction = {
                    "predicted_fault": str(p.get("predicted_fault") or p.get("class") or "UNKNOWN"),
                    "confidence": float(assessment.confidence or p.get("confidence") or 0.0),
                    "fault_probabilities": p.get("class_probabilities") or p.get("fault_probabilities") or {},
                    "top_k_faults": p.get("top_k_faults") or [],
                }

            return MLEvidence(
                model_name=assessment.model_name,
                model_version=assessment.model_version,
                prediction_type=MLPredictionType.FAULT_CLASSIFICATION,
                asset_id=asset_id,
                status=ev_status,
                prediction=prediction,
                confidence=assessment.confidence if ev_status == MLEvidenceStatus.OK else None,
                quality=MLEvidenceQuality.GOOD if ev_status == MLEvidenceStatus.OK else MLEvidenceQuality.NOT_AVAILABLE,
                features_used=assessment.features_used or [],
                provenance=assessment.provenance or {},
                source="runtime",
            )
        except Exception as exc:
            logger.error("RealFaultModelAdapter.predict failed: %s", exc, exc_info=True)
            return MLEvidence(
                model_name="ProcessFaultClassifier (real)",
                model_version="unknown",
                prediction_type=MLPredictionType.FAULT_CLASSIFICATION,
                asset_id=asset_id,
                status=MLEvidenceStatus.INFERENCE_ERROR,
                prediction=None,
                quality=MLEvidenceQuality.NOT_AVAILABLE,
                source="runtime",
                provenance={"error": str(exc)},
            )


class RealCOTModelAdapter:
    """Adapter wrapping the real FurnaceCOTPredictor → MLEvidence."""

    def predict(self, telemetry: Dict[str, float], asset_id: str) -> MLEvidence:
        try:
            from backend.ml.inference.pipeline import ml_pipeline
            from backend.models.industrial_domain import MLAssessmentStatus

            assessment = ml_pipeline.run_cot_prediction(telemetry, asset_id=asset_id)

            status_map = {
                MLAssessmentStatus.OK.value: MLEvidenceStatus.OK,
                MLAssessmentStatus.MODEL_NOT_AVAILABLE.value: MLEvidenceStatus.MODEL_NOT_AVAILABLE,
                MLAssessmentStatus.INVALID_INPUT.value: MLEvidenceStatus.INVALID_INPUT,
                MLAssessmentStatus.INFERENCE_ERROR.value: MLEvidenceStatus.INFERENCE_ERROR,
            }
            ev_status = status_map.get(assessment.status, MLEvidenceStatus.INFERENCE_ERROR)

            prediction = None
            if ev_status == MLEvidenceStatus.OK and assessment.prediction:
                p = assessment.prediction
                prediction = {
                    "predicted_cot": float(
                        p.get("predicted_cot_celsius") or p.get("score") or assessment.score or 0.0
                    ),
                    "unit": "celsius",
                    "actual_cot": p.get("actual_cot_celsius"),
                    "residual": p.get("residual_celsius"),
                }

            return MLEvidence(
                model_name=assessment.model_name,
                model_version=assessment.model_version,
                prediction_type=MLPredictionType.COT_PREDICTION,
                asset_id=asset_id,
                status=ev_status,
                prediction=prediction,
                confidence=None,  # COT: regression, no calibrated probability
                units="celsius",
                quality=MLEvidenceQuality.GOOD if ev_status == MLEvidenceStatus.OK else MLEvidenceQuality.NOT_AVAILABLE,
                features_used=assessment.features_used or [],
                provenance=assessment.provenance or {},
                source="runtime",
            )
        except Exception as exc:
            logger.error("RealCOTModelAdapter.predict failed: %s", exc, exc_info=True)
            return MLEvidence(
                model_name="FurnaceCOTPredictor (real)",
                model_version="unknown",
                prediction_type=MLPredictionType.COT_PREDICTION,
                asset_id=asset_id,
                status=MLEvidenceStatus.INFERENCE_ERROR,
                prediction=None,
                units="celsius",
                quality=MLEvidenceQuality.NOT_AVAILABLE,
                source="runtime",
                provenance={"error": str(exc)},
            )


class RealTubeTemperatureModelAdapter:
    """Adapter wrapping the real TubeTemperaturePredictor → MLEvidence."""

    def predict(self, telemetry: Dict[str, float], asset_id: str) -> MLEvidence:
        try:
            from backend.ml.inference.pipeline import ml_pipeline
            from backend.models.industrial_domain import MLAssessmentStatus

            assessment = ml_pipeline.run_tube_temperature(telemetry, asset_id=asset_id)

            status_map = {
                MLAssessmentStatus.OK.value: MLEvidenceStatus.OK,
                MLAssessmentStatus.MODEL_NOT_AVAILABLE.value: MLEvidenceStatus.MODEL_NOT_AVAILABLE,
                MLAssessmentStatus.INVALID_INPUT.value: MLEvidenceStatus.INVALID_INPUT,
                MLAssessmentStatus.INFERENCE_ERROR.value: MLEvidenceStatus.INFERENCE_ERROR,
            }
            ev_status = status_map.get(assessment.status, MLEvidenceStatus.INFERENCE_ERROR)

            prediction = None
            if ev_status == MLEvidenceStatus.OK and assessment.prediction:
                p = assessment.prediction
                prediction = {
                    "predicted_tube_temperature": float(
                        p.get("predicted_tube_temp")
                        or p.get("tube_skin_temperature")
                        or assessment.score
                        or 0.0
                    ),
                    "unit": "celsius",
                    "confidence": assessment.confidence,
                }

            return MLEvidence(
                model_name=assessment.model_name,
                model_version=assessment.model_version,
                prediction_type=MLPredictionType.TUBE_TEMPERATURE,
                asset_id=asset_id,
                status=ev_status,
                prediction=prediction,
                confidence=assessment.confidence if ev_status == MLEvidenceStatus.OK else None,
                units="celsius",
                quality=MLEvidenceQuality.GOOD if ev_status == MLEvidenceStatus.OK else MLEvidenceQuality.NOT_AVAILABLE,
                features_used=assessment.features_used or [],
                provenance=assessment.provenance or {},
                source="runtime",
            )
        except Exception as exc:
            logger.error("RealTubeTemperatureModelAdapter.predict failed: %s", exc, exc_info=True)
            return MLEvidence(
                model_name="TubeTemperaturePredictor (real)",
                model_version="unknown",
                prediction_type=MLPredictionType.TUBE_TEMPERATURE,
                asset_id=asset_id,
                status=MLEvidenceStatus.INFERENCE_ERROR,
                prediction=None,
                units="celsius",
                quality=MLEvidenceQuality.NOT_AVAILABLE,
                source="runtime",
                provenance={"error": str(exc)},
            )


# ---------------------------------------------------------------------------
# MLRuntime Orchestrator
# ---------------------------------------------------------------------------

class MLRuntime:
    """
    ML Runtime Orchestrator — dispatches telemetry to all four model adapters,
    collects canonical MLEvidence records, and handles graceful degradation.

    Instantiation:
      MLRuntime()                          → Uses real model adapters (wraps MLPipeline)
      build_mock_ml_runtime()              → Uses all four mock models
      MLRuntime(anomaly_model=custom)      → Mix real + custom adapters

    Any object satisfying MLModelProtocol can be passed as a model adapter.
    This is the substitution point for Arushi's trained models.
    """

    def __init__(
        self,
        anomaly_model: Optional[Any] = None,
        fault_model: Optional[Any] = None,
        cot_model: Optional[Any] = None,
        tube_temp_model: Optional[Any] = None,
    ) -> None:
        # Default to real model adapters when none provided
        self._anomaly = anomaly_model or RealAnomalyModelAdapter()
        self._fault = fault_model or RealFaultModelAdapter()
        self._cot = cot_model or RealCOTModelAdapter()
        self._tube_temp = tube_temp_model or RealTubeTemperatureModelAdapter()

        self._models = [
            (MLPredictionType.ANOMALY, self._anomaly),
            (MLPredictionType.FAULT_CLASSIFICATION, self._fault),
            (MLPredictionType.COT_PREDICTION, self._cot),
            (MLPredictionType.TUBE_TEMPERATURE, self._tube_temp),
        ]

    def run(
        self,
        asset_id: str,
        telemetry: Dict[str, Any],
    ) -> List[MLEvidence]:
        """
        Run all four ML models against the supplied telemetry.

        Returns a list of up to four MLEvidence records (one per model).
        Individual model failures produce a INFERENCE_ERROR evidence record
        rather than propagating exceptions.

        Args:
            asset_id: Target asset ID (e.g. "F-201A")
            telemetry: Dict of parameter → value (float-castable)

        Returns:
            List[MLEvidence], length = number of models registered
        """
        # Coerce values to float (best effort)
        clean_tel: Dict[str, float] = {}
        for k, v in telemetry.items():
            try:
                clean_tel[str(k)] = float(v)
            except (TypeError, ValueError):
                pass  # Skip non-numeric values silently

        results: List[MLEvidence] = []
        for pred_type, model in self._models:
            try:
                evidence = model.predict(clean_tel, asset_id)
                results.append(evidence)
            except Exception as exc:
                logger.error(
                    "MLRuntime: model %s failed for asset %s: %s",
                    pred_type.value, asset_id, exc, exc_info=True,
                )
                results.append(MLEvidence(
                    model_name=f"Unknown {pred_type.value}",
                    model_version="unknown",
                    prediction_type=pred_type,
                    asset_id=asset_id,
                    status=MLEvidenceStatus.INFERENCE_ERROR,
                    prediction=None,
                    quality=MLEvidenceQuality.NOT_AVAILABLE,
                    source="runtime",
                    provenance={"error": str(exc)},
                ))

        logger.debug(
            "MLRuntime.run: asset=%s, models=%d, successful=%d",
            asset_id,
            len(results),
            sum(1 for e in results if e.is_successful),
        )
        return results

    def run_anomaly(self, asset_id: str, telemetry: Dict[str, Any]) -> MLEvidence:
        """Run only the anomaly model."""
        clean = {str(k): float(v) for k, v in telemetry.items()
                 if _is_numeric(v)}
        return self._anomaly.predict(clean, asset_id)

    def run_fault(self, asset_id: str, telemetry: Dict[str, Any]) -> MLEvidence:
        """Run only the fault classifier."""
        clean = {str(k): float(v) for k, v in telemetry.items()
                 if _is_numeric(v)}
        return self._fault.predict(clean, asset_id)

    def run_cot(self, asset_id: str, telemetry: Dict[str, Any]) -> MLEvidence:
        """Run only the COT predictor."""
        clean = {str(k): float(v) for k, v in telemetry.items()
                 if _is_numeric(v)}
        return self._cot.predict(clean, asset_id)

    def run_tube_temp(self, asset_id: str, telemetry: Dict[str, Any]) -> MLEvidence:
        """Run only the tube temperature predictor."""
        clean = {str(k): float(v) for k, v in telemetry.items()
                 if _is_numeric(v)}
        return self._tube_temp.predict(clean, asset_id)


def _is_numeric(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Module-level singleton (uses real model adapters)
# ---------------------------------------------------------------------------

ml_runtime = MLRuntime()
