# Tennessee Eastman Process (TEP) Multiclass Fault Diagnosis — Model Card & Documentation

## 1. Executive Summary

This document specifies the architecture, training methodology, evaluation metrics, and operational inference contract for NOVA's **ProcessFaultClassifier**.

The model is an offline-trained **XGBoost 22-class Multiclass Classifier** utilizing authentic process simulation data from the standardized **Downs & Vogel (1993) / Prof. Richard Braatz (UIUC/MIT)** Tennessee Eastman Process (TEP) benchmark.

The model classifies multi-variate continuous telemetry across 22 operational states:
- **Class 0:** Normal Steady-State Operation (`NORMAL`)
- **Classes 1–21:** 21 authentic process disturbance and component fault scenarios (`IDV(1)` through `IDV(21)`)

---

## 2. Distinction: Anomaly Detection vs. Fault Classification

NOVA enforces a strict architectural separation of responsibilities between process anomaly detection and fault classification:

```text
Process Telemetry
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. ProcessAnomalyDetector (PCA + Isolation Forest)          │
│    Question: "Is the current plant behavior abnormal?"      │
│    Mechanism: Unsupervised deviation from steady-state      │
│               statistical control limits (Q, T², IF)        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ProcessFaultClassifier (XGBoost Multiclass)              │
│    Question: "Which known fault pattern is most likely?"    │
│    Mechanism: Supervised probability distribution over      │
│               22 discrete process states (NORMAL + IDV 1-21)│
└─────────────────────────────────────────────────────────────┘
```

- If `ProcessAnomalyDetector` detects an anomaly, `ProcessFaultClassifier` provides diagnostic evidence indicating which known failure mode matches the symptom.
- If normal telemetry is provided to `ProcessFaultClassifier`, it outputs `NORMAL` with corresponding probability rather than forcing a fault prediction.
- The classifier only recognizes fault patterns represented in its 22 training classes; novel or unmodeled disturbances must be flagged by the anomaly detector.

---

## 3. Dataset Architecture & Leakage Prevention

### 3.1 Benchmark Source Files
The model uses all 44 authentic TEP simulation files from the Downs & Vogel / Braatz repository:

| Set | Filename | Shape | Sampling | Injection Time | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Normal Train** | `d00.dat` | $500 \times 52$ | 3.0 min | None | Training & Validation (normal) |
| **Fault Train** | `d01.dat`..`d21.dat` | $480 \times 52$ (21 files) | 3.0 min | Sample 20 (1.0 hr) | Training & Validation (faults 1–21) |
| **Normal Test** | `d00_te.dat` | $960 \times 52$ | 3.0 min | None | Independent Testing (normal) |
| **Fault Test** | `d01_te.dat`..`d21_te.dat` | $960 \times 52$ (21 files) | 3.0 min | Sample 160 (8.0 hr) | Independent Testing (faults 1–21) |

### 3.2 Chronological Splitting & Leakage Controls
- **Zero Temporal Leakage:** Samples are never randomly shuffled into train/val/test splits.
- **Within-Run Splitting:**
  - Training runs (`d00.dat` to `d21.dat`): first 75% chronological samples $\to$ **Training Set** (7,893 samples); remaining 25% chronological samples $\to$ **Validation Set** (2,645 samples).
- **Independent Test Evaluation:**
  - Test evaluation is performed solely on independent simulation runs (`d00_te.dat` to `d21_te.dat`, 21,120 samples) which use different initial condition seeds and different simulation durations.

### 3.3 Fault Injection Boundary & Transition Window Exclusion
In training runs `d01.dat`..`d21.dat`, disturbances are injected at sample 20 ($t=20$).
For temporal window size $W=3$:
- $t < 20$: pure normal operation ($\text{Class } 0$).
- $t = 20$ (window samples 18, 19, 20) and $t = 21$ (window samples 19, 20, 21): **Transition Windows** that straddle the pre-fault and post-fault boundary.
- **Mandatory Policy:** Exactly 2 transition windows per fault run ($2 \times 21 = 42$ windows total) are **excluded** from training and validation sets to prevent contaminated transition labels.
- $t \ge 22$: pure fault operation ($\text{Class } f\_id$).

---

## 4. Class Definitions (22 Classes)

| Class ID | Fault Code | Description | Disturbance Type |
| :---: | :--- | :--- | :--- |
| **0** | `NORMAL` | Normal Steady-State Operation | Normal |
| **1** | `IDV(1)` | A/C Feed Ratio, B Composition Constant (Stream 4) | Step |
| **2** | `IDV(2)` | B Composition, A/C Ratio Constant (Stream 4) | Step |
| **3** | `IDV(3)` | D Feed Temp (Stream 2) | Step |
| **4** | `IDV(4)` | Reactor Cooling Water Inlet Temp | Step |
| **5** | `IDV(5)` | Condenser Cooling Water Inlet Temp | Step |
| **6** | `IDV(6)` | A Feed Loss (Stream 1) | Step |
| **7** | `IDV(7)` | C Header Pressure Loss - Reduced Availability (Stream 4) | Step |
| **8** | `IDV(8)` | A, B, C Feed Composition (Stream 4) | Random Variation |
| **9** | `IDV(9)` | D Feed Temp (Stream 2) | Random Variation |
| **10** | `IDV(10)` | C Feed Temp (Stream 4) | Random Variation |
| **11** | `IDV(11)` | Reactor Cooling Water Inlet Temp | Random Variation |
| **12** | `IDV(12)` | Condenser Cooling Water Inlet Temp | Random Variation |
| **13** | `IDV(13)` | Reaction Kinetics | Slow Drift |
| **14** | `IDV(14)` | Reactor Cooling Water Valve | Sticking |
| **15** | `IDV(15)` | Condenser Cooling Water Valve | Sticking |
| **16** | `IDV(16)` | Unknown Disturbance A | Unknown |
| **17** | `IDV(17)` | Unknown Disturbance B | Unknown |
| **18** | `IDV(18)` | Unknown Disturbance C | Unknown |
| **19** | `IDV(19)` | Unknown Disturbance D | Unknown |
| **20** | `IDV(20)` | Unknown Disturbance E | Unknown |
| **21** | `IDV(21)` | Stream 4 Valve Fixed Position | Valve Position |

---

## 5. Feature Engineering Contract (156 Features)

The classifier operates on 52 process variables:
- 41 continuous process measurements: `xmeas_1` through `xmeas_41`
- 11 manipulated variables: `xmv_1` through `xmv_11`

### 5.1 Three Feature Families ($W=3$ Window)
For each of the 52 process variables, 3 deterministic features are extracted:
1. `raw`: Instantaneous value at current time step $x_t$.
2. `rolling_mean`: 3-sample temporal average $\frac{1}{3} \sum_{i=0}^2 x_{t-i}$.
3. `temporal_delta`: First-order rate of change $x_t - x_{t-2}$.

Total features: $52 \times 3 = 156$ features.

### 5.2 Deterministic Feature Ordering
Frozen canonical feature schema order:
```text
xmeas_1_raw ... xmeas_41_raw, xmv_1_raw ... xmv_11_raw (indices 0..51)
xmeas_1_mean ... xmeas_41_mean, xmv_1_mean ... xmv_11_mean (indices 52..103)
xmeas_1_delta ... xmeas_41_delta, xmv_1_delta ... xmv_11_delta (indices 104..155)
```

### 5.3 Incomplete Window Handling
When fewer than 3 observations are available (e.g. at startup or single-vector inference):
- If $t=0$: `rolling_mean` $= x_0$, `temporal_delta` $= 0.0$.
- If $t=1$: `rolling_mean` $= \text{mean}(x_0, x_1)$, `temporal_delta` $= x_1 - x_0$.

---

## 6. Preprocessing & Scaling

- A dedicated `TEPFaultPreprocessor` encapsulates a `StandardScaler` fitted strictly on the 156-feature training split ($X_{train}$).
- The fitted means and standard deviations are serialized directly within the model artifact to guarantee zero train/inference distribution shift.
- The preprocessor is never refitted during validation, testing, or production inference.

---

## 7. XGBoost Model Configuration

```yaml
framework: xgboost
version: 3.2.0
objective: multi:softprob
num_class: 22
n_estimators: 200
max_depth: 6
learning_rate: 0.08
subsample: 0.8
colsample_bytree: 0.8
tree_method: hist
eval_metric: mlogloss
random_state: 42
n_jobs: 4
```

---

## 8. Evaluation Results (Independent Held-Out Test Set)

Evaluated on 21,120 independent test samples from `d00_te.dat` through `d21_te.dat`:

| Metric | Score |
| :--- | :--- |
| **Overall Accuracy** | **69.01%** |
| **Top-3 Accuracy** | **83.22%** |
| **Macro Precision** | **73.45%** |
| **Macro Recall** | **71.07%** |
| **Macro F1-Score** | **71.05%** |
| **Weighted F1-Score** | **69.65%** |

### 8.1 Selected Per-Class F1-Scores
- `NORMAL` (Class 0): Precision = 67.18%, Recall = 58.70%, F1 = 0.6266
- `IDV(1)` (Class 1): Precision = 98.86%, Recall = 97.88%, **F1 = 0.9837**
- `IDV(2)` (Class 2): Precision = 92.48%, Recall = 96.88%, **F1 = 0.9463**
- `IDV(4)` (Class 4): Precision = 93.30%, Recall = 97.50%, **F1 = 0.9535**
- `IDV(5)` (Class 5): Precision = 95.70%, Recall = 96.99%, **F1 = 0.9634**
- `IDV(6)` (Class 6): Precision = 100.0%, Recall = 100.0%, **F1 = 1.0000**
- `IDV(7)` (Class 7): Precision = 100.0%, Recall = 100.0%, **F1 = 1.0000**
- `IDV(8)` (Class 8): Precision = 94.63%, Recall = 90.50%, **F1 = 0.9250**
- `IDV(12)` (Class 12): Precision = 89.97%, Recall = 89.75%, **F1 = 0.8986**
- `IDV(14)` (Class 14): Precision = 96.47%, Recall = 96.22%, **F1 = 0.9634**
- `IDV(17)` (Class 17): Precision = 90.22%, Recall = 89.12%, **F1 = 0.8967**
- `IDV(18)` (Class 18): Precision = 90.45%, Recall = 89.30%, **F1 = 0.8987**

### 8.2 Known Difficult Faults & Physical Explanations
In authentic TEP literature, several faults are notoriously difficult to classify because of strong closed-loop feedback controller compensation:
- **IDV(3) (D Feed Temp Step, F1: 0.1755):** The reactor jacket and feed preheater temperature controllers rapidly compensate for this step disturbance, producing minimal detectable steady-state variation in the 52 monitored variables.
- **IDV(9) (D Feed Temp Random, F1: 0.0559):** Random temperature variations are similarly masked by the thermal inertia of the reactor and the fast action of the cooling water valve.
- **IDV(15) (Condenser Cooling Water Valve Sticking, F1: 0.1764):** Valve stiction produces intermittent limit cycling that closely resembles normal operating variations until significant drift occurs.

---

## 9. Production Inference Contract

### 9.1 Status Contract
Inference calls through `ProcessFaultClassifier.classify_fault(telemetry_vector)` return an `MLAssessment` with one of the following canonical statuses:
- `OK`: Model artifact loaded and inference successfully executed.
- `MODEL_NOT_AVAILABLE`: Model artifact missing, corrupt, or model explicitly disabled.
- `INVALID_INPUT`: Telemetry input is None, empty, or non-dictionary.
- `INFERENCE_ERROR`: Unhandled runtime exception during feature transformation or prediction (contained safely).

### 9.2 Prediction Payload
```json
{
  "fault_id": 1,
  "fault_code": "IDV(1)",
  "description": "A/C Feed Ratio, B Composition Constant (Stream 4) - Step",
  "confidence": 0.9837,
  "top_candidates": [
    {"class_id": 1, "code": "IDV(1)", "description": "A/C Feed Ratio, B Composition Constant (Stream 4) - Step", "confidence": 0.9837},
    {"class_id": 8, "code": "IDV(8)", "description": "A, B, C Feed Composition (Stream 4) - Random Variation", "confidence": 0.0084},
    {"class_id": 0, "code": "NORMAL", "description": "Normal Steady-State Operation", "confidence": 0.0032}
  ],
  "probability_distribution": {
    "NORMAL": 0.0032,
    "IDV(1)": 0.9837,
    "IDV(2)": 0.0011,
    "...": 0.0001
  }
}
```

### 9.3 Stream Isolation
The classifier maintains isolated `deque(maxlen=3)` history buffers keyed by `stream_id` or `asset_id` to prevent cross-asset or cross-plant telemetry contamination. Stream history can be explicitly reset using `classifier.reset_stream(stream_id)`.

---

## 10. Model Artifact & Registry Specifications

- **Artifact Path:** `artifacts/models/process_fault_classifier/v1.0.0/model.joblib`
- **File Size:** 1,984,074 bytes (1.89 MB)
- **SHA-256 Checksum:** `736bf3414bf1509f6aae592e6b893ebf2dd1080e3c04c0807b55aa5d5923a226`
- **Registry Entry:** `artifacts/models/registry.yaml` (`status: ready`)

---

## 11. Safety & Operational Constraints

> [!CAUTION]
> **NOVA Zero-Actuation Policy:**
> `ProcessFaultClassifier` is strictly a diagnostic assistant. It provides probabilistic evidence to NOVA's reasoning layer and human operators.
> It must **NEVER**:
> 1. Issue setpoint adjustments to DCS/PLC controllers.
> 2. Actuate control valves or trip emergency safety systems (ESD/SIS).
> 3. Bypass SafetyGuard or operational constraint checks.
> 4. Initiate automated maintenance actions.

---

## 12. Reproducibility

To re-train and re-evaluate the model from raw benchmark files:
```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m ml_training.tep.train_fault_classifier
```
To run the automated test suite:
```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m pytest backend/tests/test_tep_fault_classifier.py -v
```
