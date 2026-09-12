# Comprehensive Evaluation Report: FurnaceCOTPredictor (v1.1.0)

- **Model Name:** `FurnaceCOTPredictor`
- **Model Version:** `v1.1.0`
- **Evaluation Date:** 2026-09-12T16:41:05.087320+00:00
- **Dataset:** `data/curated/furnace_cot/furnace_cot_canonical.csv`
- **Dataset SHA-256:** `55c0a1c1653e8b034a0e0a03b1373879466d0c2001e0cbe08d03205ca4ddd5b8`
- **Algorithm:** XGBoost Regressor (`objective='reg:squarederror'`, `n_estimators=500`, `learning_rate=0.05`, `max_depth=6`)
- **Status:** **VALIDATED_WITH_LIMITATIONS**

---

## 1. Executive Summary

FurnaceCOTPredictor v1.1.0 was retrained strictly from the canonical curated ethylene cracking dataset (`furnace_cot_canonical.csv`, 30,015 records) with strict `TrainingGate` verification and chronological split isolation.

| Metric | v1.1.0 (Curated Chronological) | v1.0.0 (Legacy Baseline) | Delta / Assessment |
| :--- | :--- | :--- | :--- |
| **MAE (°C)** | **1.6601 °C** | 1.6601 °C | Parity achieved on curated data |
| **RMSE (°C)** | **2.0688 °C** | 2.0679 °C | Parity (+0.0009 °C) |
| **R² Score** | **0.9972** | 0.9972 | Preserved across unseen batches |
| **MAPE (%)** | **0.1929%** | 0.1930% | 0.19% relative error |
| **sMAPE (%)** | **0.1927%** | N/A | High symmetric stability |
| **Median Abs Error** | **1.4205 °C** | 1.4282 °C | 50% of predictions within 1.42 °C |
| **P90 Abs Error** | **3.4302 °C** | 3.4105 °C | 90% within 3.43 °C |
| **P95 Abs Error** | **3.9991 °C** | 3.9981 °C | 95% within 4.00 °C |
| **Max Abs Error** | **8.2421 °C** | 8.1948 °C | Max error strictly < 8.25 °C |
| **Residual Mean (Bias)** | **-0.8802 °C** | -0.8887 °C | Slight systematic overprediction |
| **Residual Std** | **1.8722 °C** | 1.8672 °C | Tight residual spread |

---

## 2. Investigation of High R² (0.9972)

As required by the scientific ML audit:
- **No Single Feature Leakage:** Individual linear regressions of single features against COT yield R² between 0.0036 (`C4H6`) and 0.6784 (`C2H6`). None exceed 0.68.
- **Physical Kinetics:** In ethylene pyrolysis, the 14 effluent gas chromatography species (especially aromatics C8H10, C7H8, C6H6, C8H8 and light ends C2H4, C3H6, CH4) and coil operating pressure form a mathematically over-determined kinetic fingerprint of coil outlet temperature (Arrhenius reaction progress).
- **Out-of-Sample Batch Holdout:** The test split evaluates exclusively on the final 4,503 rows (batches 13-15), which were entirely unseen during training and validation. The model generalizes to these separate runs with an MAE of 1.66 °C.

---

## 3. Performance Across Operating Ranges

| Operating Range | Sample Count | MAE (°C) | RMSE (°C) | Mean Bias (°C) | Max Error (°C) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `< 820 °C` | 901 | 1.6504 | 2.0430 | -1.1163 | 6.1155 |
| `820-850 °C` | 982 | 1.6991 | 2.1443 | -0.9075 | 8.2421 |
| `850-880 °C` | 896 | 1.7200 | 2.1323 | -0.9228 | 6.4831 |
| `880-910 °C` | 1002 | 1.8250 | 2.2135 | -1.1889 | 7.0658 |
| `> 910 °C` | 722 | 1.3159 | 1.6700 | -0.0670 | 5.6250 |

---

## 4. Top 10 Largest Absolute Errors

| Sample Index | Actual COT (°C) | Predicted COT (°C) | Residual (°C) | Abs Error (°C) | Cracking Gas Temp (°C) | Pressure (Pa) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 26482 | 834.02 | 842.26 | -8.24 | 8.24 | 724.62 | 344205 |
| 29638 | 901.12 | 908.19 | -7.07 | 7.07 | 816.25 | 310790 |
| 28596 | 845.92 | 852.90 | -6.97 | 6.97 | 736.46 | 342084 |
| 28614 | 848.48 | 855.18 | -6.71 | 6.71 | 738.35 | 341748 |
| 28552 | 842.94 | 849.53 | -6.58 | 6.58 | 732.42 | 342917 |
| 26831 | 861.22 | 867.70 | -6.48 | 6.48 | 759.06 | 337610 |
| 28781 | 862.33 | 868.55 | -6.23 | 6.23 | 753.97 | 338579 |
| 28344 | 817.62 | 823.74 | -6.12 | 6.12 | 707.44 | 346776 |
| 26978 | 837.75 | 843.86 | -6.11 | 6.11 | 774.55 | 334812 |
| 28706 | 856.30 | 862.40 | -6.09 | 6.09 | 746.43 | 340006 |

---

## 5. Feature Importance (XGBoost Gain)

| Rank | Feature Name | Description | Importance |
| :--- | :--- | :--- | :--- |
| 1 | `C8H10` | Pyrolysis telemetry parameter | 0.3082 |
| 2 | `C7H8` | Pyrolysis telemetry parameter | 0.1662 |
| 3 | `C3H8` | Pyrolysis telemetry parameter | 0.1662 |
| 4 | `C6H6` | Pyrolysis telemetry parameter | 0.1198 |
| 5 | `C3H6` | Pyrolysis telemetry parameter | 0.1094 |
| 6 | `C8H8` | Pyrolysis telemetry parameter | 0.0556 |
| 7 | `C2H4` | Pyrolysis telemetry parameter | 0.0186 |
| 8 | `Pressure` | Pyrolysis telemetry parameter | 0.0178 |
| 9 | `Cracking gas temperature` | Pyrolysis telemetry parameter | 0.0161 |
| 10 | `C2H6` | Pyrolysis telemetry parameter | 0.0121 |
| 11 | `C2H2` | Pyrolysis telemetry parameter | 0.0040 |
| 12 | `CH4` | Pyrolysis telemetry parameter | 0.0027 |
| 13 | `C4H6` | Pyrolysis telemetry parameter | 0.0025 |
| 14 | `H2` | Pyrolysis telemetry parameter | 0.0005 |
| 15 | `C4H8` | Pyrolysis telemetry parameter | 0.0002 |
| 16 | `H2O` | Pyrolysis telemetry parameter | 0.0001 |

---

## 6. Known Limitations & Operational Constraints

1. **Systematic Batch Shift (Bias = -0.88 °C):** On future operating runs, the model exhibits a mild negative residual mean (slight overprediction of ~0.88 °C), reflecting subtle inter-batch thermodynamic variations.
2. **Deterministic Point Estimate:** Prediction confidence is currently analytical/deterministic; calibrated Bayesian or conformal uncertainty intervals are not yet implemented.
3. **Sensor Quality Sensitivity:** Performance depends on continuous online analytical gas chromatography for effluent compositions; loss or degradation of GC analyzer signals requires preprocessor mean imputation.
