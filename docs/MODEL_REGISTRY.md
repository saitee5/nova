# NOVA Model Registry Specification

**Registry File:** `artifacts/models/registry.yaml`  
**Owner Module:** `backend/ml/registry/registry.py`  
**Class Name:** `ModelRegistry`

---

## 1. Registry Architecture

The Model Registry provides immutable cataloging and lifecycle management for all predictive models deployed in NOVA. It decouples model storage paths, dataset lineage, and evaluation metrics from application code.

### Supported Lifecycle Statuses
- `not_trained`: Placeholder registered; contracts defined; no model artifact created yet.
- `training`: Actively undergoing offline or cluster training.
- `candidate`: Training complete; awaiting automated validation & canary testing.
- `ready`: Validated and available for production inference.
- `deprecated`: Replaced by a newer version; preserved for historical auditability.

---

## 2. Registry Schema (`registry.yaml`)

Every registered model conforms to the following YAML structure:

```yaml
models:
  <model_identifier>:
    model: <Friendly Model Name>
    version: <SemVer string, e.g., "1.0.0">
    status: not_trained | candidate | ready | deprecated
    dataset: <Dataset identifier>
    dataset_hash: <SHA-256 hash of training data or manifest>
    feature_schema:
      inputs:
        - <feature_name_1>
        - <feature_name_2>
      targets:
        - <target_name>
    artifact_path: <Relative path to serialized model file>
    preprocessing_artifact: <Relative path to scalers / transformers>
    evaluation_artifact: <Relative path to test evaluation report>
    created_at: <ISO-8601 UTC timestamp>
```

---

## 3. Registered Baseline Models

The four foundational models scaffolded in NOVA are:
1. `process_anomaly_detector` (v1.0.0) — PCA + Isolation Forest
2. `process_fault_classifier` (v1.0.0) — XGBoost Multiclass
3. `furnace_cot_predictor` (v1.0.0) — CNN + BiLSTM + Attention / XGBoost
4. `tube_temperature_predictor` (v1.0.0) — LSTM Autoencoder + ANN
