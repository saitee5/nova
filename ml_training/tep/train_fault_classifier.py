"""
ml_training/tep/train_fault_classifier.py — Train & Evaluate XGBoost TEP Fault Classifier.

Trains a 21-class XGBoost multiclass model on the canonical Tennessee Eastman Process dataset:
data/curated/tep/tep_canonical.csv

Enforces:
1. Curated-only dataset consumption via TrainingGate.
2. Leakage-safe within-run chronological train/validation splits.
3. Boundary transition window exclusion (2 windows per fault run at t=20, 21).
4. 156 deterministic features (raw, 3-step mean, delta).
5. Serializes versioned model artifact and standard evaluation deliverables.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
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

from ml_training.common.metrics import save_evaluation_artifacts
from ml_training.common.training_gate import (
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TrainingGate,
    compute_file_sha256,
)
from ml_training.tep.dataset import (
    CANONICAL_FAULT_FEATURES,
    CANONICAL_FEATURES,
    CURATED_TEP_PATH,
    FAULT_DESCRIPTIONS,
    TARGET_COLUMN,
    load_tep_multiclass_splits,
)
from ml_training.tep.preprocessor import TEPFaultPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nova.ml.tep.train_fault")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"


def train_and_evaluate(
    dataset_path: Path = CURATED_TEP_PATH,
    version: str = "v1.1.0",
    random_state: int = 42,
    n_estimators: int = 200,
    max_depth: int = 6,
    max_runs_per_fault: int = 10,
) -> Dict[str, Any]:
    """Train and evaluate 21-class TEP Fault Classifier."""
    logger.info("=== Starting TEP Multiclass Fault Classifier Training Pipeline ===")

    # 1. Training Gate
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tep",
    )

    # 2. Load Dataset Splits
    split_data = load_tep_multiclass_splits(
        dataset_path=valid_path,
        train_ratio=0.75,
        window_size=3,
        max_runs_per_fault=max_runs_per_fault,
    )

    X_train = split_data.x_train
    y_train = split_data.y_train
    X_val = split_data.x_val
    y_val = split_data.y_val
    X_test = split_data.x_test
    y_test = split_data.y_test

    # 3. Fit Preprocessor strictly on Training Data
    preprocessor = TEPFaultPreprocessor(feature_names=CANONICAL_FAULT_FEATURES, window_size=3)
    preprocessor.fit(X_train)

    X_train_scaled = preprocessor.transform(X_train)
    X_val_scaled = preprocessor.transform(X_val)
    X_test_scaled = preprocessor.transform(X_test)

    # 4. Train Model
    clf = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=21,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        tree_method="hist",
        early_stopping_rounds=20,
    )

    clf.fit(
        X_train_scaled,
        y_train,
        eval_set=[(X_train_scaled, y_train), (X_val_scaled, y_val)],
        verbose=False,
    )

    # 5. Evaluate on Test Split
    y_pred = clf.predict(X_test_scaled)
    acc = float(accuracy_score(y_test, y_pred))
    macro_prec = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
    macro_rec = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    metrics = {
        "accuracy": acc,
        "macro_precision": macro_prec,
        "macro_recall": macro_rec,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
    }

    # 6. Save Versioned Model Artifact
    model_dir = ARTIFACTS_DIR / "process_fault_classifier" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.joblib"

    artifact_payload = {
        "model_name": "ProcessFaultClassifier",
        "version": version,
        "model": clf,
        "preprocessor": preprocessor,
        "feature_names": CANONICAL_FAULT_FEATURES,
        "class_mapping": FAULT_DESCRIPTIONS,
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(artifact_payload, model_file, compress=3)

    # 7. Save Standard Evaluation Deliverables
    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(cm)
    save_evaluation_artifacts(
        model_name="ProcessFaultClassifier",
        version=version,
        metrics=metrics,
        training_metadata={"dataset_path": str(valid_path), "classes_count": 21},
        confusion_matrix_df=cm_df,
    )

    logger.info("ProcessFaultClassifier training complete. Accuracy: %.4f, Macro F1: %.4f", acc, macro_f1)
    return {
        "metrics": metrics,
        "artifact_path": str(model_file),
    }


if __name__ == "__main__":
    train_and_evaluate()
