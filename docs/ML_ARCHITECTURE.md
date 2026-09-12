# NOVA Pluggable ML Architecture

**System:** NOVA Industrial AI Co-Pilot & Safety Advisory Platform  
**Document Version:** 1.0  
**Phase:** Scaffolding & Contract Lock (Pre-Training)

---

## 1. Design Principles

1. **Pluggable & Graceful Degradation:** The backend and pipeline run seamlessly when model weights are not present. When an artifact is missing, each detector returns a structured `MLAssessment` with:
   ```json
   {
     "status": "MODEL_NOT_AVAILABLE",
     "score": 0.0,
     "confidence": 0.0,
     "prediction": null
   }
   ```
2. **Zero Fabrication:** No random numbers, fake scores, or hardcoded mock predictions are returned under any circumstances.
3. **Strongly Typed Result Envelopes:** All models adhere to standard industrial assessment schemas containing model version, execution latency, features used, and provenance.
4. **Decoupled Training & Inference:** Models can be trained offline using benchmarks (e.g. Tennessee Eastman Process, plant historians) and dropped into the artifact registry without altering pipeline or service code.

---

## 2. The Four Planned ML Models

### 1. Process Anomaly Detector (`ProcessAnomalyDetector`)
* **Target Domain:** Continuous chemical and petrochemical processes (Tennessee Eastman Process benchmark).
* **Planned Algorithm:**
  - Dimensionality Reduction / Subspace Monitoring: Principal Component Analysis (PCA) with Hotelling's $T^2$ and Squared Prediction Error ($Q$/SPE) metrics.
  - High-dimensional density estimation: Isolation Forest ensemble.
* **Input Schema:** Standardized telemetry vector of continuous process variables (temperatures, pressures, flow rates, liquid levels, component mole fractions).
* **Output Envelope:**
  - `status`: `OK` | `MODEL_NOT_AVAILABLE` | `INVALID_INPUT` | `INFERENCE_ERROR`
  - `score`: Anomaly magnitude (0.0 to 1.0, normalized against 99th percentile control limit)
  - `prediction`: Boolean indicator (`True` if anomalous)
  - `features_used`: List of tag names evaluated

### 2. Process Fault Classifier (`ProcessFaultClassifier`)
* **Target Domain:** Root-cause diagnosis of process upsets (21 standard TEP fault modes + normal operation).
* **Planned Algorithm:** Gradient Boosted Trees (XGBoost multiclass classifier with softmax probability output).
* **Input Schema:** Windowed feature vector containing normalized values, rolling deltas, and rates of change across all 52 TEP process variables.
* **Output Envelope:**
  - `status`: `OK` | `MODEL_NOT_AVAILABLE` | `INVALID_INPUT` | `INFERENCE_ERROR`
  - `prediction`: Identified fault ID (e.g., `IDV(1)`: A/C Feed Ratio step change, `IDV(6)`: A Feed Loss)
  - `score` / `confidence`: Calibrated class probability (0.0 to 1.0)
  - `labels`: Top-3 candidate fault classes with respective probabilities

### 3. Furnace Coil Outlet Temperature (COT) Predictor (`FurnaceCOTPredictor`)
* **Target Domain:** Ethylene cracking furnaces / reforming furnaces.
* **Planned Algorithm:**
  - Baseline: XGBoost Regressor with lag features.
  - Deep Learning Candidate: 1D-CNN feature extractor + Bidirectional LSTM + Multi-Head Temporal Attention mechanism for multi-horizon forecast.
* **Input Schema:** Feed hydrocarbon mass flow, dilution steam-to-oil ratio, fuel gas flow, burner pressures, damper positions, and historical COT readings across individual furnace passes.
* **Output Envelope:**
  - `status`: `OK` | `MODEL_NOT_AVAILABLE` | `INVALID_INPUT` | `INFERENCE_ERROR`
  - `prediction`: Predicted COT in °C (e.g. $842.5^\circ\text{C}$)
  - `score`: Forecast horizon confidence / prediction interval width

### 4. Tube Skin Temperature Predictor (`TubeTemperaturePredictor`)
* **Target Domain:** Pyrometry, tube coking, and localized radiant zone hotspot detection.
* **Planned Algorithm:**
  - Feature Compression: LSTM Autoencoder extracting compressed latent temporal trajectories.
  - Hotspot Regression: Artificial Neural Network (ANN) regression head mapping latent representations to individual tube temperature profiles.
* **Input Schema:** Multi-point tube skin thermocouple measurements, optical pyrometer readings, firing duty, and total run length in operating hours.
* **Output Envelope:**
  - `status`: `OK` | `MODEL_NOT_AVAILABLE` | `INVALID_INPUT` | `INFERENCE_ERROR`
  - `prediction`: Maximum tube skin temperature across passes (°C)
  - `labels`: Identification of high-risk tube passes nearing metallurgical limits (e.g. $1080^\circ\text{C}$ threshold)

---

## 3. Transition from `MODEL_NOT_AVAILABLE` to Production Artifact

When real model weights are trained:
1. Place serialized weights into `artifacts/models/<model_name>/v1.0.0/model.joblib` or `model.pt`.
2. Update `artifacts/models/registry.yaml` status to `ready` and record artifact paths, dataset hashes, and evaluation metrics.
3. The model constructor automatically detects the file path, loads the weights, and transitions from emitting `MODEL_NOT_AVAILABLE` to executing real inference.
4. **No modifications to `MLPipeline`, `PlantStateService`, `IndustrialRiskEngine`, or API routes are required.**
