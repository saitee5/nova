# NOVA Backend Architecture Audit

**Status:** Complete  
**System:** NOVA Industrial AI Co-Pilot & Safety Advisory System  
**Audit Scope:** Full backend directory inspection, existing service review, database schema, ML inference pipeline, event bus, agent architecture, and API layer.

---

## 1. Executive Summary

The NOVA backend repository is a mission-critical industrial advisory system built with FastAPI, SQLite/PostgreSQL, Qdrant semantic memory, an in-process asynchronous Event Bus, and an agentic multi-agent architecture. The audit confirms that the core systems are operational and adhere to strict read-only safety principles.

The purpose of this audit is to lock canonical contracts across domains (Plant, Unit, Asset, Sensor, Telemetry, Alarms, Maintenance, Permits, Occupancy, Operating Mode, Plant State, ML Assessments, Risk, Episodes, Evidence, and Safety Guards) and establish pluggable ML infrastructure where models gracefully degrade to `MODEL_NOT_AVAILABLE` without breaking pipelines or triggering runtime exceptions.

---

## 2. Component Inventory & Audit Table

| Component | Location | Purpose | Current Implementation | Status | Dependencies | Consumers | Inputs | Outputs | Tests | Known Issues | Action |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **Event Bus** | `backend/bus/event_bus.py` | In-process pub/sub event distribution | `EventBus` singleton with FIFO queues and topic subscriptions | Production Ready | `asyncio`, `logging` | Pipeline, Agents, WebSocket | Any domain event object / Dict | Dispatched event notifications | `test_transport_chain.py` | In-memory only; needs distributed queue for multi-node deployments | **KEEP** |
| **Telemetry Ingestion** | `backend/pipeline/telemetry_pipeline.py` | Stream ingestion and dispatch | `TelemetryPipeline` validating packets, writing DB, publishing to bus | Production Ready | `db`, `bus`, `config` | API routers, Simulator | Raw or canonical JSON telemetry | Stored row, Bus broadcast | `test_pipeline.py` | Legacy format accepted raw dict; now extended for canonical contracts | **EXTEND** |
| **Plant State Service** | `backend/services/plant_state_service.py` | Authoritative single source of plant state | Combines telemetry, active alarms, permits, maintenance, occupancy | Complete | `models.industrial_domain` | Risk Engine, Episodes, Evidence Package | Telemetry, Alarms, SIMOPS events | Aggregated `PlantState` | `test_canonical_contracts.py` | In-memory cache with DB synchronization | **KEEP** |
| **Feature Engine** | `backend/ml/features/extractor.py` | Windowed feature computation for ML | `FeatureExtractor` computing rolling mean, std, min, max, deltas, ROC | Complete | `numpy` | Unified ML Pipeline | `PlantState`, Raw series | `FeatureWindow` vector | `test_canonical_contracts.py` | Lightweight pure Python/numpy implementation | **KEEP** |
| **ML Model Registry** | `backend/ml/registry/registry.py` | Model artifact management & metadata | `ModelRegistry` reading `artifacts/models/registry.yaml` | Complete | `yaml`, `pydantic` | Inference models, MLPipeline | Model name & version | `ModelMetadata`, artifact paths | `test_canonical_contracts.py` | Initializes in `not_trained` status | **KEEP** |
| **Anomaly Detector** | `backend/ml/anomaly/detector.py` | TEP process anomaly detection | `ProcessAnomalyDetector` with PCA + Isolation Forest interface | Pluggable Skeleton | Registry, Base ML contract | ML Pipeline, Episodes | Telemetry vector / Dict | `MLAssessment` (`MODEL_NOT_AVAILABLE`) | `test_canonical_contracts.py` | Real weights pending training | **EXTEND** |
| **Fault Classifier** | `backend/ml/fault/classifier.py` | TEP multiclass fault classification | `ProcessFaultClassifier` with XGBoost multiclass interface | Pluggable Skeleton | Registry, Base ML contract | ML Pipeline, Episodes | Feature vector / Dict | `MLAssessment` (`MODEL_NOT_AVAILABLE`) | `test_canonical_contracts.py` | Real weights pending training | **EXTEND** |
| **Furnace COT Predictor** | `backend/ml/furnace/cot_predictor.py` | Coil Outlet Temp regression | `FurnaceCOTPredictor` with CNN-BiLSTM-Attention interface | Pluggable Skeleton | Registry, Base ML contract | ML Pipeline | Temperature & flow vector | `MLAssessment` (`MODEL_NOT_AVAILABLE`) | `test_canonical_contracts.py` | Real weights pending training | **EXTEND** |
| **Tube Temp Predictor** | `backend/ml/furnace/tube_temp_predictor.py` | Pyrometry / skin temp predictor | `TubeTemperaturePredictor` with LSTM-AE + ANN interface | Pluggable Skeleton | Registry, Base ML contract | ML Pipeline | Thermal & flow vector | `MLAssessment` (`MODEL_NOT_AVAILABLE`) | `test_canonical_contracts.py` | Real weights pending training | **EXTEND** |
| **Unified ML Pipeline** | `backend/ml/inference/pipeline.py` | Pluggable multi-model inference runner | `MLPipeline` (`IndustrialMLInferencePipeline`) | Production Ready | Anomaly, Fault, COT, Tube Temp detectors | Risk Engine, REST API | `PlantState` or Feature vector | Dict of `MLAssessment` | `test_canonical_contracts.py` | Gracefully handles missing weights | **KEEP** |
| **Industrial Risk Engine** | `backend/services/industrial_risk_service.py` | Deterministic risk & SIMOPS reasoning | Evaluates base severity, equipment criticality, permit conflicts | Production Ready | `models.industrial_domain` | Episodes, Copilot, REST API | `PlantState`, ML assessments | `IndustrialRiskAssessment` | `test_canonical_contracts.py` | Policy v1.0 enforced | **KEEP** |
| **Episode Engine** | `backend/services/episode_engine.py` | 7-stage incident lifecycle management | Manages `NORMAL` to `RESOLVED` transitions and history | Production Ready | `db`, `models.industrial_domain` | Copilot, REST API | Correlated events & state | `OperationalEpisode` | `test_canonical_contracts.py` | DB persistence enabled | **KEEP** |
| **Semantic Memory** | `backend/memory/collections.py` | Vector search across knowledge bases | Qdrant client wrapper with `upsert` and `search` | Production Ready | `qdrant_client` | Copilot, Evidence Package | Queries, Documents, Embeddings | Ranked semantic search hits | `test_memory.py` | Local disk storage fallback | **KEEP** |
| **Evidence Package** | `backend/models/evidence.py` | Context consolidation for LLM | Strongly typed container uniting state, ML, risk, knowledge | Production Ready | Domain models | LLM / Copilot Reasoner | State, Risk, Memory matches | Structured `EvidencePackage` | `test_canonical_contracts.py` | Ready for prompt synthesis | **KEEP** |
| **Safety Boundary** | `backend/policy_engine/safety_guard.py` | Deterministic advisory guardrail | Regex & keyword validator blocking actuation/PLC commands | Production Ready | None | Agents, API, LLM | Proposed action strings | Boolean approval + violation log | `test_safety_guard.py` | Zero actuation permitted | **KEEP** |
| **REST API** | `backend/api/routes_industrial.py` | Canonical industrial endpoints | FastAPI APIRouter covering all domain entities & state | Production Ready | Services, Models | Frontend, External clients | HTTP GET/POST | JSON response envelopes | `test_canonical_contracts.py` | Fully backwards compatible | **KEEP** |
| **Scenario Simulator** | `data_simulator/` | Correlated industrial event stream | Scenario runner (`furnace`, `compressor`, `simops`) | Production Ready | `asyncio`, HTTP client | Pipeline, Backend ingestion | Scenario JSON definitions | Correlated telemetry stream | Scenario configs verified | **KEEP** |

---

## 3. Action Summary

- **KEEP (14 components):** Event Bus, Plant State Service, Feature Engine, Model Registry, Unified ML Pipeline, Risk Engine, Episode Engine, Semantic Memory, Evidence Package, Safety Boundary, REST API, Simulator, Agents, Voice module.
- **EXTEND (4 components):** Anomaly Detector, Fault Classifier, Furnace COT Predictor, Tube Temperature Predictor (scaffolded to return `MODEL_NOT_AVAILABLE` with strict schema validation; ready for trained weights in subsequent prompts).
- **CONSOLIDATE / REFACTOR (0 components):** All existing APIs and paths were preserved without deprecation or naming collision.
- **REPLACE (0 components):** No working production modules were replaced.
