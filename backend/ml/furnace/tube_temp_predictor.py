"""
backend/ml/furnace/tube_temp_predictor.py — Furnace Tube-Temperature Soft Sensor Contract.

Approach:
- XGBoost Regression (statistical surrogate for synthetic TMT target)
- Fitted preprocessor (StandardScaler on 17 process features)

Target Provenance:
- target_type: "physics-informed synthetic"
- This is NOT measured industrial plant TMT.
- This is NOT a coking detector.
- This does NOT claim industrial validation.

Dataset target: Industrial Cracking-Furnace Soft-Sensor Dataset.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus

logger = logging.getLogger("nova.ml.furnace.tube_temp")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class BaseTubeTemperaturePredictor(ABC):
    @abstractmethod
    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        pass


class TubeTemperaturePredictor(BaseTubeTemperaturePredictor):
    """
    Furnace Tube Temperature Soft Sensor contract.
    Loads XGBoost regression model trained on physics-informed synthetic TMT target.
    Returns MODEL_NOT_AVAILABLE when weights/artifacts are missing or pending validation.
    Guarantees zero hard-coded temperature stub emissions.
    """

    MODEL_DISPLAY_NAME = "TubeTemperaturePredictor (XGBoost Synthetic Surrogate)"

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.meta = model_registry.get_model_metadata("tube_temperature_predictor")
        self.version = self.meta.version if self.meta else "v1.1.0"
        self._model: Any = None
        self._preprocessor: Any = None
        self._feature_names: list = []
        self._target_type: str = "physics-informed synthetic"
        self.is_loaded: bool = False
        self._load_artifact()

    def _load_artifact(self) -> None:
        """Attempt to load trained tube temperature artifact if available on disk."""
        candidate_path: Optional[Path] = None
        if self.model_path:
            p = Path(self.model_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p
        elif self.meta and self.meta.status not in ("not_trained", "placeholder"):
            p = Path(self.meta.artifact_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p

        if candidate_path and candidate_path.exists():
            try:
                import joblib
                payload = joblib.load(candidate_path)
                self._model = payload.get("model") or payload.get("xgb_regressor")
                self._preprocessor = payload.get("preprocessor")
                self._feature_names = payload.get("feature_names", [])
                self._target_type = payload.get("target_type", "physics-informed synthetic")
                self.is_loaded = (self._model is not None)
                if self.is_loaded:
                    logger.info("Loaded TubeTemperaturePredictor from %s", candidate_path)
            except Exception as exc:
                logger.warning("Failed to load tube temperature artifact from %s: %s", candidate_path, exc)
                self.is_loaded = False
        else:
            self.is_loaded = False

    def predict_tube_temperature(self, soft_sensor_inputs: Dict[str, float]) -> MLAssessment:
        if soft_sensor_inputs is None or not isinstance(soft_sensor_inputs, dict) or len(soft_sensor_inputs) == 0:
            return MLAssessment(
                model_name=self.MODEL_DISPLAY_NAME,
                model_version=self.version,
                status=MLAssessmentStatus.INVALID_INPUT.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=[],
                provenance={
                    "dataset": "TubeSkinDataset",
                    "target_type": self._target_type,
                    "reason": "Invalid or empty soft sensor input provided.",
                },
            )

        if not self.is_loaded or self._model is None:
            return MLAssessment(
                model_name=self.MODEL_DISPLAY_NAME,
                model_version=self.version,
                status=MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(soft_sensor_inputs.keys()),
                provenance={
                    "dataset": "TubeSkinDataset",
                    "target_type": self._target_type,
                    "status": "Artifact not available or pending target validation.",
                },
            )

        try:
            # When model artifact exists, execute inference through fitted preprocessor and model
            if self._preprocessor is not None and hasattr(self._preprocessor, "transform"):
                X = self._preprocessor.transform(soft_sensor_inputs)
            else:
                X = [list(soft_sensor_inputs.values())]

            pred_val = float(self._model.predict(X)[0])
            return MLAssessment(
                model_name=self.MODEL_DISPLAY_NAME,
                model_version=self.version,
                status=MLAssessmentStatus.OK.value,
                prediction={"predicted_tmt_celsius": round(pred_val, 2)},
                score=round(pred_val, 2),
                confidence=None,
                features_used=self._feature_names if self._feature_names else list(soft_sensor_inputs.keys()),
                provenance={
                    "dataset": "TubeSkinDataset",
                    "target_type": self._target_type,
                    "artifact": str(self.model_path),
                    "disclaimer": (
                        "Predicted TMT is based on a physics-informed SYNTHETIC target. "
                        "NOT measured industrial plant TMT. NOT a coking detector."
                    ),
                },
            )
        except Exception as exc:
            logger.error("Inference failed in TubeTemperaturePredictor: %s", exc)
            return MLAssessment(
                model_name=self.MODEL_DISPLAY_NAME,
                model_version=self.version,
                status=MLAssessmentStatus.INFERENCE_ERROR.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(soft_sensor_inputs.keys()),
                provenance={"error": str(exc)},
            )
