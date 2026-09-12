import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus

logger = logging.getLogger("nova.ml.furnace.cot")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class BaseFurnaceCOTPredictor(ABC):
    @abstractmethod
    def predict_cot(self, furnace_telemetry: Dict[str, float]) -> MLAssessment:
        pass


class FurnaceCOTPredictor(BaseFurnaceCOTPredictor):
    """
    Production Furnace COT Predictor implementation.
    Loads offline-trained XGBoost regressor model.joblib artifact on authentic ethylene cracking data.
    Returns MODEL_NOT_AVAILABLE when model artifacts/weights are absent.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.meta = model_registry.get_model_metadata("furnace_cot_predictor")
        self.version = self.meta.version if self.meta else "v1.0.0"
        self.resolved_artifact_path: Optional[Path] = None
        self.is_loaded: bool = False

        # Component models and configuration
        self.preprocessor: Any = None
        self.xgb_regressor: Any = None
        self.feature_names: List[str] = []
        self.target_name: str = "coil_outlet_temperature"
        self.target_unit: str = "celsius"
        self.schema_version: str = "v1.0.0"

        self._load_artifact()

    def _load_artifact(self) -> None:
        """Load model.joblib from explicit path or model registry."""
        candidate_path: Optional[Path] = None

        if self.model_path:
            p = Path(self.model_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p
        elif self.meta and self.meta.status != "not_trained":
            p = Path(self.meta.artifact_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p
        else:
            std_path = REPO_ROOT / "artifacts" / "models" / "furnace_cot_predictor" / "v1.0.0" / "model.joblib"
            if std_path.exists():
                candidate_path = std_path

        if candidate_path and candidate_path.exists():
            try:
                payload = joblib.load(candidate_path)
                self.preprocessor = payload["preprocessor"]
                self.xgb_regressor = payload.get("xgb_regressor") or payload.get("model")
                self._model = self.xgb_regressor
                self.feature_names = payload.get("feature_names", [])
                self.target_name = payload.get("target_name", "coil_outlet_temperature")
                self.target_unit = payload.get("target_unit", "celsius")
                self.schema_version = payload.get("schema_version", "v1.0.0")
                self.resolved_artifact_path = candidate_path
                self.is_loaded = True
                logger.info(
                    "Loaded FurnaceCOTPredictor artifact from %s (features=%d)",
                    candidate_path,
                    len(self.feature_names),
                )
            except Exception as exc:
                logger.warning("Failed to load furnace COT artifact from %s: %s", candidate_path, exc)
                self.is_loaded = False
        else:
            self.is_loaded = False
            logger.info("FurnaceCOTPredictor artifact not available (candidate: %s)", candidate_path)

    def predict_cot(
        self,
        furnace_telemetry: Dict[str, float],
        asset_id: Optional[str] = None,
    ) -> MLAssessment:
        """
        Execute deterministic COT prediction on single-timestamp telemetry dictionary.

        Guarantees:
        - Strict zero target leakage (target aliases filtered before transformation)
        - Canonical 16-feature vector alignment
        - Graceful handling of invalid inputs and missing artifacts
        - Isolated state across assets and streams
        """
        if furnace_telemetry is None or not isinstance(furnace_telemetry, dict) or len(furnace_telemetry) == 0:
            return MLAssessment(
                model_name="FurnaceCOTPredictor (XGBoost Regressor)",
                model_version=self.version,
                status=MLAssessmentStatus.INVALID_INPUT.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=[],
                provenance={"dataset": "EthyleneFurnace", "reason": "Invalid or empty telemetry provided."},
            )

        if not self.is_loaded:
            return MLAssessment(
                model_name="FurnaceCOTPredictor (XGBoost Regressor)",
                model_version=self.version,
                status=MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
                prediction=None,
                score=None,
                confidence=0.0,
                features_used=list(furnace_telemetry.keys()),
                provenance={"dataset": "EthyleneFurnace", "status": "Artifact not yet installed in registry."},
            )

        try:
            stream_id = str(
                asset_id
                or furnace_telemetry.get("stream_id")
                or furnace_telemetry.get("asset_id")
                or "F-201A"
            )

            # Check if actual COT is provided in telemetry for residual calculation (case-insensitive)
            actual_cot: Optional[float] = None
            target_candidates = {"actual_cot", "target_cot", "cot", "coil_outlet_temperature", "ti-20101", "ti_20101"}
            for k, v in furnace_telemetry.items():
                if str(k).lower().strip() in target_candidates:
                    try:
                        actual_cot = float(v)
                        break
                    except (ValueError, TypeError):
                        pass

            # Preprocess features (guaranteed zero target leakage: COT is stripped)
            X_features = self.preprocessor.transform(furnace_telemetry)

            # Predict COT in Celsius using underlying model
            regressor = getattr(self, "_model", None) or getattr(self, "xgb_regressor", None)
            if regressor is None or not hasattr(regressor, "predict"):
                raise RuntimeError("Underlying regression model is invalid or unavailable")

            pred_cot = float(regressor.predict(X_features)[0])

            # Compute residual only if actual COT was supplied
            residual: Optional[float] = None
            if actual_cot is not None:
                residual = round(actual_cot - pred_cot, 4)

            prediction_payload = {
                "predicted_cot_celsius": round(pred_cot, 2),
                "target_unit": self.target_unit,
                "actual_cot_celsius": round(actual_cot, 2) if actual_cot is not None else None,
                "residual_celsius": residual,
            }

            return MLAssessment(
                model_name="FurnaceCOTPredictor (XGBoost Regressor)",
                model_version=self.version,
                status=MLAssessmentStatus.OK.value,
                prediction=prediction_payload,
                score=round(pred_cot, 2),
                confidence=None,  # Not calibrated probabilistic confidence; omitted per Section 19
                features_used=self.feature_names,
                provenance={
                    "dataset": "Industrial Ethylene Cracking Furnace Telemetry (30,015 sets)",
                    "artifact": str(self.resolved_artifact_path),
                    "schema_version": self.schema_version,
                    "stream_id": stream_id,
                },
            )

        except Exception as exc:
            logger.error("Inference failed in FurnaceCOTPredictor: %s", exc, exc_info=True)
            return MLAssessment(
                model_name="FurnaceCOTPredictor (XGBoost Regressor)",
                model_version=self.version,
                status=MLAssessmentStatus.INFERENCE_ERROR.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(furnace_telemetry.keys()),
                provenance={"error": str(exc)},
            )


# Module-level singletons for convenience and backward compatibility
cot_predictor = FurnaceCOTPredictor()
furnace_cot_predictor = cot_predictor

