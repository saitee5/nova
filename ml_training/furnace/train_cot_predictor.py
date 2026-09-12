"""
ml_training/furnace/train_cot_predictor.py — Train & Evaluate XGBoost Furnace COT Predictor.

Trains an authentic XGBoost regression model on the 30,015-sample industrial ethylene cracking furnace benchmark.
- Chronological splitting: 70% train (21,010 samples), 15% val (4,502 samples), 15% test (4,503 samples).
- Zero data leakage: strict historical-only features, preprocessor fit on training data only.
- Target leakage prevention: COT is strictly excluded from input features.
- Early stopping on validation split (early_stopping_rounds=30).
- Single-pass evaluation on held-out test split (MAE, RMSE, R2, MAPE, P90, P95, Max Error, residual analysis by regime).
- Serializes production artifact to artifacts/models/furnace_cot_predictor/v1.0.0/model.joblib.
- Writes evaluation metrics to artifacts/models/eval_furnace_cot.json.
- Updates artifacts/models/registry.yaml with status: ready.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
import yaml
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml_training.furnace.dataset import (
    CANONICAL_FEATURE_NAMES,
    RAW_DATA_PATH,
    TARGET_NAME,
    compute_file_sha256,
    load_furnace_cot_dataset,
)
from ml_training.furnace.preprocessor import FurnaceCOTPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("furnace.train_cot")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "models"
MODEL_DIR = ARTIFACTS_DIR / "furnace_cot_predictor" / "v1.0.0"
MODEL_FILE = MODEL_DIR / "model.joblib"
EVAL_FILE = ARTIFACTS_DIR / "eval_furnace_cot.json"
REGISTRY_FILE = ARTIFACTS_DIR / "registry.yaml"


def train_and_evaluate() -> Dict[str, Any]:
    logger.info("=== Starting Furnace COT Predictor Training ===")
    logger.info("XGBoost version: %s", xgb.__version__)

    # 1. Load Dataset Splits Chronologically
    split_data = load_furnace_cot_dataset(
        filepath=RAW_DATA_PATH,
        train_ratio=0.70,
        val_ratio=0.15,
    )

    X_train_df = split_data.x_train
    y_train = split_data.y_train.values
    X_val_df = split_data.x_val
    y_val = split_data.y_val.values
    X_test_df = split_data.x_test
    y_test = split_data.y_test.values

    # Strict target leakage assertion
    assert TARGET_NAME not in X_train_df.columns, "CRITICAL: Target found in training features"
    assert TARGET_NAME not in X_val_df.columns, "CRITICAL: Target found in validation features"
    assert TARGET_NAME not in X_test_df.columns, "CRITICAL: Target found in test features"

    logger.info(
        "Dataset shapes: Train=%s, Val=%s, Test=%s",
        X_train_df.shape,
        X_val_df.shape,
        X_test_df.shape,
    )

    # 2. Fit Preprocessor strictly on Training Data
    preprocessor = FurnaceCOTPreprocessor(feature_names=CANONICAL_FEATURE_NAMES)
    preprocessor.fit(X_train_df)

    X_train = preprocessor.transform(X_train_df)
    X_val = preprocessor.transform(X_val_df)
    X_test = preprocessor.transform(X_test_df)

    # 3. Configure and Train XGBoost Regressor with Early Stopping
    xgb_params: Dict[str, Any] = {
        "objective": "reg:squarederror",
        "n_estimators": 500,
        "learning_rate": 0.05,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "tree_method": "hist",
        "eval_metric": "rmse",
        "early_stopping_rounds": 30,
        "n_jobs": 4,
    }

    logger.info("Training XGBoost Regressor with early stopping on validation split...")
    regressor = xgb.XGBRegressor(**xgb_params)
    regressor.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iteration = int(regressor.best_iteration) if hasattr(regressor, "best_iteration") and regressor.best_iteration is not None else 500
    logger.info("Training complete. Best iteration: %d", best_iteration)

    # 4. Independent Held-Out Test Evaluation
    logger.info("Evaluating on held-out test data (%d samples)...", len(y_test))
    y_pred = regressor.predict(X_test)

    mae = float(mean_absolute_error(y_test, y_pred))
    mse = float(mean_squared_error(y_test, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_test, y_pred))
    mape = float(np.mean(np.abs((y_test - y_pred) / y_test)) * 100.0)

    residuals = y_test - y_pred
    abs_errors = np.abs(residuals)
    median_ae = float(np.median(abs_errors))
    p90_ae = float(np.percentile(abs_errors, 90))
    p95_ae = float(np.percentile(abs_errors, 95))
    max_ae = float(np.max(abs_errors))
    res_mean = float(np.mean(residuals))
    res_std = float(np.std(residuals))

    # Regime-specific residual analysis
    # Low COT: < 830°C, Medium COT: 830°C to 900°C, High COT: > 900°C
    regimes = {
        "low_cot_under_830C": y_test < 830.0,
        "medium_cot_830_to_900C": (y_test >= 830.0) & (y_test <= 900.0),
        "high_cot_over_900C": y_test > 900.0,
    }
    regime_metrics: Dict[str, Any] = {}
    for r_name, r_mask in regimes.items():
        if np.any(r_mask):
            sub_y = y_test[r_mask]
            sub_pred = y_pred[r_mask]
            sub_res = residuals[r_mask]
            sub_abs = abs_errors[r_mask]
            regime_metrics[r_name] = {
                "sample_count": int(np.sum(r_mask)),
                "actual_cot_mean": round(float(np.mean(sub_y)), 2),
                "mae": round(float(mean_absolute_error(sub_y, sub_pred)), 4),
                "rmse": round(float(np.sqrt(mean_squared_error(sub_y, sub_pred))), 4),
                "median_ae": round(float(np.median(sub_abs)), 4),
                "p95_ae": round(float(np.percentile(sub_abs, 95)), 4),
                "residual_mean": round(float(np.mean(sub_res)), 4),
                "residual_std": round(float(np.std(sub_res)), 4),
            }

    # Feature Importance (gain-based)
    feature_importances = {
        CANONICAL_FEATURE_NAMES[i]: round(float(regressor.feature_importances_[i]), 5)
        for i in range(len(CANONICAL_FEATURE_NAMES))
    }
    # Sort descending
    sorted_importances = dict(sorted(feature_importances.items(), key=lambda x: x[1], reverse=True))

    overall_metrics = {
        "mae_celsius": round(mae, 4),
        "rmse_celsius": round(rmse, 4),
        "r2_score": round(r2, 4),
        "mape_percent": round(mape, 4),
        "median_absolute_error": round(median_ae, 4),
        "p90_absolute_error": round(p90_ae, 4),
        "p95_absolute_error": round(p95_ae, 4),
        "max_absolute_error": round(max_ae, 4),
        "residual_mean": round(res_mean, 4),
        "residual_std": round(res_std, 4),
    }

    eval_report: Dict[str, Any] = {
        "model_name": "FurnaceCOTPredictor (XGBoost Regressor Baseline)",
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "xgboost_version": xgb.__version__,
        "dataset_metadata": {
            "name": split_data.metadata["dataset_name"],
            "source": split_data.metadata["source"],
            "sha256": split_data.metadata["sha256"],
            "total_samples": split_data.metadata["total_samples"],
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "features_count": len(CANONICAL_FEATURE_NAMES),
            "target": TARGET_NAME,
            "target_unit": "celsius",
            "target_mean": split_data.metadata["target_mean"],
            "target_std": split_data.metadata["target_std"],
            "target_min": split_data.metadata["target_min"],
            "target_max": split_data.metadata["target_max"],
        },
        "model_configuration": {
            "objective": "reg:squarederror",
            "n_estimators": 500,
            "best_iteration": best_iteration,
            "learning_rate": 0.05,
            "max_depth": 6,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "tree_method": "hist",
        },
        "overall_metrics": overall_metrics,
        "operating_regime_analysis": regime_metrics,
        "feature_importances": sorted_importances,
    }

    logger.info(
        "Evaluation Results: MAE=%.4f °C, RMSE=%.4f °C, R2=%.4f, MAPE=%.4f%%, P95=%.4f °C",
        mae,
        rmse,
        r2,
        mape,
        p95_ae,
    )

    # Save evaluation report JSON
    EVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Saved evaluation report to %s", EVAL_FILE)

    # 5. Serialize Production Artifact
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    artifact_payload: Dict[str, Any] = {
        "model": regressor,
        "xgb_regressor": regressor,
        "preprocessor": preprocessor,
        "feature_names": CANONICAL_FEATURE_NAMES,
        "target_name": TARGET_NAME,
        "target_unit": "celsius",
        "schema_version": "v1.0.0",
        "metadata": {
            "model_name": "furnace_cot_predictor",
            "version": "v1.0.0",
            "target": TARGET_NAME,
            "target_unit": "celsius",
            "trained_timestamp": datetime.now(timezone.utc).isoformat(),
            "xgboost_version": xgb.__version__,
            "best_iteration": best_iteration,
            "random_seed": 42,
            "dataset_sha256": split_data.metadata["sha256"],
            "metrics": overall_metrics,
        },
        "training_metadata": {
            "trained_timestamp": datetime.now(timezone.utc).isoformat(),
            "xgboost_version": xgb.__version__,
            "best_iteration": best_iteration,
            "random_seed": 42,
            "dataset_sha256": split_data.metadata["sha256"],
            "metrics": overall_metrics,
        },
    }

    joblib.dump(artifact_payload, MODEL_FILE, compress=3)
    artifact_size = MODEL_FILE.stat().st_size
    artifact_sha256 = compute_file_sha256(MODEL_FILE)
    logger.info(
        "Saved model artifact to %s (size: %d bytes, sha256: %s)",
        MODEL_FILE,
        artifact_size,
        artifact_sha256,
    )

    # 6. Update Model Registry (registry.yaml)
    update_model_registry(artifact_sha256, artifact_size, eval_report)

    return {
        "artifact_path": str(MODEL_FILE),
        "artifact_size": artifact_size,
        "artifact_sha256": artifact_sha256,
        "best_iteration": best_iteration,
        "metrics": overall_metrics,
    }


def update_model_registry(artifact_sha256: str, artifact_size: int, eval_report: Dict[str, Any]) -> None:
    """Update registry.yaml with furnace_cot_predictor status=ready."""
    if not REGISTRY_FILE.exists():
        logger.warning("registry.yaml not found at %s", REGISTRY_FILE)
        return

    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        registry_data = yaml.safe_load(f)

    if "models" not in registry_data:
        registry_data["models"] = {}

    rel_artifact_path = "artifacts/models/furnace_cot_predictor/v1.0.0/model.joblib"
    registry_data["models"]["furnace_cot_predictor"] = {
        "name": "FurnaceCOTPredictor",
        "version": "v1.0.0",
        "model_type": "furnace_cot_prediction",
        "algorithm": "XGBoost Regression Baseline",
        "status": "ready",
        "dataset": eval_report["dataset_metadata"]["name"],
        "dataset_hash": f"sha256:{eval_report['dataset_metadata']['sha256']}",
        "feature_schema": "ethylene_cracking_16_features_v1",
        "target": "coil_outlet_temperature_celsius",
        "artifact_path": rel_artifact_path,
        "preprocessing_artifact": rel_artifact_path,
        "evaluation_artifact": "artifacts/models/eval_furnace_cot.json",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "framework": "xgboost",
        "framework_version": xgb.__version__,
        "asset_class": "ethylene_cracking_furnace",
        "description": "Industrial ethylene cracking furnace Coil Outlet Temperature (COT) XGBoost regression predictor.",
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "evaluation_metrics": eval_report["overall_metrics"],
        "feature_names": CANONICAL_FEATURE_NAMES,
    }

    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        yaml.dump(registry_data, f, sort_keys=False, default_flow_style=False)

    logger.info("Updated model registry at %s: furnace_cot_predictor -> ready", REGISTRY_FILE)


if __name__ == "__main__":
    train_and_evaluate()
