# NOVA Unified ML Pipeline Specification

**Owner Module:** `backend/ml/inference/pipeline.py`  
**Class Name:** `MLPipeline` (with backward compatibility alias `IndustrialMLInferencePipeline`)  
**Status:** Operational (Graceful Fallback Mode)

---

## 1. Responsibilities

The Unified ML Pipeline orchestrates inference across all operational machine learning models in NOVA. It acts as the isolation boundary between incoming industrial telemetry/plant states and raw model execution.

Key design contracts:
1. **Never Fails the System:** If any model weight is missing, corrupted, or encounters an inference error, the pipeline catches the condition, logs the error, and populates the assessment envelope with `MODEL_NOT_AVAILABLE` or `INFERENCE_ERROR`.
2. **Deterministic Interfaces:** Accepts either a live `PlantState`, a precomputed `FeatureWindow`, or a raw telemetry dictionary.
3. **Structured Composite Output:** Returns a dictionary mapping model names (`anomaly_detection`, `fault_diagnosis`, `furnace_cot`, `tube_temperature`) to validated `MLAssessment` domain objects.

---

## 2. Pipeline Execution Flow

```text
               ┌──────────────────────────────┐
               │    PlantState / Telemetry     │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │       Feature Extractor      │
               │ (Rolling stats, Deltas, ROC) │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │          MLPipeline          │
               └──────┬───────┬───────┬───────┘
                      │       │       │       │
       ┌──────────────┘       │       │       └──────────────┐
       ▼                      ▼       ▼                      ▼
┌──────────────┐       ┌────────┐   ┌─────────┐       ┌──────────────┐
│AnomalyDetector│       │ Fault  │   │ Furnace │       │  Tube Temp   │
│ (PCA+IsoFor) │       │Classif.│   │   COT   │       │  Predictor   │
└──────┬───────┘       └───┬────┘   └───┬─────┘       └──────┬───────┘
       │                   │            │                    │
       │                   ▼            ▼                    │
       └──────────────► Combined Assessments ◄───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │   Dict[str, MLAssessment]    │
               │  (Ready for Risk Engine)     │
               └──────────────────────────────┘
```

---

## 3. Graceful Fallback Behavior

When models are not yet trained:
```python
pipeline = MLPipeline()
assessments = pipeline.run(plant_state)

assert assessments["anomaly_detection"].status == "MODEL_NOT_AVAILABLE"
assert assessments["anomaly_detection"].score == 0.0
assert assessments["fault_diagnosis"].status == "MODEL_NOT_AVAILABLE"
assert assessments["fault_diagnosis"].prediction is None
```

The output conforms 100% to the Pydantic schema required by `IndustrialRiskEngine` and `OperationalEpisodeEngine`, allowing end-to-end integration testing before model training begins.
