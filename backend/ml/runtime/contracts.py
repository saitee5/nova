"""
backend/ml/runtime/contracts.py — Canonical ML Evidence Contracts.

Defines the single typed representation that ALL ML model outputs are
normalized into before entering the intelligence pipeline (Context, Risk,
Episode, Agents).

Design principle:
  Different ML models → Different raw outputs
              ↓
  MLEvidence  (one canonical representation)
              ↓
  Intelligence layer (model-agnostic)

Field rules:
  - prediction is None when status != OK
  - confidence is None when the model does not produce calibrated probabilities
  - units is None when the output is dimensionless
  - Never substitute zero for None when a model is unavailable
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Status / Quality Enumerations
# ---------------------------------------------------------------------------

class MLEvidenceStatus(str, Enum):
    """Inference outcome status — propagated from raw MLAssessment.status."""
    OK = "OK"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    INVALID_INPUT = "INVALID_INPUT"
    INFERENCE_ERROR = "INFERENCE_ERROR"


class MLEvidenceQuality(str, Enum):
    """Data quality of the ML evidence."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class MLPredictionType(str, Enum):
    """Categorical type of ML prediction for downstream routing."""
    ANOMALY = "anomaly"
    FAULT_CLASSIFICATION = "fault_classification"
    COT_PREDICTION = "cot_prediction"
    TUBE_TEMPERATURE = "tube_temperature"


# ---------------------------------------------------------------------------
# Model-specific typed payloads
# ---------------------------------------------------------------------------

class AnomalyPayload(BaseModel):
    """
    Typed output payload for the Process Anomaly Detector.
    Fields only present when status == OK.
    """
    is_anomaly: bool
    anomaly_score: float = Field(ge=0.0, le=1.0, description="Composite anomaly score [0,1]")
    pca_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    if_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class FaultPayload(BaseModel):
    """
    Typed output payload for the Process Fault Classifier.
    Fields only present when status == OK.
    """
    predicted_fault: str = Field(description="Top-1 predicted fault label")
    confidence: float = Field(ge=0.0, le=1.0)
    fault_probabilities: Dict[str, float] = Field(default_factory=dict)
    top_k_faults: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {fault, probability} for top-K predictions",
    )


class COTPredictionPayload(BaseModel):
    """
    Typed output for the Furnace Coil Outlet Temperature (COT) Predictor.
    Fields only present when status == OK.
    """
    predicted_cot: float = Field(description="Predicted COT value")
    unit: str = Field(default="celsius")
    actual_cot: Optional[float] = Field(None, description="Actual COT if supplied in telemetry")
    residual: Optional[float] = Field(None, description="actual - predicted (if actual available)")


class TubeTemperaturePayload(BaseModel):
    """
    Typed output for the Tube Temperature Soft Sensor.
    Fields only present when status == OK.

    NOTE: coking_index is deliberately excluded unless Arushi trains a validated
    coking target. Tube temperature is a temperature-only soft sensor.
    """
    predicted_tube_temperature: float = Field(description="Predicted tube skin temperature")
    unit: str = Field(default="celsius")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Canonical MLEvidence
# ---------------------------------------------------------------------------

class MLEvidence(BaseModel):
    """
    Canonical ML evidence record consumed by the intelligence pipeline.

    All four ML model outputs are normalized into this single type.
    The intelligence layer (Context, Risk, Episode, Agents) depends only
    on MLEvidence, not on model-specific internal structures.

    When status != OK:
      - prediction is None
      - confidence is None
      - quality is NOT_AVAILABLE or BAD

    Never substitute zero or placeholder values for missing predictions.
    """
    model_config = {"arbitrary_types_allowed": True}

    # Identity
    model_name: str
    model_version: str
    prediction_type: MLPredictionType

    # Target
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Outcome
    status: MLEvidenceStatus
    prediction: Optional[Dict[str, Any]] = None   # None when not OK
    confidence: Optional[float] = None             # None when not calibrated

    # Metadata
    units: Optional[str] = None
    quality: MLEvidenceQuality = MLEvidenceQuality.GOOD
    features_used: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    source: str = "runtime"   # "runtime" | "mock" | "offline"

    @property
    def is_successful(self) -> bool:
        """True only when inference completed without error."""
        return self.status == MLEvidenceStatus.OK

    @property
    def anomaly_score(self) -> Optional[float]:
        """Convenience accessor for anomaly score."""
        if self.prediction_type == MLPredictionType.ANOMALY and self.prediction:
            return self.prediction.get("anomaly_score")
        return None

    @property
    def is_anomaly(self) -> Optional[bool]:
        """Convenience accessor for anomaly flag."""
        if self.prediction_type == MLPredictionType.ANOMALY and self.prediction:
            return self.prediction.get("is_anomaly")
        return None

    @property
    def predicted_fault(self) -> Optional[str]:
        """Convenience accessor for predicted fault label."""
        if self.prediction_type == MLPredictionType.FAULT_CLASSIFICATION and self.prediction:
            return self.prediction.get("predicted_fault")
        return None

    @property
    def predicted_cot(self) -> Optional[float]:
        """Convenience accessor for predicted COT."""
        if self.prediction_type == MLPredictionType.COT_PREDICTION and self.prediction:
            return self.prediction.get("predicted_cot")
        return None

    @property
    def predicted_tube_temperature(self) -> Optional[float]:
        """Convenience accessor for predicted tube temperature."""
        if self.prediction_type == MLPredictionType.TUBE_TEMPERATURE and self.prediction:
            return self.prediction.get("predicted_tube_temperature")
        return None
