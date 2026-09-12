# NOVA Backend Target Architecture

**System:** NOVA Industrial AI Co-Pilot & Safety Advisory Platform  
**Document Version:** 1.0 (Contract Lock & Scaffolding)

---

## 1. High-Level Architectural Flow

```text
                  INDUSTRIAL SYSTEMS
             (DCS, SCADA, PLC, Histograms)
                         │
                         ▼
                INGESTION / CONNECTORS
               (`backend/pipeline/`)
                         │
                         ▼
             NORMALIZATION & VALIDATION
            (`backend/pipeline/normalizer`)
                         │
                         ▼
                 CANONICAL EVENTS
            (`backend/models/industrial_domain`)
                         │
                         ▼
                    PLANT STATE
         (`backend/services/plant_state_service`)
                         │
                ┌────────┴────────┐
                ▼                 ▼
          FEATURE ENGINE     CONTEXT ENGINE
      (`backend/ml/features`)  (`backend/services/`)
                │                 │
                └────────┬────────┘
                         ▼
                    ML PIPELINE
         (`backend/ml/inference/pipeline`)
                         │
                         ▼
               INDUSTRIAL RISK ENGINE
       (`backend/services/industrial_risk_service`)
                         │
                         ▼
               OPERATIONAL EPISODE
        (`backend/services/episode_engine`)
                    │          │
                    ▼          ▼
               PostgreSQL    Qdrant
            (Relational DB)  (Semantic Memory)
                    │          │
                    └────┬─────┘
                         ▼
                  EVIDENCE PACKAGE
             (`backend/models/evidence`)
                         │
                         ▼
                    LLM / AGENTS
               (`backend/agents/`, `llm/`)
                         │
                         ▼
                  OPERATOR / VOICE
                 (`backend/voice/`, UI)
                         │
                         ▼
                 FEEDBACK & AUDIT
              (`backend/db/`, API logs)
```

---

## 2. Layer-by-Layer Architectural Specification

### 1. Ingestion / Connectors & Normalization
* **Owner Module:** `backend/pipeline/telemetry_pipeline.py` & `backend/api/routes_industrial.py`
* **Responsibility:** Ingest raw telemetry, sensor streams, OPC UA / MQTT / REST payloads. Normalize incoming fields (`tag` -> `parameter`, `reading` -> `value`, timestamp parsing) into canonical contracts.
* **Input Contract:** Raw JSON payload, `ProcessTelemetryCreate`, or SCADA telemetry dictionary.
* **Output Contract:** `ProcessTelemetry` with `quality="GOOD"`, validated engineering units, provenance metadata.
* **Database Interaction:** Inserts into SQLite/PostgreSQL `telemetry_events` table asynchronously.
* **Event Interaction:** Publishes normalized `telemetry` event to `backend/bus/event_bus.py`.

### 2. Plant State Aggregation
* **Owner Module:** `backend/services/plant_state_service.py`
* **Responsibility:** Maintain the authoritative, multi-modal, real-time snapshot of the entire facility or unit, combining telemetry, active alarms, maintenance permits, occupancy, and operating modes.
* **Input Contract:** `ProcessTelemetry`, `Alarm`, `Permit`, `MaintenanceRecord`, `OccupancyRecord`, `OperatingMode`.
* **Output Contract:** `PlantState` domain model.
* **Database Interaction:** Cached in memory with periodic checkpointing to `plants` and `operational_episodes` tables.
* **Event Interaction:** Subscribes to telemetry and alarm events; emits `plant_state_updated` notifications.

### 3. Feature & Context Engine
* **Owner Module:** `backend/ml/features/extractor.py`
* **Responsibility:** Extract windowed time-series features across numerical channels: delta, rate of change (ROC), rolling statistics (mean, std, min, max), baseline deviations, and one-hot operating mode context.
* **Input Contract:** Historical telemetry sliding window (`List[ProcessTelemetry]` or `PlantState`).
* **Output Contract:** `FeatureWindow` containing structured tabular feature vectors and statistical summaries.
* **Database Interaction:** Read-only queries to `telemetry_events` when historical cold windows are required.
* **Event Interaction:** None (stateless compute transformation).

### 4. Pluggable ML Pipeline
* **Owner Module:** `backend/ml/inference/pipeline.py` & `backend/ml/registry/`
* **Responsibility:** Coordinate inference across the four core industrial models:
  1. `ProcessAnomalyDetector` (TEP statistical monitoring & Isolation Forest)
  2. `ProcessFaultClassifier` (TEP multiclass XGBoost)
  3. `FurnaceCOTPredictor` (CNN + BiLSTM + Attention / XGBoost)
  4. `TubeTemperaturePredictor` (LSTM-AE + ANN)
  Gracefully handles missing model weights by emitting `status="MODEL_NOT_AVAILABLE"` envelopes without crashing.
* **Input Contract:** `PlantState` or `FeatureWindow` dictionary.
* **Output Contract:** `Dict[str, MLAssessment]`.
* **Database Interaction:** Inserts records into `ml_assessments` table for tracking and audits.
* **Event Interaction:** Emits `ml_assessment_completed` on the event bus.

### 5. Industrial Risk Engine
* **Owner Module:** `backend/services/industrial_risk_service.py`
* **Responsibility:** Deterministic, explainable risk scoring combining equipment criticality, active alarms, SIMOPS conflicts (hot work + flammable hydrocarbon line + personnel present), and validated ML assessments.
* **Input Contract:** `PlantState`, `Dict[str, MLAssessment]`, policy thresholds.
* **Output Contract:** `IndustrialRiskAssessment` with `risk_score` (0.0–1.0), `risk_tier` (LOW, MEDIUM, HIGH, CRITICAL), contributing factors, and `advisory_only=True`.
* **Database Interaction:** Writes to `risk_assessments` table.
* **Event Interaction:** Emits `risk_escalated` event if severity reaches `HIGH` or `CRITICAL`.

### 6. Operational Episode Engine
* **Owner Module:** `backend/services/episode_engine.py`
* **Responsibility:** Manage incident lifecycles through 7 canonical states:
  `NORMAL` -> `DEVIATION` -> `ANOMALY` -> `DIAGNOSIS` -> `ELEVATED_RISK` -> `MITIGATION_OBSERVATION` -> `RESOLVED`.
  Correlate telemetry, alarms, permits, risk evaluations, and operator interventions.
* **Input Contract:** Operational events, telemetry anomalies, alarm transitions, risk evaluations.
* **Output Contract:** `OperationalEpisode` model.
* **Database Interaction:** Full transactional lifecycle recorded in `operational_episodes` table.
* **Event Interaction:** Subscribes to all domain events; publishes `episode_transitioned`.

### 7. Dual Memory Persistence Layer
* **Owner Module:** `backend/db/db.py` (Relational) & `backend/memory/collections.py` (Semantic)
* **Responsibility:**
  - **Relational (PostgreSQL/SQLite):** System of record for time-series telemetry, audit events, users, permits, and active states.
  - **Semantic (Qdrant):** Dense vector storage across collections (`nova_operational_memory`, `nova_engineering_knowledge`, `nova_industry_cases`) for RAG retrieval.
* **Input Contract:** Entity instances (`upsert`, SQL queries).
* **Output Contract:** Persisted rows and semantic vector search hit payloads.
* **Database Interaction:** Direct connection pooling and vector index operations.
* **Event Interaction:** None.

### 8. Evidence Package & Reasoning Layer
* **Owner Module:** `backend/models/evidence.py` & `backend/agents/`
* **Responsibility:** Consolidate plant state, ML assessments, risk calculations, permit conflicts, and semantic knowledge matches into a unified `EvidencePackage` before dispatching to LLM / Copilot.
* **Input Contract:** `PlantState`, `List[MLAssessment]`, `IndustrialRiskAssessment`, `List[MemoryMatch]`.
* **Output Contract:** Strongly typed `EvidencePackage` payload.
* **Database Interaction:** Read-only retrieval of contextual historical records.
* **Event Interaction:** Emits `evidence_package_generated`.

### 9. Safety Guard & Operator Advisory Boundary
* **Owner Module:** `backend/policy_engine/safety_guard.py`
* **Responsibility:** Enforce zero-actuation safety constraint. Blocks direct PLC, DCS, SIS, or ESD actuation commands. All NOVA outputs remain strictly read-only advisory recommendations.
* **Input Contract:** Raw natural language command, proposed tool action, or agent response.
* **Output Contract:** Validation boolean (`is_safe`) and violation audit log.
* **Database Interaction:** Writes blocked violations to `audit_events`.
* **Event Interaction:** Emits `safety_violation_blocked` alert.
