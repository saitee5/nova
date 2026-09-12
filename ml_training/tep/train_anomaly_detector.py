"""
ml_training/tep/train_anomaly_detector.py — Reproducible TEP Anomaly Detection Training Pipeline.

Trains PCA Statistical Process Monitoring + Isolation Forest on normal TEP operation.
- Training Data: d00.dat 80% chronological split (400 samples)
- Validation / Calibration Data: d00.dat 20% chronological split (100 samples)
- Evaluation Sets: d00_te.dat (normal test) + d01_te.dat to d05_te.dat (fault runs)
- Target Artifact: artifacts/models/process_anomaly_detector/v1.0.0/model.joblib
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from ml_training.tep.dataset import CANONICAL_FEATURES, VERIFIED_HASHES, load_tep_splits
from ml_training.tep.preprocessor import TEPPreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tep.training")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACT_DIR = REPO_ROOT / "artifacts" / "models" / "process_anomaly_detector" / "v1.0.0"
EVAL_ARTIFACT_PATH = REPO_ROOT / "artifacts" / "models" / "eval_anomaly_tep.json"


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_pca_statistics(Z: np.ndarray, pca: PCA) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute Squared Prediction Error (SPE / Q-statistic) and Hotelling's T^2 statistic.
    - Q = ||Z - Z_hat||^2 (residual subspace error)
    - T^2 = sum(t_i^2 / lambda_i) (principal subspace distance)
    """
    T = pca.transform(Z)
    Z_hat = pca.inverse_transform(T)
    Q = np.sum((Z - Z_hat) ** 2, axis=1)
    T2 = np.sum((T ** 2) / pca.explained_variance_, axis=1)
    return Q, T2


def train_tep_anomaly_model(
    random_state: int = 42,
    variance_target: float = 0.90,
    contamination: float = 0.01,
) -> Dict[str, Any]:
    """Execute complete reproducible training, threshold calibration, and evaluation pipeline."""
    logger.info("=== Starting TEP Anomaly Detector Training Pipeline ===")

    # 1. Load Dataset Splits (80/20 chronological split on normal d00.dat)
    splits = load_tep_splits()
    x_train = splits.x_train
    x_val = splits.x_val

    # 2. Fit Preprocessor (StandardScaler fitted strictly on 400 normal training samples)
    preprocessor = TEPPreprocessor(feature_names=CANONICAL_FEATURES)
    preprocessor.fit(x_train)
    Z_train = preprocessor.transform(x_train)
    Z_val = preprocessor.transform(x_val)

    # 3. Fit PCA Component on Z_train
    # Deterministic rule: minimal components to explain >= 90.0% variance
    pca = PCA(n_components=variance_target, svd_solver="full", random_state=random_state)
    pca.fit(Z_train)
    n_components = int(pca.n_components_)
    explained_var = [float(v) for v in pca.explained_variance_ratio_]
    cum_var = float(np.sum(explained_var))
    logger.info("Fitted PCA: %d components explaining %.2f%% variance", n_components, cum_var * 100)

    # 4. Fit Isolation Forest Component on Z_train
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    iso_forest.fit(Z_train)
    logger.info("Fitted Isolation Forest: 100 estimators, contamination=%.3f", contamination)

    # 5. Leakage-Safe Threshold Calibration on Validation Split ONLY
    Q_val, T2_val = compute_pca_statistics(Z_val, pca)
    q_threshold = float(np.percentile(Q_val, 99.0))
    t2_threshold = float(np.percentile(T2_val, 99.0))

    df_val = iso_forest.decision_function(Z_val)
    if_threshold = float(np.percentile(df_val, 1.0))
    df_std = max(1e-4, float(np.std(df_val)))

    logger.info("Frozen Thresholds Calibrated on 100 Normal Validation Samples:")
    logger.info("  PCA Q Threshold (99th pct): %.4f", q_threshold)
    logger.info("  PCA T2 Threshold (99th pct): %.4f", t2_threshold)
    logger.info("  Isolation Forest Threshold (1st pct): %.4f (std=%.4f)", if_threshold, df_std)

    # 6. Evaluation Function for Held-Out Test Sets
    def evaluate_test_set(X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        Z_test = preprocessor.transform(X_test)
        Q, T2 = compute_pca_statistics(Z_test, pca)
        df = iso_forest.decision_function(Z_test)

        # Normalized PCA ratio and calibrated score
        r_pca = np.maximum(Q / q_threshold, T2 / t2_threshold)
        s_pca = 1.0 - np.power(0.5, r_pca)

        # Calibrated Isolation Forest score
        s_if = 1.0 / (1.0 + np.exp(10.0 * (df - if_threshold) / df_std))

        # Combined score
        s_combined = 0.5 * s_pca + 0.5 * s_if
        y_pred = (s_combined >= 0.50).astype(int)

        n_samples = len(y_test)
        n_faults = int(np.sum(y_test))

        res: Dict[str, Any] = {
            "total_samples": n_samples,
            "fault_samples": n_faults,
            "false_positive_rate": float(np.mean(y_pred[y_test == 0])) if np.any(y_test == 0) else 0.0,
        }

        if n_faults > 0:
            res["precision"] = float(precision_score(y_test, y_pred, zero_division=0))
            res["recall"] = float(recall_score(y_test, y_pred, zero_division=0))
            res["f1"] = float(f1_score(y_test, y_pred, zero_division=0))

            # Detection delay (first detection at or after sample 160)
            fault_preds = y_pred[160:]
            detected_indices = np.where(fault_preds == 1)[0]
            if len(detected_indices) > 0:
                first_idx = int(detected_indices[0])
                res["detection_delay_samples"] = first_idx
                res["detection_delay_minutes"] = first_idx * 3.0
            else:
                res["detection_delay_samples"] = -1
                res["detection_delay_minutes"] = -1.0

        return res

    # 7. Evaluate on Held-Out Test Scenarios
    eval_results: Dict[str, Any] = {}
    for scenario_name, (X_te, y_te) in splits.test_sets.items():
        metrics = evaluate_test_set(X_te, y_te)
        eval_results[scenario_name] = metrics
        logger.info("Evaluation on %s: %s", scenario_name, metrics)

    # 8. Assemble Production Model Artifact
    artifact_payload = {
        "model_name": "ProcessAnomalyDetector",
        "version": "v1.0.0",
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
            "formula": "S = 0.5 * (1 - 0.5^(max(Q/Q_th, T2/T2_th))) + 0.5 / (1 + exp(10*(df - df_th)/df_std))",
        },
        "feature_names": CANONICAL_FEATURES,
        "feature_schema_version": "tep_continuous_process_features_v1",
        "training_metadata": {
            "dataset": "Tennessee Eastman Process (TEP) Benchmark",
            "benchmark_origin": "Prof. Richard Braatz / Downs & Vogel (1993)",
            "d00_sha256": VERIFIED_HASHES.get("d00.dat"),
            "train_samples": len(x_train),
            "val_samples": len(x_val),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "random_state": random_state,
        },
    }

    # 9. Serialize Artifact to Disk
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_artifact_path = ARTIFACT_DIR / "model.joblib"
    joblib.dump(artifact_payload, model_artifact_path, compress=3)
    artifact_size = model_artifact_path.stat().st_size
    artifact_hash = compute_file_sha256(model_artifact_path)

    logger.info("Saved model artifact to %s (%d bytes, sha256=%s)", model_artifact_path, artifact_size, artifact_hash)

    # 10. Save Evaluation Report
    eval_report = {
        "model": "ProcessAnomalyDetector",
        "version": "v1.0.0",
        "algorithm": "PCA + Isolation Forest",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "model_artifact_path": str(model_artifact_path.relative_to(REPO_ROOT)),
        "artifact_sha256": artifact_hash,
        "pca": {
            "n_components": n_components,
            "cumulative_explained_variance": cum_var,
            "q_threshold": q_threshold,
            "t2_threshold": t2_threshold,
        },
        "isolation_forest": {
            "n_estimators": 100,
            "threshold": if_threshold,
            "df_std": df_std,
        },
        "scenarios": eval_results,
    }

    EVAL_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVAL_ARTIFACT_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Saved evaluation report to %s", EVAL_ARTIFACT_PATH)

    return {
        "artifact_path": model_artifact_path,
        "artifact_size": artifact_size,
        "artifact_sha256": artifact_hash,
        "n_components": n_components,
        "cum_var": cum_var,
        "q_threshold": q_threshold,
        "t2_threshold": t2_threshold,
        "if_threshold": if_threshold,
        "eval_report": eval_report,
    }


if __name__ == "__main__":
    train_tep_anomaly_model()
