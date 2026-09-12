# Tennessee Eastman Process (TEP) Anomaly Detection System

**Model Identifier:** `ProcessAnomalyDetector`  
**Model Version:** `v1.0.0`  
**Registry Key:** `process_anomaly_detector`  
**Status:** `ready`  
**Artifact:** `artifacts/models/process_anomaly_detector/v1.0.0/model.joblib`  
**Algorithms:** Principal Component Analysis (Hotelling's $T^2$ + SPE / $Q$) + Isolation Forest

---

## 1. Dataset & Benchmark Specification

The model is trained and evaluated on the standardized chemical process benchmark developed by Downs & Vogel (1993) and maintained by Prof. Richard D. Braatz (UIUC/MIT):

* **Source:** Prof. Richard Braatz Research Group, MIT / University of Illinois.
* **Origin Files:**
  - `d00.dat`: Fault-free continuous process training run ($52 \text{ variables} \times 500 \text{ samples}$).
  - `d00_te.dat`: Fault-free continuous testing run ($960 \text{ samples} \times 52 \text{ variables}$, 48 hours).
  - `d01_te.dat` to `d05_te.dat`: Testing runs for Faults 1 to 5 ($960 \text{ samples} \times 52 \text{ variables}$ each, disturbance introduced at sample 160).
* **Sampling Resolution:** 3 minutes per observation interval.
* **File Hashes (SHA-256):**
  - `d00.dat`: `4c3c0b11eefacf93e5d2529e2866d7a625e37aa9153d0f95fae17a6c9e560deb`
  - `d00_te.dat`: `57d56da4199e3d73582855d810be1d13d931386fd728bf1694798c7b0a03678c`
  - `d01_te.dat`: `e7e6992fb39664e739fccbc001a1c5d5f7cb21829544f734ca3f282c26f680e5`
  - `d02_te.dat`: `a34bd9c3693fa96bd3ee533fb7fbe29a9d226a4e3250b585ef1308e1136dbfb0`
  - `d03_te.dat`: `b7bf6f2ed7cff0a5577898b009edd252b9bdf6ee9ff7dbeacf9af9aa4c6abace`
  - `d04_te.dat`: `1ccb488dd5feac11aad54623451168abef066229e685872597897800363916f9`
  - `d05_te.dat`: `1def7258a2865aeead699d52c8cf926fbf34c1467aaf298121987ab858fd0888`

---

## 2. Process Variables (52 Canonical Features)

The feature space consists of 41 continuous process measurements (`xmeas_1` through `xmeas_41`) and 11 manipulated variables (`xmv_1` through `xmv_11`):

| Variable ID | Description | Nominal Mean | Engineering Units |
|:---|:---|:---|:---|
| `xmeas_1` | A Feed (stream 1) | 0.2505 | kscmh |
| `xmeas_2` | D Feed (stream 2) | 3664.1 | kg/hr |
| `xmeas_3` | E Feed (stream 3) | 4505.3 | kg/hr |
| `xmeas_4` | A and C Feed (stream 4) | 9.349 | kscmh |
| `xmeas_5` | Recycle Flow (stream 8) | 26.89 | kscmh |
| `xmeas_6` | Reactor feed rate (stream 6) | 42.34 | kscmh |
| `xmeas_7` | Reactor pressure | 2705.1 | kPa gauge |
| `xmeas_8` | Reactor level | 75.00 | % |
| `xmeas_9` | Reactor temperature | 120.40 | °C |
| `xmeas_10` | Purge rate (stream 9) | 0.337 | kscmh |
| `xmeas_11` | Separator temperature | 80.11 | °C |
| `xmeas_12` | Separator level | 50.00 | % |
| `xmeas_13` | Separator pressure | 2633.7 | kPa gauge |
| `xmeas_14` | Separator underflow (stream 10) | 25.16 | m³/hr |
| `xmeas_15` | Stripper level | 50.00 | % |
| `xmeas_16` | Stripper pressure | 2005.2 | kPa gauge |
| `xmeas_17` | Stripper underflow (stream 11) | 22.95 | m³/hr |
| `xmeas_18` | Stripper temperature | 65.73 | °C |
| `xmeas_19` | Stripper steam flow | 230.5 | kg/hr |
| `xmeas_20` | Compressor work | 341.5 | kW |
| `xmeas_21` | Reactor cooling water outlet temp | 94.60 | °C |
| `xmeas_22` | Separator cooling water outlet temp | 77.29 | °C |
| `xmeas_23..41`| Component compositions (Analyzers A to H) | Various | mol % |
| `xmv_1..11` | Manipulated valve positions (D, E, A feeds, recycle, purge, etc.) | Various | % open |

---

## 3. Data Splitting & Leakage-Safe Calibration

To ensure unbiased threshold determination and zero data leakage:
1. **Training Split ($X_{train}$):** First 80% of `d00.dat` chronologically (400 samples). Used exclusively for fitting `StandardScaler`, `PCA`, and `IsolationForest`.
2. **Validation / Calibration Split ($X_{val}$):** Remaining 20% of `d00.dat` chronologically (100 samples). Used exclusively to compute and freeze statistical thresholds ($Q_{thresh}$, $T^2_{thresh}$, $\text{if\_threshold}$).
3. **Held-Out Test Sets:**
   - `d00_te.dat` (960 normal samples)
   - `d01_te.dat` through `d05_te.dat` (960 samples each, fault starting at sample 160)
   Thresholds are completely frozen before any evaluation on test sets occurs.

---

## 4. Modeling Methodology & Equations

### Preprocessing
Standardized using z-score normalization based strictly on $X_{train}$:
$$Z = \frac{X - \mu_{train}}{\sigma_{train}}$$

### PCA Subspace Process Monitoring
* **Components Selected:** 31 components (explaining 90.54% cumulative variance).
* **Squared Prediction Error (SPE / $Q$-statistic):**
  $$Q = \|Z - \hat{Z}\|_2^2 = \sum_{j=1}^{52} (Z_j - \hat{Z}_j)^2$$
  *Frozen Threshold ($Q_{thresh}$, 99th pct on validation):* **17.5129**
* **Hotelling's $T^2$ Statistic:**
  $$T^2 = \sum_{i=1}^{31} \frac{t_i^2}{\lambda_i}$$
  *Frozen Threshold ($T^2_{thresh}$, 99th pct on validation):* **51.5462**
* **Calibrated PCA Score ($S_{PCA} \in [0.0, 1.0]$):**
  $$r_{PCA} = \max\left(\frac{Q}{Q_{thresh}}, \frac{T^2}{T^2_{thresh}}\right)$$
  $$S_{PCA} = 1.0 - 0.5^{r_{PCA}} = 1.0 - \exp(-\ln(2) \cdot r_{PCA})$$
  *(At control limit $r_{PCA} = 1.0$, $S_{PCA} = 0.50$)*

### Isolation Forest Outlier Detection
* **Hyperparameters:** `n_estimators=100`, `contamination=0.01`, `random_state=42`, `n_jobs=-1`.
* **Decision Function Calibration:**
  *Frozen Threshold ($\text{if\_threshold}$, 1st pct on validation):* **-0.0186** ($\sigma_{df} = 0.0273$).
* **Calibrated IF Score ($S_{IF} \in [0.0, 1.0]$):**
  $$S_{IF} = \frac{1}{1 + \exp\left(10 \cdot \frac{df - \text{if\_threshold}}{\sigma_{df}}\right)}$$
  *(At threshold $df = \text{if\_threshold}$, $S_{IF} = 0.50$)*

### Composite Anomaly Decision
$$S_{combined} = 0.5 \cdot S_{PCA} + 0.5 \cdot S_{IF}$$
$$\text{is\_anomaly} = (S_{combined} \ge 0.50) \;\lor\; (S_{PCA} \ge 0.50) \;\lor\; (S_{IF} \ge 0.50)$$

---

## 5. Empirical Evaluation Results

Evaluated on 48-hour continuous test runs (960 samples each, 3-min sampling interval):

| Scenario | Description | Total Samples | Pre-Fault FPR | Post-Fault Recall | Precision | F1-Score | Detection Delay |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `normal_d00_te` | Nominal Steady-State | 960 | **2.92%** | N/A | N/A | N/A | None (Nominal) |
| `fault_01_te` | A/C Feed Ratio Step | 960 | 0.62% | **86.12%** | 0.998 | **0.925** | 6 samples (18 min) |
| `fault_02_te` | B Composition Step | 960 | 0.00% | **97.62%** | 1.000 | **0.988** | 14 samples (42 min) |
| `fault_03_te` | D Feed Temp Step | 960 | 4.38% | 8.00% | 0.901 | 0.147 | 9 samples (27 min) |
| `fault_04_te` | Reactor Cooling Water Temp Step | 960 | 0.62% | 10.38% | 0.988 | 0.188 | 63 samples (189 min) |
| `fault_05_te` | Condenser Cooling Water Step | 960 | 0.62% | 29.62% | 0.996 | 0.457 | 6 samples (18 min) |

*Note on Faults 3 & 4:* In Tennessee Eastman literature, Faults 3, 4, 9, and 15 are known as low-observability disturbances because the closed-loop PI controllers vigorously compensate for the temperature step without driving process variables into anomalous variance regimes.

---

## 6. Reproducibility & Pipeline Usage

### 1. Download Dataset
```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m ml_training.tep.download_dataset
```

### 2. Run Reproducible Training
```powershell
& "C:\Users\Hitendra Singh\AppData\Local\Programs\Python\Python311\python.exe" -m ml_training.tep.train_anomaly_detector
```

### 3. Production Inference Example
```python
from backend.ml.anomaly.detector import ProcessAnomalyDetector

detector = ProcessAnomalyDetector()
sample_telemetry = {"xmeas_1": 0.2498, "xmeas_2": 3642.6, "xmeas_7": 2705.0}

assessment = detector.detect_anomaly(sample_telemetry)
assert assessment.status == "OK"
print(f"Anomaly Score: {assessment.score} | Detected: {assessment.prediction['is_anomaly']}")
```
