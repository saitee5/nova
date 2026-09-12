# NOVA ML Data Requirements & Ingestion Specifications

**Document Version:** 1.0  
**Domain:** Industrial Petrochemical, Chemical & Refining Facilities  
**Scope:** Specification of datasets required for training, fine-tuning, and evaluating the 4 core NOVA ML models.

---

## 1. Required Data Domains

To enable robust, explainable, and production-grade ML inference, future dataset collection must encompass the following operational domains:

1. **Process Telemetry (Continuous Time-Series):**
   - **Temperatures:** Coil outlet temperatures (COT), tube metal skin temperatures, flue gas, radiant box, convection section, compressor suction/discharge temperatures.
   - **Pressures:** Suction/discharge headers, furnace firebox draft pressure, TLE differential pressures, fuel gas manifold pressure.
   - **Flow Rates:** Hydrocarbon feed mass flow, dilution steam flow, fuel gas flow rate, quench oil injection flow, BFW circulating rates.
   - **Liquid Levels:** Steam drum level, flash drum levels, knock-out drum levels, fractionator bottom levels.
   - **Stream Compositions:** Online gas chromatograph analysis (feed ethane/propane ratio, tail gas hydrogen/methane, cracked gas composition).
   - **Valve Positions & Actuator Signals:** Fuel control valve %, draft damper opening %, quench valve %, anti-surge recycle valve %.
   - **Mechanical Load & Vibration:** Compressor shaft speed (RPM), axial displacement, radial vibration (X/Y proximity probes), motor drive MW load.
   - **Differential Pressure:** Filter differential pressures, tube pass $\Delta P$, catalyst bed $\Delta P$.

2. **Operating Mode Context:**
   - Categorical state: `STEADY_STATE`, `RAMP_UP`, `RAMP_DOWN`, `DEC_FEED`, `DECOKING`, `TURNDOWN`, `TRIP`, `EMERGENCY_SHUTDOWN`.

3. **Asset & Equipment Metadata:**
   - Asset IDs, design design limits (MAWP, design temp), metallurgy (e.g., HP-40 Nb modified microalloy), commissioning dates, historical run lengths.

4. **Alarm & Event History:**
   - Timestamp, tag name, alarm priority (LOW, MEDIUM, HIGH, CRITICAL), trigger value, trip limit, acknowledge timestamp, return-to-normal timestamp.

5. **Maintenance & Inspection Logs:**
   - Decoking history, mechanical pigging logs, tube thickness UT measurements, burner tip replacements, valve rebuild records.

6. **Permit-to-Work (PTW) Records:**
   - Active work permits, hot work certificates, confined space entry, isolation certificates, associated equipment, validity windows.

7. **Personnel Occupancy & Zone Presence:**
   - RFID / gate badge counts per battery limit zone, headcount during SIMOPS, evacuation mustered counts.

8. **Incident & Root-Cause Labels:**
   - Verified post-incident investigation reports, verified root-cause categorization, incident duration, loss metrics.

---

## 2. Planned Training Datasets & Governance Specification

### Dataset 1: Tennessee Eastman Process (TEP) Benchmark
* **Primary Target:** Anomaly Detection (`ProcessAnomalyDetector`) and Fault Classification (`ProcessFaultClassifier`).
* **Source:** Downs & Vogel (1993) Tennessee Eastman Industrial Challenge Problem; Rieth et al. (2017) extended simulation dataset.
* **Provenance:** `SIMULATED_BENCHMARK`
* **License:** Public Academic / MIT
* **Schema:**
  - 52 continuous process variables: 41 measured variables (XMEAS 1-41) + 11 manipulated variables (XMV 1-11).
  - Categorical fault flag: Normal operation + 21 programmed process disturbances (IDV 1 to 21).
* **Sampling Frequency & Time Resolution:** 3-minute sampling interval across simulation runs spanning 48 hours to 96 hours.
* **Units:** SI / Engineering units ($kPa$, $m^3/hr$, $^\circ\text{C}$, $kg/hr$, $mol\%$).
* **Missingness & Noise:** Continuous numerical stream with Gaussian measurement noise; no missing values in baseline synthetic generator.
* **Label Definition:** Multiclass categorical target $\{0, 1, \dots, 21\}$, where 0 is nominal steady state and 1–21 correspond to specific disturbance origins.
* **Limitations:** Simulated kinetics; does not capture real furnace coking or physical degradation over multi-month timescales.
* **Validation Strategy:** Split by simulation run seeds (70% train, 15% validation, 15% test). Never split randomly across time within a single run to prevent data leakage.

---

### Dataset 2: Ethylene Cracking Furnace Run-Length Historian
* **Primary Target:** Furnace COT Predictor (`FurnaceCOTPredictor`) and Tube Skin Predictor (`TubeTemperaturePredictor`).
* **Source:** Petrochemical plant historian (or validated high-fidelity simulator benchmark).
* **Provenance:** `REAL_INDUSTRIAL_DATA` (or `SIMULATED_BENCHMARK` prior to plant access).
* **License:** Proprietary Industrial Consortium Agreement / Safe synthetic twin.
* **Schema:**
  - Multi-pass feed flows, steam ratios, coil outlet temperatures, fuel flow, excess air / $O_2$ in flue gas.
  - Multi-point pyrometer / tube skin thermocouple array readings ($T_{skin, 1 \dots N}$).
  - Cumulative run length (days since decoke).
* **Sampling Frequency & Time Resolution:** 1-minute SCADA averages aggregated to 5-minute rolling feature windows.
* **Units:** Degrees Celsius ($^\circ\text{C}$), Metric tons/hr, $Nm^3/hr$, $kPa$.
* **Missingness & Noise:** Sensor outages, bad quality flags (`quality != 'GOOD'`), drift due to thermocouple aging. Requires forward-fill up to 15 minutes and outlier filtering.
* **Label Definition:**
  - Continuous scalar: Multi-horizon COT forecast at $t+15\text{m}, t+30\text{m}, t+60\text{m}$.
  - Continuous vector: Maximum tube skin temperature across radiant coils.
* **Limitations:** Highly seasonal; influenced by ambient air temperature and fuel gas calorific variation.
* **Validation Strategy:** Chronological block splitting. Train on historical run cycles $1 \dots K-2$, validate on cycle $K-1$, test on final cycle $K$.

---

## 3. Data Ingestion & Preprocessing Quality Gates

Before any dataset is admitted into the model training pipeline, it must satisfy:
1. **Provenance Verification:** All raw files must have an accompanying cryptographic SHA-256 hash and metadata record in `artifacts/data/manifest.yaml`.
2. **Quality Scrubbing:** Telemetry records with bad sensor quality flags (`BAD`, `UNCERTAIN`, `DISCONNECTED`) must be isolated and imputed or masked.
3. **Data Leakage Check:** Feature engineering functions (e.g. rolling mean/std) must be strictly causal, computing statistics only using past observations ($t \le T$).
