"""
ml_training/tep/train_fault_classifier.py — Train & Evaluate XGBoost TEP Fault Classifier.

Trains an authentic 22-class XGBoost multiclass model on the Tennessee Eastman Process benchmark.
- Leakage-safe within-run chronological train/validation splits (75/25) on d00.dat..d21.dat.
- Boundary transition window exclusion (2 windows per fault run, 42 total).
- Independent held-out test evaluation on d00_te.dat..d21_te.dat.
- 156 deterministic features (raw, 3-step mean, delta).
- Serializes production artifact to artifacts/models/process_fault_classifier/v1.0.0/model.joblib.
- Updates artifacts/models/registry.yaml with status: ready.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import yaml
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from ml_training.tep.dataset import (
    CANONICAL_FAULT_FEATURES,
    FAULT_DESCRIPTIONS,
    TEP_DATA_DIR,
    load_tep_multiclass_splits,
)
from ml_training.tep.preprocessor import TEPFaultPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tep.train_fault_classifier")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"
MODEL_DIR = ARTIFACTS_DIR / "process_fault_classifier" / "v1.0.0"
MODEL_FILE = MODEL_DIR / "model.joblib"
EVAL_FILE = ARTIFACTS_DIR / "eval_fault_tep.json"
REGISTRY_FILE = ARTIFACTS_DIR / "registry.yaml"


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def train_and_evaluate() -> Dict[str, Any]:
    logger.info("=== Starting TEP Multiclass Fault Classifier Training ===")
    logger.info("XGBoost version: %s", xgb.__version__)

    # 1. Load Dataset Splits with Transition Window Exclusion
    split_data = load_tep_multiclass_splits(
        data_dir=TEP_DATA_DIR,
        train_ratio=0.75,
        window_size=3,
    )

    X_train = split_data.x_train
    y_train = split_data.y_train
    X_val = split_data.x_val
    y_val = split_data.y_val
    X_test = split_data.x_test
    y_test = split_data.y_test

    logger.info("Dataset shape: Train=%s, Val=%s, Test=%s", X_train.shape, X_val.shape, X_test.shape)
    logger.info("Classes represented: %d (0..21)", len(np.unique(y_train)))

    # 2. Fit Preprocessor strictly on Training Data
    preprocessor = TEPFaultPreprocessor(feature_names=CANONICAL_FAULT_FEATURES, window_size=3)
    preprocessor.fit(X_train)

    X_train_scaled = preprocessor.transform(X_train)
    X_val_scaled = preprocessor.transform(X_val)
    X_test_scaled = preprocessor.transform(X_test)

    # 3. Configure and Train XGBoost Multiclass Classifier
    xgb_params: Dict[str, Any] = {
        "objective": "multi:softprob",
        "num_class": 22,
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.08,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "tree_method": "hist",
        "eval_metric": "mlogloss",
        "n_jobs": 4,
    }

    logger.info("Training XGBoost with parameters: %s", xgb_params)
    clf = xgb.XGBClassifier(**xgb_params)
    clf.fit(
        X_train_scaled,
        y_train,
        eval_set=[(X_val_scaled, y_val)],
        verbose=False,
    )

    # 4. Independent Held-Out Test Evaluation
    logger.info("Evaluating on held-out test data (%d samples)...", len(y_test))
    y_prob = clf.predict_proba(X_test_scaled)
    y_pred = np.argmax(y_prob, axis=1)

    # Top-1 metrics
    acc = float(accuracy_score(y_test, y_pred))
    macro_prec = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
    macro_rec = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    # Top-3 accuracy
    top3_preds = np.argsort(y_prob, axis=1)[:, -3:]
    top3_hits = [y_test[i] in top3_preds[i] for i in range(len(y_test))]
    top3_acc = float(np.mean(top3_hits))

    # Per-class metrics
    per_class_prec = precision_score(y_test, y_pred, average=None, zero_division=0)
    per_class_rec = recall_score(y_test, y_pred, average=None, zero_division=0)
    per_class_f1 = f1_score(y_test, y_pred, average=None, zero_division=0)
    unique_classes, class_counts = np.unique(y_test, return_counts=True)
    support_dict = dict(zip(unique_classes.tolist(), class_counts.tolist()))

    per_class_results: Dict[str, Any] = {}
    for cls_id in range(22):
        desc = FAULT_DESCRIPTIONS.get(cls_id, {})
        per_class_results[str(cls_id)] = {
            "code": desc.get("code", f"CLASS_{cls_id}"),
            "description": desc.get("description", "Unknown"),
            "precision": round(float(per_class_prec[cls_id]), 4),
            "recall": round(float(per_class_rec[cls_id]), 4),
            "f1_score": round(float(per_class_f1[cls_id]), 4),
            "support": int(support_dict.get(cls_id, 0)),
        }

    conf_mat = confusion_matrix(y_test, y_pred).tolist()

    eval_report: Dict[str, Any] = {
        "model_name": "ProcessFaultClassifier (XGBoost Multiclass)",
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "xgboost_version": xgb.__version__,
        "dataset": "Tennessee Eastman Process Benchmark (Downs & Vogel / Braatz)",
        "num_classes": 22,
        "test_samples_total": len(y_test),
        "overall_metrics": {
            "accuracy": round(acc, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "top_3_accuracy": round(top3_acc, 4),
        },
        "per_class_metrics": per_class_results,
        "confusion_matrix": conf_mat,
    }

    logger.info(
        "Evaluation Results: Accuracy=%.4f, Macro-F1=%.4f, Weighted-F1=%.4f, Top-3=%.4f",
        acc,
        macro_f1,
        weighted_f1,
        top3_acc,
    )

    # Save evaluation report
    EVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Saved evaluation report to %s", EVAL_FILE)

    # 5. Serialize Production Artifact
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    artifact_payload: Dict[str, Any] = {
        "preprocessor": preprocessor,
        "xgb_classifier": clf,
        "feature_names": CANONICAL_FAULT_FEATURES,
        "feature_order": CANONICAL_FAULT_FEATURES,
        "class_mapping": FAULT_DESCRIPTIONS,
        "window_config": {
            "window_size": 3,
            "sampling_interval_minutes": 3.0,
            "variables_count": 52,
            "features_count": 156,
            "stride": 1,
            "incomplete_window_handling": "mean=current, delta=0.0",
        },
        "schema_version": "v1.0.0",
        "training_metadata": {
            "trained_timestamp": datetime.now(timezone.utc).isoformat(),
            "xgboost_version": xgb.__version__,
            "random_seed": 42,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "excluded_transition_windows": split_data.metadata["excluded_transition_windows"],
            "metrics": eval_report["overall_metrics"],
        },
    }

    joblib.dump(artifact_payload, MODEL_FILE, compress=3)
    artifact_size = MODEL_FILE.stat().st_size
    artifact_sha256 = compute_file_sha256(MODEL_FILE)
    logger.info("Saved model artifact to %s (size: %d bytes, sha256: %s)", MODEL_FILE, artifact_size, artifact_sha256)

    # 6. Update Model Registry (registry.yaml)
    update_model_registry(artifact_sha256, artifact_size, eval_report)

    return {
        "artifact_path": str(MODEL_FILE),
        "artifact_size": artifact_size,
        "artifact_sha256": artifact_sha256,
        "metrics": eval_report["overall_metrics"],
    }


def update_model_registry(artifact_sha256: str, artifact_size: int, eval_report: Dict[str, Any]) -> None:
    """Update registry.yaml with process_fault_classifier status=ready."""
    if not REGISTRY_FILE.exists():
        logger.warning("registry.yaml not found at %s", REGISTRY_FILE)
        return

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry_data = yaml.safe_load(f)

    if "models" not in registry_data:
        registry_data["models"] = {}

    rel_artifact_path = "artifacts/models/process_fault_classifier/v1.0.0/model.joblib"
    registry_data["models"]["process_fault_classifier"] = {
        "version": "v1.0.0",
        "status": "ready",
        "type": "xgboost_multiclass",
        "framework": "xgboost",
        "framework_version": xgb.__version__,
        "asset_class": "tennessee_eastman_process",
        "description": "Tennessee Eastman Process 22-class XGBoost fault diagnostic classifier.",
        "artifact_path": rel_artifact_path,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "trained_timestamp": datetime.now(timezone.utc).isoformat(),
        "training_dataset": {
            "name": "Tennessee Eastman Process (TEP) Benchmark",
            "source": "Prof. Richard Braatz (UIUC/MIT) / Downs & Vogel (1993)",
            "runs": "d00.dat to d21.dat (training/validation), d00_te.dat to d21_te.dat (independent testing)",
            "classes_count": 22,
            "variables_count": 52,
            "engineered_features_count": 156,
            "window_size": 3,
            "sampling_interval_minutes": 3.0,
            "split": "within-run chronological 75% train / 25% validation; independent test runs",
            "excluded_transition_windows": 42,
        },
        "feature_schema": {
            "version": "v1.0.0",
            "total_features": 156,
            "families": ["raw (52)", "rolling_mean (52)", "temporal_delta (52)"],
            "variables": "xmeas_1..41, xmv_1..11",
        },
        "evaluation_metrics": eval_report["overall_metrics"],
        "class_mapping": {
            k: v["code"] for k, v in FAULT_DESCRIPTIONS.items()
        },
    }

    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        yaml.dump(registry_data, f, sort_keys=False, default_flow_style=False)

    logger.info("Updated model registry at %s: process_fault_classifier -> ready", REGISTRY_FILE)


if __name__ == "__main__":
    train_and_evaluate()
