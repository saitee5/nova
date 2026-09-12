# Evaluation Report: TubeTemperaturePredictor (v1.1.0)

- **Generated At:** 2026-09-12T17:21:23.237888+00:00
- **Model Name:** `TubeTemperaturePredictor`
- **Model Version:** `v1.1.0`
- **Target Type:** `physics-informed synthetic`
- **Status:** `VALIDATED_WITH_LIMITATIONS`

---

## ⚠️ SYNTHETIC TARGET DISCLOSURE

> **This model predicts a PHYSICS-INFORMED SYNTHETIC TMT target.**
>
> The target variable `TMT` was generated via 1D radial heat transfer equations
> with a known pressure-unit mismatch in the generation formula (Pa vs bar/atm).
>
> **This is NOT measured industrial plant TMT.**
> **This is NOT a coking detector.**
> **This does NOT claim industrial validation.**
>
> High R² reflects learnability of the synthetic formula, not industrial accuracy.

---

## Summary Metrics

| Metric | Value |
| :--- | :--- |
| MAE | 0.1557 °C |
| RMSE | 0.3175 °C |
| R² Score | 1.0 |
| MAPE | 0.017% |
| sMAPE | 0.017% |
| Median Abs Error | 0.0096 °C |
| P90 Abs Error | 0.474 °C |
| P95 Abs Error | 0.702 °C |
| P99 Abs Error | 1.2948 °C |
| Max Abs Error | 3.0883 °C |
| Pearson Correlation | 1.0 |

## Residual Analysis

| Metric | Value |
| :--- | :--- |
| Residual Mean (Bias) | -0.0028 °C |
| Residual Std | 0.3175 °C |
| Residual Skewness | -0.6573 |
| Residual Kurtosis | 12.4726 |

## Physical Constraint Check (TMT > COT)

- **Violations:** 0 / 4503
- **Violation Rate:** 0.0000%

## Boundary Analysis (Synthetic Target Distribution)

- **Test samples at upper bound (1100.0 °C):** 2240 (49.74%)
- **Test samples at lower bound (COT + 35 °C):** 2263 (50.26%)

## Overfitting Check

| Split | MAE (°C) | R² |
| :--- | :--- | :--- |
| Train | 0.0814 | 1.0 |
| Validation | 0.1366 | 1.0 |
| Test | 0.1557 | 1.0 |

## Training Metadata

```json
{
  "dataset_path": "C:\\Users\\Aarushi Sachdeva\\OneDrive\\Desktop\\nova\\data\\curated\\tube_temperature\\tube_temperature_canonical.csv",
  "dataset_sha256": "adeac6e405fef71e5de18393467109d5b3549d934925416f1494274afbafd6b6",
  "train_samples": 21010,
  "val_samples": 4502,
  "test_samples": 4503,
  "target_type": "physics-informed synthetic",
  "target_units": "\u00b0C",
  "features": [
    "C2H2",
    "C2H4",
    "C2H6",
    "C3H6",
    "C3H8",
    "C4H6",
    "C4H8",
    "C6H6",
    "C7H8",
    "C8H10",
    "C8H8",
    "CH4",
    "H2O",
    "H2",
    "Pressure",
    "Cracking gas temperature",
    "COT"
  ],
  "features_count": 17,
  "split_strategy": "chronological 70% train / 15% val / 15% test",
  "algorithm": "XGBoost Regression (hist, max_depth=6, lr=0.05, n_est=500, early_stop=30)",
  "random_state": 42,
  "artifact_path": "C:\\Users\\Aarushi Sachdeva\\OneDrive\\Desktop\\nova\\artifacts\\models\\tube_temperature_predictor\\v1.1.0\\model.joblib",
  "artifact_sha256": "950bfb2b80e9ba8af4ca5a9bd93b5e013c60527a7d0d5ff0561fe79e51950613",
  "artifact_size_bytes": 555017,
  "trained_at": "2026-09-12T17:21:23.171652+00:00",
  "provenance_warning": "This model predicts a SYNTHETIC TMT target derived from 1D radial heat transfer equations with a known pressure-unit mismatch. It is NOT a measured industrial plant TMT predictor. High R\u00b2 reflects learnability of the synthetic formula, not industrial accuracy."
}
```
