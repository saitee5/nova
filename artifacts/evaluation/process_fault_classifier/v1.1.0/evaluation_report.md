# ProcessFaultClassifier Evaluation Report (Version v1.1.0)

- **Model Version:** `v1.1.0`
- **Model Status:** `VALIDATED_WITH_LIMITATIONS`
- **Evaluated At:** `2026-09-12T16:02:57.551644+00:00`
- **Dataset Path:** `C:\Users\Aarushi Sachdeva\OneDrive\Desktop\nova\data\curated\tep\tep_canonical.csv`
- **Dataset SHA-256:** `e375f84e32bb574c9c99234bada5498214c5e118fb568c8af83987839c87b410`
- **Training Duration:** `61.2 s`

---

## 1. Executive Summary & Aggregate Performance

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Overall Accuracy** | **`80.28%`** | Exact 21-class top-1 classification accuracy |
| **Macro Precision** | `0.8324` | Unweighted mean precision across all 21 classes |
| **Macro Recall** | `0.8085` | Unweighted mean recall across all 21 classes |
| **Macro F1 Score** | **`0.8164`** | Unweighted harmonic mean of precision and recall |
| **Weighted F1 Score** | `0.8051` | Support-weighted harmonic mean across classes |
| **Top-3 Accuracy** | **`91.63%`** | True fault class is within top-3 model recommendations |
| **Top-5 Accuracy** | `96.95%` | True fault class is within top-5 model recommendations |
| **Multi-Class Log Loss** | `0.5900` | Cross-entropy penalization for probability miscalibration |
| **Brier Score** | `0.2484` | Mean squared probability error (lower is better) |
| **Mean Confidence** | `76.27%` | Average probability assigned to top-1 predicted class |
| **Low Confidence Rate** | `24.27%` | Predictions with confidence $< 0.40$ (uncertain zone) |
| **High-Confidence Errors** | `339` | Incorrect predictions where model confidence was $\ge 0.70$ |

---

## 2. Dataset Split & Simulation-Run Isolation

- **Curated Dataset:** `data/curated/tep/tep_canonical.csv`
- **Split Strategy:** Strict `simulation_run` entity isolation (no cross-run sample contamination)
- **Train Partition:** Runs `10` per class (`104,600` samples)
- **Validation Partition:** Runs `2` per class (`20,920` samples)
- **Independent Test Partition:** Runs `4` per class (`41,840` samples)
- **Transition Window Handling:** Samples $t \in \{20, 21\}$ excluded around fault injection boundary to prevent transient boundary artifact learning.
- **Pre-injection Baseline ($t \le 19$):** Assigned class `0` (`NORMAL`).
- **Active Fault Regime ($t \ge 22$):** Assigned fault scenario class `1..20`.

---

## 3. Per-Class Performance Breakdown (21 Classes)

| Class ID | Code | Description | Type | Support | Precision | Recall | F1 Score | Mean Conf | Top Confusion Partner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0` | `NORMAL` | Normal Steady-State Operation | Normal | `3,520` | `0.4314` | `0.6614` | **`0.5222`** | `0.43` | `IDV(3)` (529) |
| `1` | `IDV(1)` | A/C Feed Ratio, B Composition Constant (Stream 4) - Step | Step | `1,916` | `1.0000` | `0.9943` | **`0.9971`** | `0.99` | `IDV(8)` (9) |
| `2` | `IDV(2)` | B Composition, A/C Ratio Constant (Stream 4) - Step | Step | `1,916` | `0.9828` | `0.9854` | **`0.9841`** | `0.99` | `NORMAL` (21) |
| `3` | `IDV(3)` | D Feed Temp (Stream 2) - Step | Step | `1,916` | `0.2981` | `0.4494` | **`0.3585`** | `0.28` | `NORMAL` (650) |
| `4` | `IDV(4)` | Reactor Cooling Water Inlet Temp - Step | Step | `1,916` | `0.9719` | `0.9922` | **`0.9819`** | `0.98` | `IDV(11)` (15) |
| `5` | `IDV(5)` | Condenser Cooling Water Inlet Temp - Step | Step | `1,916` | `0.9830` | `0.9953` | **`0.9891`** | `0.98` | `IDV(12)` (9) |
| `6` | `IDV(6)` | A Feed Loss (Stream 1) - Step | Step | `1,916` | `1.0000` | `1.0000` | **`1.0000`** | `1.00` | `None` (0) |
| `7` | `IDV(7)` | C Header Pressure Loss - Reduced Availability (Stream 4) - Step | Step | `1,916` | `1.0000` | `0.9995` | **`0.9997`** | `1.00` | `IDV(19)` (1) |
| `8` | `IDV(8)` | A, B, C Feed Composition (Stream 4) - Random Variation | Random | `1,916` | `0.9725` | `0.8659` | **`0.9161`** | `0.82` | `IDV(12)` (68) |
| `9` | `IDV(9)` | D Feed Temp (Stream 2) - Random Variation | Random | `1,916` | `0.2231` | `0.1211` | **`0.1570`** | `0.28` | `NORMAL` (793) |
| `10` | `IDV(10)` | C Feed Temp (Stream 4) - Random Variation | Random | `1,916` | `0.8611` | `0.7573` | **`0.8059`** | `0.61` | `NORMAL` (176) |
| `11` | `IDV(11)` | Reactor Cooling Water Inlet Temp - Random Variation | Random | `1,916` | `0.9621` | `0.9269` | **`0.9442`** | `0.92` | `IDV(4)` (55) |
| `12` | `IDV(12)` | Condenser Cooling Water Inlet Temp - Random Variation | Random | `1,916` | `0.8992` | `0.9222` | **`0.9106`** | `0.88` | `IDV(18)` (32) |
| `13` | `IDV(13)` | Reaction Kinetics - Slow Drift | Drift | `1,916` | `0.9740` | `0.8220` | **`0.8916`** | `0.83` | `NORMAL` (94) |
| `14` | `IDV(14)` | Reactor Cooling Water Valve - Sticking | Sticking | `1,916` | `1.0000` | `0.9995` | **`0.9997`** | `0.99` | `IDV(11)` (1) |
| `15` | `IDV(15)` | Condenser Cooling Water Valve - Sticking | Sticking | `1,916` | `0.2580` | `0.1853` | **`0.2157`** | `0.28` | `NORMAL` (782) |
| `16` | `IDV(16)` | Unknown Disturbance A | Unknown | `1,916` | `0.9384` | `0.8105` | **`0.8698`** | `0.71` | `NORMAL` (104) |
| `17` | `IDV(17)` | Unknown Disturbance B | Unknown | `1,916` | `0.9966` | `0.9233` | **`0.9585`** | `0.93` | `NORMAL` (68) |
| `18` | `IDV(18)` | Unknown Disturbance C | Unknown | `1,916` | `0.9805` | `0.8638` | **`0.9184`** | `0.83` | `NORMAL` (117) |
| `19` | `IDV(19)` | Unknown Disturbance D | Unknown | `1,916` | `0.8793` | `0.8857` | **`0.8825`** | `0.81` | `IDV(20)` (71) |
| `20` | `IDV(20)` | Unknown Disturbance E | Unknown | `1,916` | `0.8676` | `0.8173` | **`0.8417`** | `0.76` | `NORMAL` (120) |

---

## 4. Error Analysis & Confusion Partners

### A. Top Confused Fault Pairs

| Actual Fault | Predicted Fault | Misclassified Observations | Error Rate of Actual |
| :--- | :--- | :--- | :--- |
| `IDV(9)` | `NORMAL` | `793` | `41.39%` |
| `IDV(15)` | `NORMAL` | `782` | `40.81%` |
| `IDV(3)` | `NORMAL` | `650` | `33.92%` |
| `IDV(9)` | `IDV(3)` | `552` | `28.81%` |
| `NORMAL` | `IDV(3)` | `529` | `15.03%` |
| `IDV(15)` | `IDV(3)` | `454` | `23.70%` |
| `NORMAL` | `IDV(15)` | `293` | `8.32%` |
| `IDV(9)` | `IDV(15)` | `261` | `13.62%` |
| `NORMAL` | `IDV(9)` | `251` | `7.13%` |
| `IDV(15)` | `IDV(9)` | `227` | `11.85%` |

### B. Difficult / Low-Observability Fault Classes

- **`IDV(3)`** (Recall: `44.9%`): Frequently confused with `NORMAL`. Consistent with chemical engineering literature on TEP (Downs & Vogel 1993, Russell et al. 2000), where closed-loop controllers absorb the disturbance with minimal steady-state sensor deviation.
- **`IDV(9)`** (Recall: `12.1%`): Frequently confused with `NORMAL`. Consistent with chemical engineering literature on TEP (Downs & Vogel 1993, Russell et al. 2000), where closed-loop controllers absorb the disturbance with minimal steady-state sensor deviation.
- **`IDV(15)`** (Recall: `18.5%`): Frequently confused with `NORMAL`. Consistent with chemical engineering literature on TEP (Downs & Vogel 1993, Russell et al. 2000), where closed-loop controllers absorb the disturbance with minimal steady-state sensor deviation.

### C. High-Confidence Error Diagnosis

Across all `41,840` held-out test observations, there are `339` instances (0.81%) where the model assigned probability $\ge 0.70$ to an incorrect fault class. In operational deployment, the digital-twin advisory layer requires a confidence margin $\ge 0.20$ before executing automated advisory actions.

---

## 5. Operational Recommendations & Digital-Twin Advisory Policy

1. **Primary Diagnosis (`HIGH_CONFIDENCE`):** Probability $\ge 0.70$ and margin $\ge 0.20$. Actionable for digital twin root-cause recommendations.
2. **Secondary Diagnosis (`MODERATE_CONFIDENCE`):** Probability $\in [0.40, 0.70)$. Consult Top-3 candidates list.
3. **Uncertain State (`LOW_CONFIDENCE_UNCERTAIN`):** Probability $< 0.40$. Defer to `ProcessAnomalyDetector` and retrieve historical RAG incident packages.