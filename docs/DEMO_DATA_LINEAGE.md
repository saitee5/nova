# NOVA Demo Data Lineage & Industrial Source Audit

**Workstream Owner:** Arushi (ML, RAG, Knowledge Base, Retrieval, Evidence/Provenance)  
**System Status:** `DEMO_KNOWLEDGE_CORPUS_ENRICHED`  
**Corpus Path:** `data/knowledge/demo/`

---

## 1. Executive Summary & Governance Principles

The NOVA Demo Knowledge Corpus is an enriched, internally coherent synthetic engineering corpus designed to simulate realistic operational intelligence across an industrial ethylene cracking unit (`UNIT-CRACK-01`, centering on Pyrolysis Cracking Furnace `F-201A`).

### Core Governance Rules
1. **No Raw Row Copying**: Source datasets are studied strictly for **structure, distributions, failure taxonomies, engineering units, and domain relationships**. No raw rows, confidential records, or personal data are copied.
2. **Strict Non-Authoritative Safeguards**: Every generated record carries:
   - `source_type: synthetic_demo`
   - `authority: demo_only`
   - `industrial_validation: false`
   - `is_synthetic_demo: true`
   - `derived_from_source: true`
3. **No PII / Medical Data**: Health and safety datasets are used only for hazard taxonomy and PPE concepts; no personal health records or individual identifiers are reproduced.
4. **Immutable ML Training Sets**: ML training datasets (`data/curated/`) remain strictly untouched.

---

## 2. Source Datasets Audit & Classification

| Dataset Identifier | File Path | Format | Rows / Size | Domain | Classification | RAG & Demo Generation Use | Quality / Sensitivity Considerations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tennessee Eastman Process (TEP)** | `data/curated/tep/tep_canonical.csv` | CSV | 200,000 rows, 55 cols | Process Dynamics & Faults | `SOURCE_OF_TRUTH_REFERENCE` | Provides 21-class fault taxonomy, cooling water dynamics, pressure/temperature coupling. | Simulation benchmark; no PII. Curated ML dataset (immutable). |
| **Furnace COT Dataset** | `data/curated/furnace_cot/furnace_cot_canonical.csv` | CSV | 2,834 rows, 17 cols | Pyrolysis Reaction Kinetics | `SOURCE_OF_TRUTH_REFERENCE` | Provides chemical composition (C2H4, C2H6, etc.), pressure, cracking temperature, and COT operating ranges (800–890 °C). | Open industrial process dataset; immutable ML source. |
| **Synthetic Tube Temperature** | `data/curated/tube_temperature/tube_temperature_canonical.csv` | CSV | 2,834 rows, 18 cols | Radiant Coil Tube Metal Temp (TMT) | `SYNTHETIC_REFERENCE` | Provides TMT ranges (930–1080 °C) and surrogate prediction targets for demo soft sensor. | Target is physics-informed synthetic formula; must preserve synthetic disclaimer. |
| **Industrial Safety & Health Analytics** | `data/raw/safety/IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv` | CSV | 425 rows, 11 cols | Safety & Incidents | `AUXILIARY_REFERENCE` | Provides incident severity hierarchy (near-miss, minor, major), critical risk categories, and root cause descriptions. | Contains freeform accident narratives; individual records and dates are NOT copied directly. |
| **Petrochemical Advanced Optimization** | `data/raw/petrochemical/petrochemical_advanced_data.csv` | CSV | 10,000 rows, 16 cols | Petrochemical Process & Assets | `AUXILIARY_REFERENCE` | Informs vibration limits (mm/s), valve position dynamics (%), catalyst aging, and energy intensity metrics. | Synthetic/industrial telemetry benchmark; clean numerical data. |
| **Petrochemical Predictive Maintenance** | `data/raw/environmental/petrochemical_predictive_maintenance.csv` | CSV | 15,120 rows, 29 cols | Maintenance & Rotating Equipment | `AUXILIARY_REFERENCE` | Informs pump/compressor degradation, maintenance cycles, bearing vibration thresholds, and SO2/flue emissions. | Synthetic industrial dataset; informs maintenance interval structures. |
| **Qdrant Operational Memory Seed Data** | `qdrant/seed_data/*.jsonl` | JSONL | 8 files, ~40 records | VIGIL Memory Layer | `AUXILIARY_REFERENCE` | Establishes schema conventions for equipment context, incident memories, LOTO procedures, and risk patterns. | Seed data for vector memory; reference for JSON schema. |

---

## 3. Source-to-Demo Mapping & Lineage

### Domain A: Cracking Furnace Operations & Thermal Severity
- **Source Reference**: `data/curated/furnace_cot/furnace_cot_canonical.csv` & `data/curated/tube_temperature/`
- **What Was Learned**:
  - Operating COT range: 840.0 °C to 860.0 °C; high trip: 890.0 °C.
  - Radiant coil TMT operating range: 930.0 °C to 980.0 °C; alarm: 1040.0 °C; trip: 1080.0 °C.
  - Dilution steam ratio: 0.35 to 0.45 kg steam / kg hydrocarbon.
- **Generated Demo Artifacts**:
  - `DOC-DEMO-SOP-F201-001` (Normal Envelope)
  - `DOC-DEMO-ALM-F201-002` (High COT Alarm Response)
  - `DOC-DEMO-ALM-F201-003` (Low COT Alarm Response)
  - `DOC-DEMO-SOP-F201-004` (Startup & Firing Sequence)
  - `DOC-DEMO-SOP-F201-005` (Emergency Shutdown Protocol)
  - `DOC-DEMO-ENG-F201-006` (Dilution Steam & Severity Spec)
  - `DOC-DEMO-OPM-F201-007` (TMT Monitoring & Skin Thermocouples)
- **What Was NOT Copied**: No raw continuous time-series rows. All documents are structured engineering procedures.

### Domain B: Process Anomaly & Fault Mitigation
- **Source Reference**: `data/curated/tep/tep_canonical.csv` (TEP 21-Class Fault Taxonomy)
- **What Was Learned**:
  - Step decreases in cooling water / steam induce thermal runaway.
  - Feed composition shifts (ethane/propane ratios) alter reaction severity.
  - Fuel gas pressure fluctuations trigger flame instability and localized hot spots.
- **Generated Demo Artifacts**:
  - `DOC-DEMO-OPM-FLT-008` (Fuel Gas Pressure Drift)
  - `DOC-DEMO-OPM-FLT-009` (Feed Flow & Steam Disruption)
  - `DOC-DEMO-ENG-FLT-010` (Sensor Drift & Redundant 2oo3 Thermocouple Voting)

### Domain C: Process Safety, PPE & Emergency Response
- **Source Reference**: `data/raw/safety/IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv` & `qdrant/seed_data/safety_procedures.jsonl`
- **What Was Learned**:
  - Critical risk taxonomy: high-temperature exposure, hazardous gas release, burn hazards, mechanical pinch points.
  - Multistage gas alarm protocol (20% LEL advisory, 40% LEL evacuation & hot work halt).
  - Positive energy isolation (spectacle blinding, electrical lockouts at 480V MCC).
- **Generated Demo Artifacts**:
  - `DOC-DEMO-SAF-GEN-011` (Gas Detection Protocol)
  - `DOC-DEMO-SAF-GEN-012` (Lockout / Tagout LOTO Principles)
  - `DOC-DEMO-SAF-GEN-013` (PPE & High-Temperature Zone Protocols)
  - `DOC-DEMO-EMG-GEN-014` (Unit Emergency Depressurization EDP & Flare Header Routing)
  - `DOC-DEMO-PMT-SOP-025` (Permit-to-Work Master Specification)

### Domain D: Equipment Hierarchy, Maintenance & Inspection
- **Source Reference**: `data/raw/petrochemical/petrochemical_advanced_data.csv`, `data/raw/environmental/`, & `qdrant/seed_data/maintenance_history.jsonl`
- **What Was Learned**:
  - Centrifugal pump vibration thresholds (normal < 4.5 mm/s, trip > 7.0 mm/s).
  - Radiant tube creep (< 3.0% diametrical growth) and ultrasonic NDT retirement thickness (6.2 mm).
  - Compressor efficiency degradation and seal oil differential pressure monitoring.
- **Generated Demo Artifacts**:
  - `DOC-DEMO-DAT-F201-015` (Furnace F-201A Datasheet)
  - `DOC-DEMO-DAT-P101-016` (Feed Pumps P-101A/B Datasheet)
  - `DOC-DEMO-PID-TOP-017` (Cracking Unit Process Stream Topology)
  - `DOC-DEMO-MNT-F201-018` (Radiant Tube Inspection & Decoking Manual)
  - `DOC-DEMO-DAT-C101-020` (Cracked Gas Compressor C-101 Datasheet)
  - `DOC-DEMO-ENG-HRC-021` (Plant Asset Hierarchy & Tag Directory)
  - `DOC-DEMO-MNT-HIS-022` (Furnace F-201A Maintenance Log & Work Orders)
  - `DOC-DEMO-INC-F201-023` (Incident Retrospective & Lessons Learned: 2025 Thermal Excursion)
  - `DOC-DEMO-INC-NRM-024` (Near-Miss Incident Log & Preventive Actions)
  - `DOC-DEMO-TRN-GEN-019` (Fundamentals of Thermal Cracking)

---

## 4. Coherent Synthetic Plant World & Entity Relationships

The demo corpus models a single, tightly connected petrochemical processing unit:

```
UNIT-CRACK-01 (Ethylene Cracking Unit)
 ├── Feed Delivery: Hydrocarbon Feed Pumps P-101A / P-101B
 ├── Cracking Core: Pyrolysis Furnace F-201A
 │    ├── Instrumentation: COT Transmitter TI-201 (2oo3), Skin Thermocouples TI-204 (1..24)
 │    ├── Actuators: Fuel Gas Valve FV-201, Dilution Steam Valve SV-204
 │    └── Combustion: 16 Floor Hearth Burners, 24 Wall Radiant Burners
 ├── Primary Quench: Transfer Line Exchanger TLE-201
 ├── Fractionation: Primary Fractionator Column C-201
 └── Compression: Cracked Gas Compressor C-101
```

### Relationship Matrix

| Entity | Relation | Linked Entity / Document |
| :--- | :--- | :--- |
| `F-201A` | `LOCATED_IN` | `UNIT-CRACK-01` |
| `F-201A` | `HAS_ALARM` | `DOC-DEMO-ALM-F201-002` (High COT), `DOC-DEMO-ALM-F201-003` (Low COT) |
| `F-201A` | `HAS_SOP` | `DOC-DEMO-SOP-F201-001` (Normal Envelope), `DOC-DEMO-SOP-F201-004` (Startup) |
| `F-201A` | `HAS_SAFETY_PROCEDURE` | `DOC-DEMO-SAF-GEN-012` (LOTO), `DOC-DEMO-SAF-GEN-013` (PPE) |
| `F-201A` | `HAS_PERMIT_REQUIREMENT` | `DOC-DEMO-PMT-SOP-025` (Hot Work, Confined Space Entry) |
| `F-201A` | `HAS_MAINTENANCE` | `DOC-DEMO-MNT-F201-018` (Inspection), `DOC-DEMO-MNT-HIS-022` (Work Orders) |
| `F-201A` | `HAS_INCIDENT` | `DOC-DEMO-INC-F201-023` (2025 Thermal Excursion Retrospective) |
| `F-201A` | `DOWNSTREAM_OF` | `P-101A/B` (Feed Pumps) |
| `F-201A` | `UPSTREAM_OF` | `TLE-201` (Transfer Line Exchanger) $\rightarrow$ `C-201` $\rightarrow$ `C-101` |
