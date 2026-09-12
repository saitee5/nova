# NOVA Knowledge Base & RAG Architecture

**Workstream Owner:** Arushi (ML, RAG, Knowledge Base, Retrieval, Evidence/Provenance)  
**System Status:** `DEMO_KNOWLEDGE_CORPUS_READY`  
**Package Path:** `backend/knowledge/`  
**Demo Corpus Path:** `data/knowledge/demo/`

---

## 1. System Overview & Architecture Flow

NOVA's operational intelligence is grounded in engineering documentation combined with validated ML model predictions. The Knowledge Base / RAG pipeline ingests, normalizes, indexes, and retrieves industrial plant knowledge with complete citation traceability and provenance.

```
 DEMO DOCUMENTS (SOPs, Operating Manuals, P&IDs, Safety Standards, Datasheets)
    │ (under data/knowledge/demo/)
    ▼
 INGESTION (Validation, Non-empty checks, SHA-256 deduplication)
    │
    ▼
 NORMALIZATION (Whitespace, Unicode NFKC, Line-ending cleanup;
                STRICT preservation of headings, steps, warnings, tables, tags, units)
    │
    ▼
 CHUNKING (Section-aware semantic chunking; step sequence integrity)
    │
    ▼
 METADATA (document_type, equipment_id, equipment_type, unit_area, version, authority)
    │
    ▼
 EMBEDDINGS / INDEX (BAAI/bge-small-en-v1.5 dense vectors + local & Qdrant indices)
    │
    ▼
 RETRIEVAL API (Cosine similarity ranking, multi-field industrial metadata filtering)
    │
    ▼
 EVIDENCE OBJECTS (DOCUMENT_EVIDENCE + MODEL_EVIDENCE)
    │
    ▼
 SOURCE / CITATION TRACEABILITY (document_id, chunk_id, section, content_hash)
    │
    ▼
 FUTURE NOVA REASONING LAYER (Context Builder -> Copilot / Risk Reasoner)
```

---

## 2. Ownership & Handoff Boundaries

| Layer / Subsystem | Owner | Scope & Responsibilities |
| :--- | :--- | :--- |
| **ML Models & Artifacts** | **Arushi** | Training, evaluation, model registry, inference contracts (`ProcessAnomalyDetector`, `ProcessFaultClassifier`, `FurnaceCOTPredictor`, `TubeTemperaturePredictor`). |
| **Knowledge Base & RAG** | **Arushi** | Document ingestion, normalization, section chunking, vector indexing, retrieval API, citations, `ModelEvidenceBridge`, `RAGContextBuilder`, and demo corpus. |
| **Evidence & Provenance** | **Arushi** | `CanonicalEvidence`, `Citation`, `DOCUMENT_EVIDENCE`, `MODEL_EVIDENCE`, synthetic surrogate transparency. |
| **NOVA Runtime & Orchestration** | **Runtime Engineer** | Consumes evidence packages & predictions, manages active cases, runs policy engine, executes operational actions, orchestrates agents. |

> [!IMPORTANT]
> The ML/RAG layer produces grounded **Evidence** and **Retrieval Results**. It does **NOT** autonomously execute plant actions or trigger state transitions. Runtime orchestration belongs strictly to the runtime layer.

---

## 3. Demo Knowledge Corpus (`data/knowledge/demo/`)

The demo corpus comprises 19 synthetic engineering documents created specifically for demonstration and testing of NOVA's knowledge retrieval capabilities.

### Synthetic Provenance & Safeguards
Every document carries mandatory demo metadata:
- `source_type`: `synthetic_demo`
- `authority`: `demo_only`
- `industrial_validation`: `false`
- `is_synthetic_demo`: `true`

> [!WARNING]
> These documents are synthetic and generated for demonstration purposes. They must never be presented as plant-authoritative or OEM-approved operating manuals.

### Document Inventory (19 Documents, 64 Chunks)

| Document ID | Type | Target Asset | Title Summary |
| :--- | :--- | :--- | :--- |
| `DOC-DEMO-SOP-F201-001` | `SOP` | `F-201A` | Normal Operating Envelope & COT Control |
| `DOC-DEMO-ALM-F201-002` | `alarm_procedure` | `F-201A` | High COT Alarm Response (TI-201 > 885 °C) |
| `DOC-DEMO-ALM-F201-003` | `alarm_procedure` | `F-201A` | Low COT Alarm Response & Quench Protection |
| `DOC-DEMO-SOP-F201-004` | `SOP` | `F-201A` | Startup & Burner Firing Sequence |
| `DOC-DEMO-SOP-F201-005` | `emergency_procedure` | `F-201A` | Emergency Furnace Shutdown (ESD-1) Protocol |
| `DOC-DEMO-ENG-F201-006` | `engineering_document` | `F-201A` | Steam Dilution Ratio & Severity Control |
| `DOC-DEMO-OPM-F201-007` | `operating_manual` | `F-201A` | Tube Metal Temperature (TMT) & Skin Thermocouples |
| `DOC-DEMO-OPM-FLT-008` | `operating_manual` | `F-201A` | Fuel Gas Pressure Drift & Valve Response |
| `DOC-DEMO-OPM-FLT-009` | `operating_manual` | `F-201A` | Feed Flow Variance & Steam Disruption |
| `DOC-DEMO-ENG-FLT-010` | `engineering_document` | `F-201A` | Sensor Drift & Redundant Thermocouple Validation |
| `DOC-DEMO-SAF-GEN-011` | `safety_procedure` | `F-201A` | Gas Detection Response Protocol |
| `DOC-DEMO-SAF-GEN-012` | `safety_procedure` | `F-201A` | Lockout / Tagout (LOTO) & Energy Isolation |
| `DOC-DEMO-SAF-GEN-013` | `safety_procedure` | `F-201A` | PPE & High-Temperature Zone Protocols |
| `DOC-DEMO-EMG-GEN-014` | `emergency_procedure` | `F-201A` | Unit Emergency Depressurization (EDP) & Flare |
| `DOC-DEMO-DAT-F201-015` | `equipment_datasheet` | `F-201A` | Pyrolysis Cracking Furnace F-201A Datasheet |
| `DOC-DEMO-DAT-P101-016` | `equipment_datasheet` | `P-101A` | Hydrocarbon Feed Pumps P-101A/B Datasheet |
| `DOC-DEMO-PID-TOP-017` | `P&ID` | `F-201A` | UNIT-CRACK-01 Process Stream Topology |
| `DOC-DEMO-MNT-F201-018` | `maintenance_manual` | `F-201A` | Radiant Tube Inspection, Decoking & Burners |
| `DOC-DEMO-TRN-GEN-019` | `training_material` | `F-201A` | Fundamentals of Thermal Cracking |

---

## 4. Ingestion & Build Script

The demo corpus is ingested and indexed deterministically using:

```bash
python -m backend.knowledge.build_demo_corpus
```

The script performs:
1. File discovery in `data/knowledge/demo/*.md`
2. Frontmatter metadata extraction
3. Content normalization and SHA-256 hash calculation
4. Deduplication validation
5. Section-aware chunking into `DocumentChunk` records
6. Vector embedding using `BAAI/bge-small-en-v1.5`
7. Deterministic index population

---

## 5. Evidence Prioritization Policy

When assembling multi-source evidence into a `RAGContext`, the following deterministic prioritization hierarchy is applied:
1. **Equipment-Specific Operational & Alarm Procedures** (e.g. `DOC-DEMO-ALM-F201-002`, `DOC-DEMO-SOP-F201-001`)
2. **Safety & Emergency Procedures** (e.g. `DOC-DEMO-SAF-GEN-011`, `DOC-DEMO-EMG-GEN-014`)
3. **Equipment Engineering Specifications & Datasheets** (e.g. `DOC-DEMO-DAT-F201-015`, `DOC-DEMO-PID-TOP-017`)
4. **Maintenance & Training Documents** (e.g. `DOC-DEMO-MNT-F201-018`, `DOC-DEMO-TRN-GEN-019`)
5. **Machine Learning Model Evidence** (`ProcessAnomalyDetector`, `ProcessFaultClassifier`, `FurnaceCOTPredictor`, `TubeTemperaturePredictor`)

---

## 6. Model Evidence Bridge & Synthetic Provenance

NOVA features 4 ML model components:
1. `ProcessAnomalyDetector` v1.1.0 (`VALIDATED_WITH_LIMITATIONS`)
2. `ProcessFaultClassifier` v1.1.0 (`VALIDATED_WITH_LIMITATIONS`)
3. `FurnaceCOTPredictor` v1.1.0 (`VALIDATED_WITH_LIMITATIONS`)
4. `TubeTemperaturePredictor` v1.0.0-demo / v1.1.0 (`DEMO_VALIDATED_WITH_LIMITATIONS`)

The `ModelEvidenceBridge` converts predictions into `MODEL_EVIDENCE` objects:

```python
from backend.knowledge import ModelEvidenceBridge

# Translating tube temp soft sensor prediction into evidence:
evidence = ModelEvidenceBridge.from_tube_temp_prediction(
    prediction={"predicted_tmt": 965.8, "confidence": 0.88, "status": "OK"}
)
```

### Synthetic Provenance Protection
For `TubeTemperaturePredictor`, the bridge explicitly embeds:
- `target_type`: `"physics_informed_synthetic_surrogate"`
- `industrial_validation`: `False`
- `limitation_notice`: *"Physics-informed statistical surrogate; NOT measured industrial telemetry."*

---

## 7. Safe Failure & Non-Hallucination Behavior

The retrieval subsystem fails safely without fabricating data:

| Condition | Status Code | Returned Content |
| :--- | :--- | :--- |
| Normal match | `RetrievalStatus.OK` | Ranked, cited chunks |
| Knowledge base is empty | `RetrievalStatus.NO_KNOWLEDGE_AVAILABLE` | Empty results list |
| Query matches no documents / negative queries | `RetrievalStatus.NO_RELEVANT_EVIDENCE` | Empty results list |
| Query is empty or whitespace | `RetrievalStatus.INVALID_QUERY` | Empty results list |
| Vector index is missing/error | `RetrievalStatus.KNOWLEDGE_BASE_UNAVAILABLE` | Empty results list |
