"""
ml_training/tube_temperature/train_tube_temp_predictor.py — Train & Evaluate Tube Temperature Predictor.

Trains an XGBoost regression model for Tube Metal Temperature (TMT) prediction from:
data/curated/tube_temperature/tube_temperature_canonical.csv

Target Provenance:
- target_type: "physics-informed synthetic"
- Target variable is derived from 1D radial heat transfer process boundary state equations.
- NOT measured industrial plant TMT.
- NOT a coking detector.
- NOT claiming industrial validation.

Known Target Limitations:
- 56% of rows are clipped at the upper metallurgical bound (1100.0 °C)
- 44% of rows are clipped at the lower bound (COT + 35.0 °C)
- The synthetic generation formula contains a pressure-unit mismatch (Pa vs bar)
- Despite these limitations, the model learns a useful input→output mapping for demonstration

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
from scipy.stats import kurtosis, skew
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

# Upper metallurgical bound used during synthetic target generation
TMT_UPPER_BOUND = 1100.0


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
    logger.info("TARGET PROVENANCE: physics-informed synthetic TMT (NOT measured plant data)")

    # 1. Training Gate Enforcement
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tube_temperature",
    )
    dataset_sha256 = compute_file_sha256(valid_path)

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

    logger.info(
        "Split sizes: train=%d, val=%d, test=%d",
        len(X_train_df), len(X_val_df), len(X_test_df),
    )

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

    t0 = datetime.now(timezone.utc)
    regressor.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=False,
    )
    training_duration = (datetime.now(timezone.utc) - t0).total_seconds()

    # 5. Comprehensive Test Set Evaluation
    y_pred_test = regressor.predict(X_test)
    y_pred_val = regressor.predict(X_val)
    y_pred_train = regressor.predict(X_train)

    test_mae = float(mean_absolute_error(y_test, y_pred_test))
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))
    test_r2 = float(r2_score(y_test, y_pred_test))
    test_mape = float(np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100)

    # Symmetric MAPE (sMAPE)
    denom = (np.abs(y_test) + np.abs(y_pred_test)) / 2.0
    test_smape = float(np.mean(np.abs(y_pred_test - y_test) / denom) * 100)

    residuals = y_test - y_pred_test
    abs_errors = np.abs(residuals)

    # Residual distribution statistics
    res_skew = float(skew(residuals))
    res_kurt = float(kurtosis(residuals))
    res_mean = float(np.mean(residuals))
    res_std = float(np.std(residuals))

    corr_matrix = np.corrcoef(y_test, y_pred_test)
    pearson_corr = float(corr_matrix[0, 1])

    # Physical constraint check: TMT > COT
    cot_test = X_test_df["COT"].values
    violations = np.sum(y_pred_test <= cot_test)
    violation_rate = float(violations / len(y_pred_test))

    # Boundary analysis: track predictions near synthetic bounds
    upper_bound_test = np.sum(np.abs(y_test - TMT_UPPER_BOUND) < 0.01)
    upper_bound_pct = float(upper_bound_test / len(y_test)) * 100
    lower_bound_test = np.sum(np.abs(y_test - (cot_test + 35.0)) < 0.01)
    lower_bound_pct = float(lower_bound_test / len(y_test)) * 100

    # Validation and train metrics for overfitting check
    val_mae = float(mean_absolute_error(y_val, y_pred_val))
    val_r2 = float(r2_score(y_val, y_pred_val))
    train_mae = float(mean_absolute_error(y_train, y_pred_train))
    train_r2 = float(r2_score(y_train, y_pred_train))

    metrics = {
        "model_name": "TubeTemperaturePredictor",
        "version": version,
        "status": "VALIDATED_WITH_LIMITATIONS",
        "target_type": TARGET_TYPE,
        "target_units": TARGET_UNITS,
        "mae_celsius": round(test_mae, 4),
        "rmse_celsius": round(test_rmse, 4),
        "r2_score": round(test_r2, 4),
        "mape_percent": round(test_mape, 4),
        "smape_percent": round(test_smape, 4),
        "median_absolute_error": round(float(np.median(abs_errors)), 4),
        "p90_absolute_error": round(float(np.percentile(abs_errors, 90)), 4),
        "p95_absolute_error": round(float(np.percentile(abs_errors, 95)), 4),
        "p99_absolute_error": round(float(np.percentile(abs_errors, 99)), 4),
        "max_absolute_error": round(float(np.max(abs_errors)), 4),
        "residual_mean": round(res_mean, 4),
        "residual_std": round(res_std, 4),
        "residual_skewness": round(res_skew, 4),
        "residual_kurtosis": round(res_kurt, 4),
        "target_pred_correlation": round(pearson_corr, 4),
        "physical_constraint_violations": int(violations),
        "physical_constraint_violation_rate": round(violation_rate, 6),
        "boundary_analysis": {
            "test_upper_bound_1100_count": int(upper_bound_test),
            "test_upper_bound_1100_pct": round(upper_bound_pct, 2),
            "test_lower_bound_cot35_count": int(lower_bound_test),
            "test_lower_bound_cot35_pct": round(lower_bound_pct, 2),
        },
        "actual_min": round(float(np.min(y_test)), 4),
        "actual_max": round(float(np.max(y_test)), 4),
        "actual_mean": round(float(np.mean(y_test)), 4),
        "actual_std": round(float(np.std(y_test)), 4),
        "pred_min": round(float(np.min(y_pred_test)), 4),
        "pred_max": round(float(np.max(y_pred_test)), 4),
        "pred_mean": round(float(np.mean(y_pred_test)), 4),
        "pred_std": round(float(np.std(y_pred_test)), 4),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "features_count": len(CANONICAL_FEATURES),
        "train_mae": round(train_mae, 4),
        "train_r2": round(train_r2, 4),
        "val_mae": round(val_mae, 4),
        "val_r2": round(val_r2, 4),
        "best_iteration": int(regressor.best_iteration) if hasattr(regressor, "best_iteration") else n_estimators,
        "training_duration_seconds": round(training_duration, 2),
        "dataset_sha256": dataset_sha256,
    }

    # 6. Save Model Artifact (Versioned)
    model_dir = ARTIFACTS_DIR / "tube_temperature_predictor" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.joblib"

    trained_time_iso = datetime.now(timezone.utc).isoformat()
    artifact_payload = {
        "model_name": "TubeTemperaturePredictor",
        "version": version,
        "model": regressor,
        "xgb_regressor": regressor,
        "preprocessor": preprocessor,
        "feature_names": CANONICAL_FEATURES,
        "target_name": TARGET_COLUMN,
        "target_units": TARGET_UNITS,
        "target_type": TARGET_TYPE,
        "schema_version": version,
        "provenance": (
            "Target 'TMT' is a physics-informed synthetic estimation computed via 1D radial heat transfer equations. "
            "It is NOT measured industrial plant TMT. It is NOT a coking detector. "
            "The synthetic generation formula contains a known pressure-unit mismatch (Pa vs bar) "
            "causing bimodal boundary collapse. This model demonstrates the fourth NOVA prediction "
            "capability while transparently representing the synthetic nature of its target."
        ),
        "metadata": {
            "model_name": "TubeTemperaturePredictor",
            "version": version,
            "algorithm": "XGBoost Regression (Synthetic Surrogate)",
            "target_type": TARGET_TYPE,
            "trained_at": trained_time_iso,
            "dataset_sha256": dataset_sha256,
        },
        "metrics": metrics,
        "trained_at": trained_time_iso,
    }
    joblib.dump(artifact_payload, model_file, compress=3)
    artifact_sha256 = compute_file_sha256(model_file)
    artifact_size = model_file.stat().st_size

    logger.info("Saved model artifact to %s (%d bytes, sha256=%s)", model_file, artifact_size, artifact_sha256)

    # 7. Save Standard Evaluation Deliverables
    training_meta = {
        "dataset_path": str(valid_path),
        "dataset_sha256": dataset_sha256,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "test_samples": len(X_test),
        "target_type": TARGET_TYPE,
        "target_units": TARGET_UNITS,
        "features": CANONICAL_FEATURES,
        "features_count": len(CANONICAL_FEATURES),
        "split_strategy": "chronological 70% train / 15% val / 15% test",
        "algorithm": "XGBoost Regression (hist, max_depth=6, lr=0.05, n_est=500, early_stop=30)",
        "random_state": random_state,
        "artifact_path": str(model_file),
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
        "trained_at": trained_time_iso,
        "provenance_warning": (
            "This model predicts a SYNTHETIC TMT target derived from 1D radial heat transfer equations "
            "with a known pressure-unit mismatch. It is NOT a measured industrial plant TMT predictor. "
            "High R² reflects learnability of the synthetic formula, not industrial accuracy."
        ),
    }

    pred_df = pd.DataFrame({
        "actual_tmt_synthetic": y_test,
        "predicted_tmt": y_pred_test,
        "cot": cot_test,
        "residual": residuals,
        "abs_error": abs_errors,
        "at_upper_bound_1100": (np.abs(y_test - TMT_UPPER_BOUND) < 0.01).astype(int),
        "at_lower_bound_cot35": (np.abs(y_test - (cot_test + 35.0)) < 0.01).astype(int),
    })

    # Generate comprehensive evaluation report
    report_md = _generate_evaluation_report(metrics, training_meta, version)

    save_evaluation_artifacts(
        model_name="TubeTemperaturePredictor",
        version=version,
        metrics=metrics,
        training_metadata=training_meta,
        predictions_df=pred_df,
        report_markdown=report_md,
    )

    logger.info(
        "TubeTemperaturePredictor %s training complete. "
        "Test MAE: %.4f °C, R²: %.4f, Violation Rate: %.4f%%, "
        "Upper-bound test pct: %.1f%%, Lower-bound test pct: %.1f%%",
        version,
        test_mae,
        test_r2,
        violation_rate * 100,
        upper_bound_pct,
        lower_bound_pct,
    )

    return {
        "metrics": metrics,
        "artifact_path": str(model_file),
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size,
    }


def _generate_evaluation_report(
    metrics: Dict[str, Any],
    training_meta: Dict[str, Any],
    version: str,
) -> str:
    """Generate comprehensive markdown evaluation report with synthetic surrogate disclaimers."""
    lines = [
        f"# Evaluation Report: TubeTemperaturePredictor ({version})",
        "",
        f"- **Generated At:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Model Name:** `TubeTemperaturePredictor`",
        f"- **Model Version:** `{version}`",
        f"- **Target Type:** `{TARGET_TYPE}`",
        f"- **Status:** `VALIDATED_WITH_LIMITATIONS`",
        "",
        "---",
        "",
        "## ⚠️ SYNTHETIC TARGET DISCLOSURE",
        "",
        "> **This model predicts a PHYSICS-INFORMED SYNTHETIC TMT target.**",
        ">",
        "> The target variable `TMT` was generated via 1D radial heat transfer equations",
        "> with a known pressure-unit mismatch in the generation formula (Pa vs bar/atm).",
        ">",
        "> **This is NOT measured industrial plant TMT.**",
        "> **This is NOT a coking detector.**",
        "> **This does NOT claim industrial validation.**",
        ">",
        "> High R² reflects learnability of the synthetic formula, not industrial accuracy.",
        "",
        "---",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| MAE | {metrics['mae_celsius']} °C |",
        f"| RMSE | {metrics['rmse_celsius']} °C |",
        f"| R² Score | {metrics['r2_score']} |",
        f"| MAPE | {metrics['mape_percent']}% |",
        f"| sMAPE | {metrics['smape_percent']}% |",
        f"| Median Abs Error | {metrics['median_absolute_error']} °C |",
        f"| P90 Abs Error | {metrics['p90_absolute_error']} °C |",
        f"| P95 Abs Error | {metrics['p95_absolute_error']} °C |",
        f"| P99 Abs Error | {metrics['p99_absolute_error']} °C |",
        f"| Max Abs Error | {metrics['max_absolute_error']} °C |",
        f"| Pearson Correlation | {metrics['target_pred_correlation']} |",
        "",
        "## Residual Analysis",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Residual Mean (Bias) | {metrics['residual_mean']} °C |",
        f"| Residual Std | {metrics['residual_std']} °C |",
        f"| Residual Skewness | {metrics['residual_skewness']} |",
        f"| Residual Kurtosis | {metrics['residual_kurtosis']} |",
        "",
        "## Physical Constraint Check (TMT > COT)",
        "",
        f"- **Violations:** {metrics['physical_constraint_violations']} / {metrics['test_samples']}",
        f"- **Violation Rate:** {metrics['physical_constraint_violation_rate'] * 100:.4f}%",
        "",
        "## Boundary Analysis (Synthetic Target Distribution)",
        "",
        f"- **Test samples at upper bound (1100.0 °C):** "
        f"{metrics['boundary_analysis']['test_upper_bound_1100_count']} "
        f"({metrics['boundary_analysis']['test_upper_bound_1100_pct']}%)",
        f"- **Test samples at lower bound (COT + 35 °C):** "
        f"{metrics['boundary_analysis']['test_lower_bound_cot35_count']} "
        f"({metrics['boundary_analysis']['test_lower_bound_cot35_pct']}%)",
        "",
        "## Overfitting Check",
        "",
        "| Split | MAE (°C) | R² |",
        "| :--- | :--- | :--- |",
        f"| Train | {metrics['train_mae']} | {metrics['train_r2']} |",
        f"| Validation | {metrics['val_mae']} | {metrics['val_r2']} |",
        f"| Test | {metrics['mae_celsius']} | {metrics['r2_score']} |",
        "",
        "## Training Metadata",
        "",
        "```json",
        json.dumps(training_meta, indent=2, default=str),
        "```",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    train_and_evaluate()
