"""
backend/ml/fault/classifier.py — Process Fault Diagnosis Interface Contract.

Model: XGBoost Multiclass Classifier
Dataset target: Tennessee Eastman Process (TEP) labeled fault scenarios (Faults 1 to 21).
"""
from __future__ import annotations

import logging
import logging
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus

logger = logging.getLogger("nova.ml.fault")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class BaseFaultClassifier(ABC):
    """Abstract Base Class for Process Fault Diagnosis."""

    @abstractmethod
    def classify_fault(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        """Classify fault type and return MLAssessment."""
        pass


class ProcessFaultClassifier(BaseFaultClassifier):
    """
    Production Process Fault Classifier implementation.
    Loads offline-trained XGBoost 22-class model.joblib artifact on Tennessee Eastman Process.
    Returns MODEL_NOT_AVAILABLE when model artifacts/weights are absent.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = model_path
        self.meta = model_registry.get_model_metadata("process_fault_classifier")
        self.version = self.meta.version if self.meta else "v1.0.0"
        self.resolved_artifact_path: Optional[Path] = None
        self.is_loaded: bool = False

        # Component models and configuration
        self.preprocessor: Any = None
        self.xgb_classifier: Any = None
        self.feature_names: List[str] = []
        self.class_mapping: Dict[int, Dict[str, str]] = {}
        self.window_config: Dict[str, Any] = {}
        self.schema_version: str = "v1.0.0"

        # Operational stream isolation for sequential inference
        self._stream_buffers: Dict[str, deque] = {}

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
            std_path = REPO_ROOT / "artifacts" / "models" / "process_fault_classifier" / "v1.0.0" / "model.joblib"
            if std_path.exists():
                candidate_path = std_path

        if candidate_path and candidate_path.exists():
            try:
                payload = joblib.load(candidate_path)
                self.preprocessor = payload["preprocessor"]
                self.xgb_classifier = payload["xgb_classifier"]
                self.feature_names = payload.get("feature_names", [])
                self.class_mapping = payload.get("class_mapping", {})
                self.window_config = payload.get("window_config", {})
                self.schema_version = payload.get("schema_version", "v1.0.0")
                self.resolved_artifact_path = candidate_path
                self.is_loaded = True
                logger.info(
                    "Loaded ProcessFaultClassifier artifact from %s (classes=%d, features=%d)",
                    candidate_path,
                    len(self.class_mapping),
                    len(self.feature_names),
                )
            except Exception as exc:
                logger.warning("Failed to load fault classifier artifact from %s: %s", candidate_path, exc)
                self.is_loaded = False
        else:
            self.is_loaded = False
            logger.info("ProcessFaultClassifier artifact not available (candidate: %s)", candidate_path)

    def reset_stream(self, stream_id: Optional[str] = None) -> None:
        """Reset history buffer for a given operational stream, or all streams if None."""
        if stream_id:
            if stream_id in self._stream_buffers:
                self._stream_buffers[stream_id].clear()
        else:
            self._stream_buffers.clear()

    def classify_fault(self, telemetry_vector: Dict[str, float]) -> MLAssessment:
        """
        Classify multi-variate process telemetry into one of 22 TEP fault states.
        Returns validated MLAssessment with status OK, MODEL_NOT_AVAILABLE, or INVALID_INPUT.
        """
        if telemetry_vector is None or not isinstance(telemetry_vector, dict) or len(telemetry_vector) == 0:
            return MLAssessment(
                model_name="ProcessFaultClassifier (XGBoost Multiclass)",
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
                model_name="ProcessFaultClassifier (XGBoost Multiclass)",
                model_version=self.version,
                status=MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(telemetry_vector.keys()),
                provenance={"dataset": "TEP (22 Classes)", "status": "Artifact not yet installed in registry."},
            )

        try:
            # Stream isolation: derive stream identifier to avoid cross-stream buffer contamination
            stream_id = str(
                telemetry_vector.get("stream_id")
                or telemetry_vector.get("asset_id")
                or "default"
            )

            if stream_id not in self._stream_buffers:
                window_size = self.window_config.get("window_size", 3)
                self._stream_buffers[stream_id] = deque(maxlen=window_size)

            stream_buf = self._stream_buffers[stream_id]

            # Preprocess and extract 156-feature window
            X_scaled = self.preprocessor.transform(telemetry_vector, history_buffer=list(stream_buf))

            # Push current telemetry to stream history
            stream_buf.append(telemetry_vector)

            # XGBoost Softmax / Probability Distribution
            probs = self.xgb_classifier.predict_proba(X_scaled)[0]

            # Determine top-1 prediction
            top1_idx = int(np.argmax(probs))
            top1_prob = float(probs[top1_idx])

            # Class metadata lookup
            cls_meta = self.class_mapping.get(top1_idx, {})
            fault_code = cls_meta.get("code", f"CLASS_{top1_idx}")
            fault_desc = cls_meta.get("description", "Unknown Fault State")

            # Determine Top-3 candidate faults
            sorted_indices = np.argsort(probs)[::-1]
            top_candidates = []
            for rank_idx in sorted_indices[:3]:
                idx_int = int(rank_idx)
                cand_meta = self.class_mapping.get(idx_int, {})
                top_candidates.append({
                    "class_id": idx_int,
                    "code": cand_meta.get("code", f"CLASS_{idx_int}"),
                    "description": cand_meta.get("description", "Unknown"),
                    "confidence": round(float(probs[idx_int]), 4),
                })

            prediction_payload = {
                "fault_id": top1_idx,
                "fault_code": fault_code,
                "description": fault_desc,
                "confidence": round(top1_prob, 4),
                "top_candidates": top_candidates,
                "probability_distribution": {
                    self.class_mapping.get(i, {}).get("code", str(i)): round(float(probs[i]), 4)
                    for i in range(len(probs))
                },
            }

            return MLAssessment(
                model_name="ProcessFaultClassifier (XGBoost Multiclass)",
                model_version=self.version,
                status=MLAssessmentStatus.OK.value,
                prediction=prediction_payload,
                score=top1_prob,
                confidence=top1_prob,
                labels=[fault_code],
                features_used=self.feature_names,
                provenance={
                    "dataset": "TEP (Downs & Vogel / Braatz)",
                    "artifact": str(self.resolved_artifact_path),
                    "schema_version": self.schema_version,
                    "stream_id": stream_id,
                },
            )

        except Exception as exc:
            logger.error("Inference failed in ProcessFaultClassifier: %s", exc, exc_info=True)
            return MLAssessment(
                model_name="ProcessFaultClassifier (XGBoost Multiclass)",
                model_version=self.version,
                status=MLAssessmentStatus.INFERENCE_ERROR.value,
                prediction=None,
                score=None,
                confidence=None,
                features_used=list(telemetry_vector.keys()),
                provenance={"error": str(exc)},
            )

