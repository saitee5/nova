# NOVA Industrial Risk Engine Specification

**Owner Module:** `backend/services/industrial_risk_service.py`  
**Class Name:** `IndustrialRiskEngine`  
**Policy Version:** `1.0`  
**Operational Mode:** Deterministic, Explainable, Advisory Only

---

## 1. Core Principles

1. **Independent of ML Availability:** The risk engine produces valid, deterministic risk evaluations whether ML models return `OK`, `MODEL_NOT_AVAILABLE`, or errors.
2. **Never Blindly Sum Probabilities:** Machine learning anomaly scores and fault probabilities do NOT get arbitrarily summed into risk scores. Instead, ML outputs serve as bounded multipliers or trigger specific explainable penalty rules.
3. **Deterministic SIMOPS (Simultaneous Operations) Detection:** Evaluates compound real-world hazards, such as hot-work permits active on equipment undergoing maintenance with personnel in the zone.
4. **Strictly Advisory:** All risk assessments declare `advisory_only=True` to prevent automated actuation.

---

## 2. Risk Calculation Formula & Factor Breakdown

The composite risk score $R \in [0.0, 1.0]$ is computed as:

$$R = \min\left(1.0, \, R_{base} + \Delta R_{alarms} + \Delta R_{simops} + \Delta R_{criticality} + \Delta R_{ml}\right)$$

Where:
* **$R_{base}$:** Nominal operating baseline risk ($0.05$ for `STEADY_STATE`, $0.15$ for `RAMP_UP`/`RAMP_DOWN`, $0.40$ for `EMERGENCY`).
* **$\Delta R_{alarms}$:**
  - Critical Alarm: $+0.35$ per active unacknowledged alarm.
  - High Alarm: $+0.20$ per active alarm.
  - Medium Alarm: $+0.08$ per active alarm.
* **$\Delta R_{simops}$ (Simultaneous Operations Penalty):**
  - Hot-work permit active + high temperature/pressure equipment + personnel present in zone: $+0.25$.
  - Confined space entry during startup/shutdown: $+0.30$.
* **$\Delta R_{criticality}$:**
  - Asset Criticality `A` (Tier 1 process critical, e.g. Ethylene furnace or cracked gas compressor): $1.25\times$ scaling on alarm penalties.
* **$\Delta R_{ml}$:**
  - Only evaluated when ML status is `OK` or `SUCCESS`.
  - Anomaly score $> 0.85$: $+0.15$ with explicit contributing factor `ML_ANOMALY_HIGH`.
  - Process fault diagnosed with confidence $> 0.80$: $+0.20$ with factor `ML_FAULT_CONFIRMED:<fault_id>`.
  - If ML status is `MODEL_NOT_AVAILABLE`, $\Delta R_{ml} = 0.0$ and no penalty is assessed.

---

## 3. Severity Tiers

The calculated risk score $R$ maps to four industrial tiers:
- **LOW:** $0.00 \le R < 0.25$ (Routine nominal operation)
- **MEDIUM:** $0.25 \le R < 0.50$ (Elevated vigilance, process drift observed)
- **HIGH:** $0.50 \le R < 0.75$ (Urgent review required; supervisor notification)
- **CRITICAL:** $0.75 \le R \le 1.00$ (Immediate mitigation required; advisory safety alert triggered)
