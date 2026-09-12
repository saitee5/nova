"""
ml_training/tep/train_anomaly_detector.py — Reproducible TEP Anomaly Detection Training Pipeline.

Trains PCA Statistical Process Monitoring + Isolation Forest on normal TEP operation from:
data/curated/tep/tep_canonical.csv

Enforces:
1. Curated-only dataset consumption via TrainingGate.
2. Chronological splitting of normal steady-state operation.
3. Calibration of detection thresholds on validation split only.
4. Serializes versioned model artifact and standard evaluation deliverables.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from ml_training.common.metrics import save_evaluation_artifacts
from ml_training.common.training_gate import (
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TrainingGate,
    compute_file_sha256,
)
from ml_training.tep.dataset import (
    CANONICAL_FEATURES,
    CURATED_TEP_PATH,
    TARGET_COLUMN,
    load_tep_splits,
)
from ml_training.tep.preprocessor import TEPPreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nova.ml.tep.train_anomaly")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"


def compute_pca_statistics(Z: np.ndarray, pca: PCA) -> Tuple[np.ndarray, np.ndarray]:
    """Compute Squared Prediction Error (SPE/Q) and Hotelling's T^2 statistic."""
    T = pca.transform(Z)
    Z_hat = pca.inverse_transform(T)
    Q = np.sum((Z - Z_hat) ** 2, axis=1)
    T2 = np.sum((T ** 2) / pca.explained_variance_, axis=1)
    return Q, T2


def train_tep_anomaly_model(
    dataset_path: Path = CURATED_TEP_PATH,
    version: str = "v1.1.0",
    random_state: int = 42,
    variance_target: float = 0.90,
    contamination: float = 0.01,
) -> Dict[str, Any]:
    """Execute complete training, threshold calibration, and evaluation pipeline."""
    logger.info("=== Starting TEP Anomaly Detector Training Pipeline ===")

    # 1. Training Gate
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tep",
    )

    # 2. Load Dataset Splits (80/20 chronological split on normal curated runs)
    splits = load_tep_splits(dataset_path=valid_path)
    x_train = splits.x_train
    x_val = splits.x_val

    # 3. Fit Preprocessor
    preprocessor = TEPPreprocessor(feature_names=CANONICAL_FEATURES)
    preprocessor.fit(x_train)
    Z_train = preprocessor.transform(x_train)
    Z_val = preprocessor.transform(x_val)

    # 4. Fit PCA Component
    pca = PCA(n_components=variance_target, svd_solver="full", random_state=random_state)
    pca.fit(Z_train)
    n_components = int(pca.n_components_)
    explained_var = [float(v) for v in pca.explained_variance_ratio_]
    cum_var = float(np.sum(explained_var))

    # 5. Fit Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    iso_forest.fit(Z_train)

    # 6. Calibrate Thresholds on Validation Data ONLY
    Q_val, T2_val = compute_pca_statistics(Z_val, pca)
    q_threshold = float(np.percentile(Q_val, 99.0))
    t2_threshold = float(np.percentile(T2_val, 99.0))

    df_val = iso_forest.decision_function(Z_val)
    if_threshold = float(np.percentile(df_val, 1.0))
    df_std = max(1e-4, float(np.std(df_val)))

    # 7. Evaluate
    metrics = {
        "pca_n_components": n_components,
        "pca_cumulative_variance": cum_var,
        "pca_q_threshold": q_threshold,
        "pca_t2_threshold": t2_threshold,
        "if_threshold": if_threshold,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
    }

    # 8. Assemble Artifact Payload
    artifact_payload = {
        "model_name": "ProcessAnomalyDetector",
        "version": version,
        "algorithm": "PCA + Isolation Forest",
        "preprocessor": preprocessor,
        "pca": pca,
        "pca_config": {
            "n_components": n_components,
            "explained_variance_ratio": explained_var,
            "cumulative_explained_variance": cum_var,
            "q_threshold": q_threshold,
            "t2_threshold": t2_threshold,
        },
        "isolation_forest": iso_forest,
        "if_config": {
            "n_estimators": 100,
            "contamination": contamination,
            "random_state": random_state,
            "threshold": if_threshold,
            "df_std": df_std,
        },
        "scoring": {
            "combined_threshold": 0.50,
            "pca_weight": 0.50,
            "if_weight": 0.50,
        },
        "feature_names": CANONICAL_FEATURES,
        "feature_schema_version": "tep_continuous_process_features_v1",
        "training_metadata": {
            "dataset_path": str(valid_path),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "random_state": random_state,
        },
    }

    # 9. Save Versioned Model Artifact
    model_dir = ARTIFACTS_DIR / "process_anomaly_detector" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.joblib"
    joblib.dump(artifact_payload, model_file, compress=3)

    # 10. Save Evaluation Deliverables
    save_evaluation_artifacts(
        model_name="ProcessAnomalyDetector",
        version=version,
        metrics=metrics,
        training_metadata=artifact_payload["training_metadata"],
    )

    logger.info("ProcessAnomalyDetector training complete. Saved to %s", model_file)
    return {
        "metrics": metrics,
        "artifact_path": str(model_file),
    }


if __name__ == "__main__":
    train_tep_anomaly_model()
