# ProcessAnomalyDetector Evaluation Report (Version v1.1.0)

- **Model Version:** `v1.1.0`
- **Model Status:** `VALIDATED_WITH_LIMITATIONS`
- **Evaluated At:** `2026-09-12T15:20:13.591405+00:00`
- **Audit & Calibration Timestamp:** `2026-09-12T15:50:00.000000+00:00`
- **Dataset Path:** `C:\Users\Aarushi Sachdeva\OneDrive\Desktop\nova\data\curated\tep\tep_canonical.csv`
- **Dataset SHA-256:** `e375f84e32bb574c9c99234bada5498214c5e118fb568c8af83987839c87b410`
- **Training Duration:** `25.16 s`

---

## 1. Executive Summary & Aggregate Performance

### A. Full Test Set Performance (N = 98,000 Observations)

| Metric | Value | Population & Formula | Description |
| :--- | :--- | :--- | :--- |
| **False Positive Rate (FPR)** | **`9.62%`** | `FP / (FP + TN) = 6,159 / 64,000` | Aggregate false alarm rate across all normal-labeled observations |
| **Specificity (1 - FPR)** | **`90.38%`** | `TN / (FP + TN) = 57,841 / 64,000` | True negative rate across all normal-labeled observations |
| **Precision** | **`0.7123`** | `TP / (TP + FP) = 15,252 / 21,411` | Positive predictive value |
| **Recall (Detection Rate)** | **`44.86%`** | `TP / (TP + FN) = 15,252 / 34,000` | True positive rate across active fault windows |
| **F1 Score** | **`0.5505`** | `2 * (Prec * Rec) / (Prec + Rec)` | Harmonic mean of precision and recall |
| **PR-AUC** | **`0.6758`** | `Average Precision (continuous scores)` | Area under Precision-Recall curve |
| **ROC-AUC** | **`0.8055`** | `Area Under ROC (continuous scores)` | Area under Receiver Operating Characteristic curve |
| **Uncertainty Rate** | **`8.88%`** | `N(score ∈ [0.40, 0.60)) / 98,000` | Fraction of observations in ambiguous score zone `[0.40, 0.60)` |

### B. Confusion Matrix (Full Test Set)

| | Predicted NORMAL | Predicted ANOMALOUS | Total Actual |
| :--- | :--- | :--- | :--- |
| **Actual NORMAL** | `57,841` (TN) | `6,159` (FP) | **`64,000`** |
| **Actual ANOMALOUS** | `18,748` (FN) | `15,252` (TP) | **`34,000`** |
| **Total Predicted** | **`76,589`** | **`21,411`** | **`98,000`** |

---

## 2. Numerical Audit & Subpopulation Breakdown

An independent numerical audit resolved the initial discrepancy between the previously cited **0.86% FPR** and the confusion matrix **9.62% FPR**.

### A. Subpopulation Audit Table

| Subpopulation | Test Runs | Total Samples | True Negatives (TN) | False Positives (FP) | False Positive Rate (FPR) | Specificity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Pure Normal Steady-State** (`fault_id == 0`) | 50 runs | 48,000 | 47,589 | 411 | **`0.8563%` (0.86%)** | **`99.1437%` (99.14%)** |
| **Pre-Injection Baseline** (`fault_id 1..20`, $t \le 160$) | 100 runs | 16,000 | 10,252 | 5,748 | **`35.9250%` (35.93%)** | **`64.0750%` (64.08%)** |
| **Combined Normal Population** | **150 runs** | **64,000** | **57,841** | **6,159** | **`9.6234%` (9.62%)** | **`90.3766%` (90.38%)** |

### B. Root Cause of Previous Discrepancy
1. **Denominator Disparity in Summary Metrics:** The original evaluation script computed `false_positive_rate` solely over `df_test_normal` (50 runs $\times$ 960 samples = 48,000 pure normal observations), yielding $411 / 48,000 = 0.00856 \approx 0.86\%$. However, the global confusion matrix was constructed over all 98,000 observations including the 16,000 pre-injection baseline observations from the 100 fault test runs ($100 \times 160 = 16,000$).
2. **Pre-Injection Dynamics:** In the standard TEP simulation, fault runs feature transient startup dynamics and initial closed-loop controller stabilization in samples $1 \le t \le 160$ before the disturbance is injected at $t = 161$. This increased variance produces 5,748 false alarms (35.93% FAR) during the pre-injection window, elevating the overall normal false positive count from 411 to 6,159 ($6,159 / 64,000 = 9.62\%$).
3. **Grand Total Typo:** The previous confusion matrix table displayed `20` (the number of fault classes, `len(per_fault_df)`) instead of the grand total `98,000`.

Both metrics are mathematically valid within their respective domains:
- **0.86%** reflects the **steady-state false alarm rate** on pure unperturbed operations.
- **9.62%** reflects the **full-evaluation false alarm rate** across the complete test dataset including simulation initialization transients.

---

## 3. Threshold Calibration & Architecture Parameters

- **PCA Retained Components:** `31` (explaining `90.13%` cumulative variance)
- **PCA Q (SPE) Threshold (99th percentile):** `11.8469`
- **PCA Hotelling T^2 Threshold (99th percentile):** `52.1457`
- **Isolation Forest Threshold (1st percentile):** `0.0006`
- **Decision Logic:**
  - `NORMAL`: Anomaly Score $< 0.40$
  - `UNCERTAIN`: Anomaly Score $\in [0.40, 0.60)$
  - `ANOMALOUS`: Anomaly Score $\ge 0.60$

---

## 4. Per-Fault Breakdown & Observability Analysis

| Fault ID | Code | Description | Active Detection Rate | Delay (Samples) | Delay (Minutes) | Observability Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `1` | `IDV(1)` | A/C Feed Ratio, B Composition Constant (Stream 4) - Step | **88.6%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `2` | `IDV(2)` | B Composition, A/C Ratio Constant (Stream 4) - Step | **100.0%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `3` | `IDV(3)` | D Feed Temp (Stream 2) - Step | **2.3%** | `246.6` | `739.8 min` | `DIFFICULT_UNOBSERVABLE` |
| `4` | `IDV(4)` | Reactor Cooling Water Inlet Temp - Step | **5.9%** | `138.2` | `414.6 min` | `DIFFICULT_UNOBSERVABLE` |
| `5` | `IDV(5)` | Condenser Cooling Water Inlet Temp - Step | **10.3%** | `6.0` | `18.0 min` | `DIFFICULT_UNOBSERVABLE` |
| `6` | `IDV(6)` | A Feed Loss (Stream 1) - Step | **100.0%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `7` | `IDV(7)` | C Header Pressure Loss - Reduced Availability (Stream 4) - Step | **50.9%** | `0.0` | `0.0 min` | `WEAKLY_DETECTABLE` |
| `8` | `IDV(8)` | A, B, C Feed Composition (Stream 4) - Random Variation | **99.8%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `9` | `IDV(9)` | D Feed Temp (Stream 2) - Random Variation | **2.8%** | `235.4` | `706.2 min` | `DIFFICULT_UNOBSERVABLE` |
| `10` | `IDV(10)` | C Feed Temp (Stream 4) - Random Variation | **21.7%** | `17.2` | `51.6 min` | `DIFFICULT_UNOBSERVABLE` |
| `11` | `IDV(11)` | Reactor Cooling Water Inlet Temp - Random Variation | **6.5%** | `116.2` | `348.6 min` | `DIFFICULT_UNOBSERVABLE` |
| `12` | `IDV(12)` | Condenser Cooling Water Inlet Temp - Random Variation | **99.9%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `13` | `IDV(13)` | Reaction Kinetics - Slow Drift | **99.7%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `14` | `IDV(14)` | Reactor Cooling Water Valve - Sticking | **17.4%** | `36.4` | `109.2 min` | `DIFFICULT_UNOBSERVABLE` |
| `15` | `IDV(15)` | Condenser Cooling Water Valve - Sticking | **2.0%** | `242.4` | `727.2 min` | `DIFFICULT_UNOBSERVABLE` |
| `16` | `IDV(16)` | Unknown Disturbance A | **12.2%** | `69.4` | `208.2 min` | `DIFFICULT_UNOBSERVABLE` |
| `17` | `IDV(17)` | Unknown Disturbance B | **53.1%** | `9.6` | `28.8 min` | `WEAKLY_DETECTABLE` |
| `18` | `IDV(18)` | Unknown Disturbance C | **100.0%** | `0.0` | `0.0 min` | `RELIABLY_DETECTABLE` |
| `19` | `IDV(19)` | Unknown Disturbance D | **3.9%** | `167.0` | `501.0 min` | `DIFFICULT_UNOBSERVABLE` |
| `20` | `IDV(20)` | Unknown Disturbance E | **20.1%** | `12.6` | `37.8 min` | `DIFFICULT_UNOBSERVABLE` |

---

## 5. Honest Operational Limitations & Fault Observability Discussion

### A. Reliably Detectable Faults
Faults such as **IDV(1), IDV(2), IDV(6), IDV(8), IDV(12), IDV(13), IDV(18)** cause significant deviations in reactor/separator pressures, temperatures, and feed compositions. The PCA subspace residual $Q$ and Isolation Forest detect these within 0–6 minutes of injection with $>85\%$ detection rates.

### B. Classical TEP Weakly Observable / Difficult Faults
Consistent with published literature on the Tennessee Eastman benchmark (Downs & Vogel 1993, Yin et al. 2012, Russell et al. 2000):
- **IDV(3)** (D Feed Temp Step) and **IDV(9)** (D Feed Temp Random Variation): Feed D temperature variations are compensated almost entirely by the upstream temperature controller without inducing significant downstream process variance.
- **IDV(15)** (Condenser Cooling Water Valve Sticking): The condenser cooling valve sticking effect is compensated by the cooling water flow loop, resulting in minimal statistical deviation in continuous measurements.

### C. Operational Advice
When `anomaly_status == UNCERTAIN`, the digital-twin advisory layer should combine `ProcessAnomalyDetector` with downstream specialized diagnostic classifiers (`ProcessFaultClassifier`) and historical RAG memory packages.