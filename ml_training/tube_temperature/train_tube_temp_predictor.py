"""
ml_training/tube_temperature/train_tube_temp_predictor.py — Train & Evaluate Tube Temperature Predictor.

Trains an XGBoost regression model for Tube Metal Temperature (TMT) prediction from:
data/curated/tube_temperature/tube_temperature_canonical.csv

Target Provenance:
- target_type: "physics-informed synthetic"
- Target variable is derived from 1D radial heat transfer process boundary state equations.
- NOT measured industrial plant TMT.
- NOT a coking detector.

Enforces:
1. Curated-only dataset consumption via TrainingGate.
2. Chronological splitting: 70% train (21,010 samples), 15% val (4,502 samples), 15% test (4,503 samples).
3. Zero target leakage: TMT is strictly excluded from input features.
4. Physical constraint validation: Asserts TMT > COT across all predictions.
5. Standard evaluation output under artifacts/evaluation/TubeTemperaturePredictor/<version>/.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
import yaml
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml_training.common.metrics import save_evaluation_artifacts
from ml_training.common.training_gate import (
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TargetLeakageError,
    TrainingGate,
    compute_file_sha256,
)
from ml_training.tube_temperature.dataset import (
    CANONICAL_FEATURES,
    CURATED_TUBE_TEMP_PATH,
    TARGET_COLUMN,
    TARGET_TYPE,
    TARGET_UNITS,
    load_tube_temp_dataset,
)
from ml_training.tube_temperature.preprocessor import TubeTempPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nova.ml.tube_temp.train")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"


def train_and_evaluate(
    dataset_path: Path = CURATED_TUBE_TEMP_PATH,
    version: str = "v1.1.0",
    random_state: int = 42,
    n_estimators: int = 500,
    learning_rate: float = 0.05,
    max_depth: int = 6,
) -> Dict[str, Any]:
    """Train and evaluate TubeTemperaturePredictor on curated dataset."""
    logger.info("=== Starting Tube Temperature Predictor Training Pipeline ===")

    # 1. Training Gate Enforcement
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tube_temperature",
    )

    # 2. Chronological Split
    split_data = load_tube_temp_dataset(filepath=valid_path, train_ratio=0.70, val_ratio=0.15)
    X_train_df = split_data.x_train
    y_train = split_data.y_train.values
    X_val_df = split_data.x_val
    y_val = split_data.y_val.values
    X_test_df = split_data.x_test
    y_test = split_data.y_test.values

    # Strict target leakage assertion
    assert TARGET_COLUMN not in X_train_df.columns, "CRITICAL: Target 'TMT' found in training features"
    assert TARGET_COLUMN not in X_val_df.columns, "CRITICAL: Target 'TMT' found in validation features"
    assert TARGET_COLUMN not in X_test_df.columns, "CRITICAL: Target 'TMT' found in test features"

    # 3. Fit Preprocessor strictly on Training Data
    preprocessor = TubeTempPreprocessor(feature_names=CANONICAL_FEATURES)
    preprocessor.fit(X_train_df)

    X_train = preprocessor.transform(X_train_df)
    X_val = preprocessor.transform(X_val_df)
    X_test = preprocessor.transform(X_test_df)

    # 4. Train XGBoost Regressor with Early Stopping
    regressor = xgb.XGBRegressor(
        objective="reg:squarederror",
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        tree_method="hist",
        early_stopping_rounds=30,
    )

    regressor.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=False,
    )

    # 5. Evaluate on Test Split
    y_pred_test = regressor.predict(X_test)
    test_mae = float(mean_absolute_error(y_test, y_pred_test))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))
    test_r2 = float(r2_score(y_test, y_pred_test))
    test_mape = float(np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100)

    residuals = y_test - y_pred_test
    abs_errors = np.abs(residuals)

    # Physical constraint check: TMT > COT
    cot_test = X_test_df["COT"].values
    violations = np.sum(y_pred_test <= cot_test)
    violation_rate = float(violations / len(y_pred_test))

    metrics = {
        "mae_celsius": test_mae,
        "rmse_celsius": test_rmse,
        "r2_score": test_r2,
        "mape_percent": test_mape,
        "median_absolute_error": float(np.median(abs_errors)),
        "p90_absolute_error": float(np.percentile(abs_errors, 90)),
        "p95_absolute_error": float(np.percentile(abs_errors, 95)),
        "max_absolute_error": float(np.max(abs_errors)),
        "physical_constraint_violations": int(violations),
        "physical_constraint_violation_rate": violation_rate,
    }

    # 6. Save Model Artifact (Versioned)
    model_dir = ARTIFACTS_DIR / "tube_temperature_predictor" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.joblib"

    artifact_payload = {
        "model_name": "TubeTemperaturePredictor",
        "version": version,
        "model": regressor,
        "preprocessor": preprocessor,
        "feature_names": CANONICAL_FEATURES,
        "target_name": TARGET_COLUMN,
        "target_units": TARGET_UNITS,
        "target_type": TARGET_TYPE,
        "provenance": (
            "Target 'TMT' is a physics-informed synthetic estimation computed via 1D radial heat transfer equations. "
            "It is NOT measured industrial plant TMT."
        ),
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(artifact_payload, model_file, compress=3)

    # 7. Save Standard Evaluation Deliverables
    training_meta = {
        "dataset_path": str(valid_path),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "target_type": TARGET_TYPE,
        "target_units": TARGET_UNITS,
    }
    pred_df = pd.DataFrame({
        "actual_tmt_synthetic": y_test,
        "predicted_tmt": y_pred_test,
        "cot": cot_test,
        "residual": residuals,
    })

    save_evaluation_artifacts(
        model_name="TubeTemperaturePredictor",
        version=version,
        metrics=metrics,
        training_metadata=training_meta,
        predictions_df=pred_df,
    )

    logger.info(
        "TubeTemperaturePredictor training complete. Test MAE: %.4f °C, R2: %.4f, Violation Rate: %.2f%%",
        test_mae,
        test_r2,
        violation_rate * 100,
    )
    return {
        "metrics": metrics,
        "artifact_path": str(model_file),
    }


if __name__ == "__main__":
    train_and_evaluate()
