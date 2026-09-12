"""
backend/ml/anomaly/detector.py — Process Anomaly Detection Production Interface.

Methods:
- PCA (Principal Component Analysis with Hotelling's T^2 and SPE / Q-statistic)
- Isolation Forest
- Combined explainable anomaly score and 3-tier status (NORMAL, UNCERTAIN, ANOMALOUS)

Dataset: Tennessee Eastman Process (TEP) canonical curated benchmark.
Artifact: artifacts/models/process_anomaly_detector/v1.1.0/model.joblib
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np

from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus

logger = logging.getLogger("nova.ml.anomaly")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class BaseAnomalyDetector(ABC):
    """Abstract Base Class for Process Anomaly Detection."""

    @abstractmethod
    def detect_anomaly(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        """Evaluate input vector and return MLAssessment."""
        pass


class ProcessAnomalyDetector(BaseAnomalyDetector):
    """
    Production Process Anomaly Detector implementation.
    Loads offline-trained PCA + Isolation Forest model.joblib artifact.
    Returns MODEL_NOT_AVAILABLE when model artifacts/weights are absent.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.meta = model_registry.get_model_metadata("process_anomaly_detector")
        self.version = self.meta.version if self.meta else "v1.1.0"
        self.resolved_artifact_path: Optional[Path] = None
        self.is_loaded: bool = False

        # Component models and configurations
        self.preprocessor: Any = None
        self.pca: Any = None
        self.pca_config: Dict[str, Any] = {}
        self.isolation_forest: Any = None
        self.if_config: Dict[str, Any] = {}
        self.scoring: Dict[str, Any] = {}
        self.feature_names: List[str] = []

        self._load_artifact()

    def _load_artifact(self) -> None:
        """Load model.joblib from explicit path, model registry, or latest standard path."""
        candidate_path: Optional[Path] = None

        if self.model_path:
            p = Path(self.model_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p
        elif self.meta and self.meta.status not in ("not_trained", "placeholder"):
            p = Path(self.meta.artifact_path)
            candidate_path = p if p.is_absolute() else REPO_ROOT / p
        else:
            # Check v1.1.0 first, then v1.0.0
            v1_1 = REPO_ROOT / "artifacts" / "models" / "process_anomaly_detector" / "v1.1.0" / "model.joblib"
            v1_0 = REPO_ROOT / "artifacts" / "models" / "process_anomaly_detector" / "v1.0.0" / "model.joblib"
            if v1_1.exists():
                candidate_path = v1_1
            elif v1_0.exists():
                candidate_path = v1_0

        if candidate_path and candidate_path.exists():
            try:
                payload = joblib.load(candidate_path)
                self.preprocessor = payload["preprocessor"]
                self.pca = payload["pca"]
                self.pca_config = payload.get("pca_config", {})
                self.isolation_forest = payload["isolation_forest"]
                self.if_config = payload.get("if_config", {})
                self.scoring = payload.get("scoring", {})
                self.feature_names = payload.get("feature_names", [])
                self.version = payload.get("version", self.version)
                self.resolved_artifact_path = candidate_path
                self.is_loaded = True
                logger.info(
                    "Loaded ProcessAnomalyDetector artifact from %s (version=%s)",
                    candidate_path,
                    self.version,
                )
            except Exception as exc:
                logger.warning("Failed to load anomaly artifact from %s: %s", candidate_path, exc)
                self.is_loaded = False
        else:
            self.is_loaded = False
            logger.info("ProcessAnomalyDetector artifact not available (candidate: %s)", candidate_path)

    def detect_anomaly(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        """
        Evaluate multivariate telemetry against PCA and Isolation Forest.
        Returns validated MLAssessment with status OK, MODEL_NOT_AVAILABLE, or INVALID_INPUT.
        Produces anomaly_score, anomaly_status (NORMAL, UNCERTAIN, ANOMALOUS), and confidence.
        """
        if telemetry_vector is None or not isinstance(telemetry_vector, dict) or len(telemetry_vector) == 0:
            return MLAssessment(
                model_name="ProcessAnomalyDetector (PCA + IsolationForest)",
                model_version=self.version,
                status=MLAssessmentStatus.INVALID_INPUT.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=[],
                provenance={"dataset": "TEP", "reason": "Invalid or empty telemetry vector provided."},
            )

        if not self.is_loaded:
            return MLAssessment(
                model_name="ProcessAnomalyDetector (PCA + IsolationForest)",
                model_version=self.version,
                status=MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(telemetry_vector.keys()),
                provenance={"dataset": "TEP", "status": "Artifact not yet installed in registry."},
            )

        try:
            asset_id = telemetry_vector.get("asset_id") or telemetry_vector.get("plant_id")
            sample_ref = telemetry_vector.get("sample_index") or telemetry_vector.get("timestamp")

            # Transform telemetry vector via preprocessor
            Z = self.preprocessor.transform(telemetry_vector)

            # 1. PCA Subspace Monitoring (SPE / Q and Hotelling's T^2)
            T = self.pca.transform(Z)
            Z_hat = self.pca.inverse_transform(T)
            Q = float(np.sum((Z - Z_hat) ** 2, axis=1)[0])
            T2 = float(np.sum((T ** 2) / np.maximum(1e-9, self.pca.explained_variance_), axis=1)[0])

            q_th = max(1e-6, float(self.pca_config.get("q_threshold", 17.5129)))
            t2_th = max(1e-6, float(self.pca_config.get("t2_threshold", 51.5462)))

            # Normalized PCA violation ratio
            r_pca = max(Q / q_th, T2 / t2_th)
            # Calibrated monotonic mapping to [0, 1] where r_pca = 1.0 -> 0.50
            s_pca = float(1.0 - np.power(0.5, r_pca))

            # 2. Isolation Forest Outlier Scoring
            df = float(self.isolation_forest.decision_function(Z)[0])
            if_th = float(self.if_config.get("threshold", -0.0186))
            df_std = max(1e-4, float(self.if_config.get("df_std", 0.0273)))

            # Logistic sigmoid calibration mapping threshold to 0.50
            s_if = float(1.0 / (1.0 + np.exp(10.0 * (df - if_th) / df_std)))

            # 3. Combined Explainable Score
            w_pca = float(self.scoring.get("pca_weight", 0.50))
            w_if = float(self.scoring.get("if_weight", 0.50))
            s_combined = float(w_pca * s_pca + w_if * s_if)

            comb_th = float(self.scoring.get("combined_threshold", 0.50))
            uncertain_lower = float(self.scoring.get("uncertain_lower_threshold", 0.40))
            uncertain_upper = float(self.scoring.get("uncertain_upper_threshold", 0.60))

            # Determine 3-tier status
            if s_combined < uncertain_lower:
                anomaly_status = "NORMAL"
                is_anomaly = False
            elif s_combined >= uncertain_upper:
                anomaly_status = "ANOMALOUS"
                is_anomaly = True
            else:
                anomaly_status = "UNCERTAIN"
                is_anomaly = bool(s_combined >= comb_th)

            # Calibrated confidence based on margin from uncertainty region
            if anomaly_status == "NORMAL":
                conf = 0.50 + 0.50 * ((uncertain_lower - s_combined) / max(1e-4, uncertain_lower))
            elif anomaly_status == "ANOMALOUS":
                conf = 0.50 + 0.50 * ((s_combined - uncertain_upper) / max(1e-4, 1.0 - uncertain_upper))
            else:
                conf = 0.50  # Ambiguous boundary zone

            confidence = round(float(min(1.0, max(0.50, conf))), 4)

            prediction_dict = {
                "anomaly_status": anomaly_status,
                "anomaly_score": round(s_combined, 4),
                "is_anomaly": is_anomaly,
                "pca_q": round(Q, 4),
                "pca_t2": round(T2, 4),
                "pca_score": round(s_pca, 4),
                "if_score": round(s_if, 4),
                "combined_score": round(s_combined, 4),
                "sample_reference": sample_ref,
                "asset_id": asset_id,
                "model_version": self.version,
            }

            return MLAssessment(
                model_name="ProcessAnomalyDetector (PCA + IsolationForest)",
                model_version=self.version,
                status=MLAssessmentStatus.OK.value,
                prediction=prediction_dict,
                score=round(s_combined, 4),
                confidence=confidence,
                features_used=self.feature_names,
                provenance={
                    "dataset": "Tennessee Eastman Process (TEP) Canonical Dataset",
                    "algorithm": "PCA + Isolation Forest",
                    "artifact": str(self.resolved_artifact_path.relative_to(REPO_ROOT)) if self.resolved_artifact_path else "in_memory",
                    "n_components": int(self.pca_config.get("n_components", 31)),
                },
            )
        except Exception as exc:
            logger.error("Inference failed in ProcessAnomalyDetector: %s", exc)
            return MLAssessment(
                model_name="ProcessAnomalyDetector (PCA + IsolationForest)",
                model_version=self.version,
                status=MLAssessmentStatus.INFERENCE_ERROR.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(telemetry_vector.keys()),
                provenance={"error": str(exc)},
            )
