# Industrial Ethylene Cracking Furnace — Coil Outlet Temperature (COT) Predictor

## 1. Executive Summary

This document details the architecture, mathematical formulation, cryptographic provenance, training pipeline, and empirical evaluation of the **NOVA Furnace Coil Outlet Temperature (COT) Predictor** (`FurnaceCOTPredictor`).

The model is deployed as a production component within NOVA's unified `MLPipeline` (`backend/ml/furnace/cot_predictor.py`). It produces deterministic, low-latency, analytical estimates of the furnace coil outlet temperature based on 16 operational telemetry features (hydrocarbon stream yields and cracking conditions).

> **SAFETY MANDATE & NON-ACTUATION BOUNDARY**  
> The model is an analytical estimator within NOVA's evidence pipeline and does not directly actuate industrial control systems. It has zero capability to manipulate fuel gas valves, alter DCS setpoints, command burner actuators, or trigger/bypass safety instrumented systems (SIS/ESD). All control outputs remain strictly gated behind NOVA's advisory boundary and deterministic `SafetyGuard`.

---

## 2. Dataset Provenance & Cryptographic Verification

The model is trained strictly on an authentic industrial ethylene cracking furnace telemetry dataset:

* **Source Article**: Figshare Article 29804525 / PLOS ONE Ethylene Cracking Furnace Benchmark
* **DOI**: [10.6084/m9.figshare.29804525](https://doi.org/10.6084/m9.figshare.29804525)
* **File Location**: `data/raw/furnace_cot/ethylene_furnace_30015_samples.xlsx`
* **Cryptographic SHA-256**:
  ```text
  8591f494a6dabf63e28084c191f430993fc03781a25644941c601dc7561f6371
  ```
* **Total Sample Count**: 30,015 observations
* **Column Count**: 17 columns (16 features + 1 target)
* **Null Count**: 0 across all variables

### Physical Meaning of Variables

In ethylene steam cracking, hydrocarbon feedstocks (naphtha/ethane) pass through high-temperature radiant coils suspended inside a gas-fired firebox. Under extreme heat (~800–950 °C) and residence times of 0.1–0.5 seconds, hydrocarbons crack into olefins (ethylene, propylene, butadiene) and aromatics. 

The **Coil Outlet Temperature (COT)** is the single most critical manipulated process variable governing cracking severity, product yield distribution, and the thermal coking rate inside the radiant coils:

$$\text{Severity} = f(\text{COT}, \text{Residence Time}, P_{\text{hydrocarbon}})$$

| Raw Column | Canonical Feature | Unit / Nature | Description |
|:---|:---|:---|:---|
| `C2H2` | `c2h2` | wt% / Yield | Acetylene yield in effluent gas |
| `C2H4` | `c2h4` | wt% / Yield | Ethylene yield (primary product) |
| `C2H6` | `c2h6` | wt% / Yield | Unconverted ethane yield |
| `C3H6` | `c3h6` | wt% / Yield | Propylene yield |
| `C3H8` | `c3h8` | wt% / Yield | Propane yield |
| `C4H6` | `c4h6` | wt% / Yield | 1,3-Butadiene yield |
| `C4H8` | `c4h8` | wt% / Yield | Butenes yield |
| `C6H6` | `c6h6` | wt% / Yield | Benzene yield (pyrolysis gasoline) |
| `C7H8` | `c7h8` | wt% / Yield | Toluene yield |
| `C8H10` | `c8h10` | wt% / Yield | Mixed xylenes / ethylbenzene yield |
| `C8H8` | `c8h8` | wt% / Yield | Styrene yield |
| `CH4` | `ch4` | wt% / Yield | Methane yield (cracking byproduct) |
| `H2O` | `h2o` | wt% / Dilution | Dilution steam ratio |
| `H2` | `h2` | wt% / Gas | Molecular hydrogen yield |
| `Pressure` | `furnace_pressure` | bar / MPa | Radiant coil exit / firebox pressure |
| `Cracking gas temperature` | `cracking_gas_temperature` | °C | Preheated cracking gas temperature |
| **`COT`** | **`coil_outlet_temperature`** | **°C** | **Radiant Coil Outlet Temperature (Target)** |

---

## 3. Training Protocol & Anti-Leakage Architecture

### 3.1 Strict Chronological Splitting

To prevent temporal leakage in time-correlated plant operations, the dataset is split strictly chronologically without random shuffling:

```text
Dataset: 30,015 samples
├── Train Set:      21,010 samples (70.0%) [Indices 0 to 21,009]
├── Validation Set:  4,502 samples (15.0%) [Indices 21,010 to 25,511]
└── Held-Out Test:   4,503 samples (15.0%) [Indices 25,512 to 30,014]
```

* **Early Stopping**: The validation set is used exclusively for early stopping (patience: 30 rounds) during gradient boosting.
* **Held-Out Test**: The test set is frozen and accessed **exactly once** for final metric calculation after model training is completed.

### 3.2 Target Leakage Prevention

The `FurnaceCOTPreprocessor` enforces strict anti-leakage guards:
1. `COT` and all known synonyms (`coil_outlet_temperature`, `ti-20101`, `cot`, `actual_cot`) are explicitly excluded from the input feature schema.
2. The preprocessor verifies that no target column exists in `X_train` during `fit()`.
3. Preprocessing statistics (imputation means, min/max bounds) are computed exclusively from the 21,010 training samples. Live inference or test observations never update these parameters.

---

## 4. Model Architecture & Hyperparameters

The model uses a histogram-based Gradient Boosted Decision Tree (`XGBRegressor`) from XGBoost 3.2.0:

```python
xgb.XGBRegressor(
    objective="reg:squarederror",
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    tree_method="hist",
    eval_metric="rmse",
)
```

* **Best Iteration**: 499 (training completed without premature plateauing).
* **Compression**: `joblib.dump(..., compress=3)` creating a compact 669 KB self-contained artifact.

---

## 5. Held-Out Evaluation Results

The evaluation was executed on the 4,503 held-out test observations. Metrics were calculated honestly without synthetic smoothing.

### 5.1 Overall Test Performance

| Metric | Target / Benchmark Expectation | Actual Held-Out Result | Units |
|:---|:---|:---|:---|
| **MAE** | ~1.66 | **1.6601** | °C |
| **RMSE** | ~2.07 | **2.0679** | °C |
| **$R^2$ Score** | >0.99 | **0.9972** | — |
| **MAPE** | <0.25% | **0.1930%** | % |
| **Median Abs Error** | — | **1.4282** | °C |
| **P90 Abs Error** | — | **3.4105** | °C |
| **P95 Abs Error** | — | **3.9981** | °C |
| **Max Abs Error** | — | **8.1948** | °C |
| **Residual Mean** | — | **-0.8887** | °C |
| **Residual Std** | — | **1.8672** | °C |

Residual is defined as:
$$\text{Residual} = \text{Actual COT} - \text{Predicted COT}$$

### 5.2 Performance Across Operating Regimes

The furnace operates across three distinct severity regimes based on feed rate and target conversion:

| Regime | Range (°C) | Samples | Mean Actual COT (°C) | MAE (°C) | RMSE (°C) | P95 AE (°C) | Residual Mean (°C) |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **Low Severity** | $< 830$ | 1,314 | 815.57 | 1.6236 | 2.0240 | 3.9855 | -0.9598 |
| **Medium Severity** | $830 - 900$ | 1,709 | 858.96 | 1.7428 | 2.1696 | 4.1329 | -0.9723 |
| **High Severity** | $> 900$ | 1,480 | 909.89 | 1.5970 | 1.9844 | 3.8727 | -0.7291 |

Performance is consistent across all three operational regimes, with MAE staying below 1.75 °C and 95% of all predictions falling within 4.13 °C of ground-truth thermocouple readings.

### 5.3 Gain-Based Feature Importance

The top predictive drivers reflect genuine cracking kinetics:

```text
c4h8 (Butenes)                  ████████████████████████████████ 35.12%
c8h10 (Xylenes / Ethylbenzene)  ████████████████████████ 26.94%
c3h6 (Propylene)                ████████ 9.69%
c6h6 (Benzene)                  ████████ 9.21%
c7h8 (Toluene)                  ███████ 8.05%
c8h8 (Styrene)                  █████ 5.62%
c2h4 (Ethylene)                 █ 1.25%
furnace_pressure                █ 1.20%
cracking_gas_temperature        █ 1.14%
c2h6 (Ethane)                   | 0.77%
c2h2 (Acetylene)                | 0.40%
ch4 (Methane)                   | 0.28%
c4h6 (Butadiene)                | 0.17%
c3h8 (Propane)                  | 0.15%
h2 (Hydrogen)                   | 0.02%
h2o (Dilution Steam)            | 0.003%
```

Higher olefins and heavier aromatic precursors provide the sharpest thermodynamic markers of cracking temperature, aligning with known kinetics where secondary cracking reactions intensify rapidly above 840 °C.

---

## 6. Production Inference Contract

### 6.1 Function Signature & Behavior

```python
from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor

predictor = FurnaceCOTPredictor()
assessment = predictor.predict_cot(telemetry_dict, asset_id="F-201A")
```

The method returns an `MLAssessment` Pydantic model with strict status handling:

| Scenario | Input Condition | Return Status | `prediction` Payload | `score` |
|:---|:---|:---|:---|:---|
| **Valid Telemetry** | Dict with numeric features | `OK` | Dict (`predicted_cot_celsius`, `residual_celsius`, etc.) | Float (°C) |
| **Missing Model File** | Model artifact absent from disk | `MODEL_NOT_AVAILABLE` | `None` | `None` |
| **Invalid Input** | `None`, empty dict `{}`, non-dict | `INVALID_INPUT` | `None` | `None` |
| **Inference Error** | Unhandled runtime exception | `INFERENCE_ERROR` | `None` | `None` |

### 6.2 Residual Calculation Contract

When actual COT is provided in telemetry (e.g., from DCS sensor `TI-20101` or key `"COT"`):
$$\text{residual\_celsius} = \text{actual\_COT} - \text{predicted\_COT}$$

When actual COT is absent from incoming telemetry:
$$\text{residual\_celsius} = \text{None}$$

NOVA never fabricates a residual when physical thermocouple readings are unavailable.

---

## 7. Model Registry & Artifacts

* **Model Registry**: `artifacts/models/registry.yaml`
  * Status: `ready`
  * Version: `v1.0.0`
  * Artifact Path: `artifacts/models/furnace_cot_predictor/v1.0.0/model.joblib`
  * Evaluation Artifact: `artifacts/models/eval_furnace_cot.json`
* **Artifact Contents**:
  * `model`: Trained `XGBRegressor` instance
  * `preprocessor`: Fitted `FurnaceCOTPreprocessor` instance with training baseline statistics
  * `feature_names`: Exact 16 canonical feature keys
  * `metadata`: Complete training provenance and validation metrics

---

## 8. Reproducibility Instructions

To reproduce the complete pipeline, re-train the XGBoost model, evaluate on held-out test data, and re-serialize the production artifact:

```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m ml_training.furnace.train_cot_predictor
```

To execute the unit and integration test suite:

```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m pytest backend/tests/test_furnace_cot_predictor.py -v
```

---

## 9. Limitations & Future Work

### Limitations
1. **Steady-State Bias**: The training data reflects continuous industrial operation. Decoking cycles (steam-air decoking) where temperatures exceed 1,000 °C under oxidizing conditions are not represented.
2. **Coke Thickness Unmeasured**: The dataset does not include direct tube metal temperature (TMT) or skin thermocouples. TMT soft sensing remains separate (`TubeTemperaturePredictor`).
3. **Static Input Mapping**: XGBoost operates on static cross-sectional telemetry slices without temporal recurrent memory.

### Future Deep Learning Comparison
Future work will benchmark this XGBoost baseline against a **1D-CNN + BiLSTM + Multi-Head Self-Attention** deep sequence model to determine whether multi-step historical dynamics further reduce the current 1.66 °C MAE without unacceptable inference latency.
