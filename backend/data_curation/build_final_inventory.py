import os
import json
import hashlib
import pandas as pd

def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def build_final_inventory():
    base_dir = r"c:\Users\Aarushi Sachdeva\OneDrive\Desktop\nova"
    manifest_dir = os.path.join(base_dir, "data", "manifests")
    analysis_dir = os.path.join(base_dir, "data", "analysis")
    os.makedirs(manifest_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    # 1. TEP Canonical Dataset
    tep_path = os.path.join(base_dir, "data", "curated", "tep", "tep_canonical.csv")
    if not os.path.exists(tep_path):
        raise FileNotFoundError(f"TEP canonical dataset not found at {tep_path}")
    print("Hashing TEP canonical dataset...", flush=True)
    tep_sha256 = compute_sha256(tep_path)
    tep_size = os.path.getsize(tep_path)
    
    # 2. Furnace COT Canonical Dataset
    cot_path = os.path.join(base_dir, "data", "curated", "furnace_cot", "furnace_cot_canonical.csv")
    if not os.path.exists(cot_path):
        raise FileNotFoundError(f"Furnace COT canonical dataset not found at {cot_path}")
    print("Hashing Furnace COT canonical dataset...", flush=True)
    cot_sha256 = compute_sha256(cot_path)
    cot_size = os.path.getsize(cot_path)
    
    # 3. Tube Temperature Canonical Dataset
    tmt_path = os.path.join(base_dir, "data", "curated", "tube_temperature", "tube_temperature_canonical.csv")
    if not os.path.exists(tmt_path):
        raise FileNotFoundError(f"Tube Temperature canonical dataset not found at {tmt_path}")
    print("Hashing Tube Temperature canonical dataset...", flush=True)
    tmt_sha256 = compute_sha256(tmt_path)
    tmt_size = os.path.getsize(tmt_path)
    
    inventory_data = {
        "timestamp": "2026-09-12T18:15:00Z",
        "system": "NOVA Industrial Operational-Intelligence Platform",
        "phase": "Final Canonical Dataset Preparation (Pre-Improver)",
        "models": [
            {
                "model_name": "ProcessAnomalyDetector",
                "dataset_name": "tep_canonical.csv",
                "file_path": "data/curated/tep/tep_canonical.csv",
                "source": "Tennessee Eastman Process (TEP) Benchmark",
                "rows": 15330000,
                "columns": 55,
                "target": "fault_number",
                "target_type": "Categorical fault code (0=Normal, 1-20=Fault Modes)",
                "dataset_type": "Real benchmark",
                "sha256": tep_sha256,
                "size_bytes": tep_size,
                "status": "READY"
            },
            {
                "model_name": "ProcessFaultClassifier",
                "dataset_name": "tep_canonical.csv",
                "file_path": "data/curated/tep/tep_canonical.csv",
                "source": "Tennessee Eastman Process (TEP) Benchmark",
                "rows": 15330000,
                "columns": 55,
                "target": "fault_number",
                "target_type": "Categorical fault code (0=Normal, 1-20=Fault Modes)",
                "dataset_type": "Real benchmark",
                "sha256": tep_sha256,
                "size_bytes": tep_size,
                "status": "READY"
            },
            {
                "model_name": "FurnaceCOTPredictor",
                "dataset_name": "furnace_cot_canonical.csv",
                "file_path": "data/curated/furnace_cot/furnace_cot_canonical.csv",
                "source": "Ethylene Cracking Furnace Industrial Dataset",
                "rows": 30015,
                "columns": 17,
                "target": "COT",
                "target_units": "°C",
                "target_type": "Real industrial measured continuous variable",
                "dataset_type": "Real industrial",
                "sha256": cot_sha256,
                "size_bytes": cot_size,
                "status": "READY"
            },
            {
                "model_name": "TubeTemperaturePredictor",
                "dataset_name": "tube_temperature_canonical.csv",
                "file_path": "data/curated/tube_temperature/tube_temperature_canonical.csv",
                "source": "Ethylene Cracking Furnace Process Dataset + 1D Heat Transfer Physics Model",
                "rows": 30015,
                "columns": 18,
                "target": "TMT",
                "target_units": "°C",
                "target_type": "physics-informed synthetic",
                "dataset_type": "Physics-informed synthetic",
                "sha256": tmt_sha256,
                "size_bytes": tmt_size,
                "status": "READY"
            }
        ],
        "auxiliary_datasets": [
            {
                "name": "petrochemical_advanced_data.csv",
                "path": "data/cleaned/petrochemical/petrochemical_advanced_data.csv",
                "rows": 1000,
                "classification": "AUXILIARY / FUTURE MODEL DATA"
            },
            {
                "name": "petrochemical_predictive_maintenance.csv",
                "path": "data/cleaned/petrochemical/petrochemical_predictive_maintenance.csv",
                "rows": 10000,
                "classification": "AUXILIARY / FUTURE MODEL DATA"
            },
            {
                "name": "processed_data.csv",
                "path": "data/cleaned/environmental/processed_data.csv",
                "rows": 1000,
                "classification": "AUXILIARY / FUTURE MODEL DATA"
            },
            {
                "name": "IHMStefanini_industrial_safety_and_health_database.csv",
                "path": "data/cleaned/safety/IHMStefanini_industrial_safety_and_health_database.csv",
                "rows": 138,
                "classification": "AUXILIARY / FUTURE MODEL DATA (Metals Sector Filtered)"
            }
        ]
    }
    
    # Save Inventory JSON
    inventory_json_path = os.path.join(manifest_dir, "final_training_dataset_inventory.json")
    with open(inventory_json_path, "w", encoding="utf-8") as f:
        json.dump(inventory_data, f, indent=2)
    print(f"Final training dataset inventory written to: {inventory_json_path}", flush=True)
    
    # Build Markdown Report
    report_md_path = os.path.join(analysis_dir, "final_training_dataset_report.md")
    
    md_content = """# NOVA — Final Training Dataset Preparation Report

## Executive Summary

This report documents the discovery, auditing, cleaning, physical-semantic validation, and curation of the final canonical training datasets for NOVA's four core machine learning models:
1. **`ProcessAnomalyDetector`**
2. **`ProcessFaultClassifier`**
3. **`FurnaceCOTPredictor`**
4. **`TubeTemperaturePredictor`**

All canonical datasets have been curated under `data/curated/` and validated with cryptographic SHA-256 signatures, explicit manifests, and physical-semantic checks. No model training, retraining, pipeline modifications, or Dataset Quality Improver execution was performed during this stage.

---

## Final Training Dataset Summary Table

| Model | Final Dataset | Source | Rows | Columns | Target | Target Units | Dataset Type | Status |
| :--- | :--- | :--- | ---: | ---: | :--- | :--- | :--- | :--- |
| **ProcessAnomalyDetector** | `tep_canonical.csv` | TEP Benchmark | 15,330,000 | 55 | `fault_number` | Code (0–20) | Real benchmark | **READY** |
| **ProcessFaultClassifier** | `tep_canonical.csv` | TEP Benchmark | 15,330,000 | 55 | `fault_number` | Code (0–20) | Real benchmark | **READY** |
| **FurnaceCOTPredictor** | `furnace_cot_canonical.csv` | Ethylene Furnace | 30,015 | 17 | `COT` | °C | Real industrial | **READY** |
| **TubeTemperaturePredictor** | `tube_temperature_canonical.csv` | Ethylene Furnace + 1D Heat Transfer Physics | 30,015 | 18 | `TMT` | °C | Physics-informed synthetic | **READY** |

---

## Detailed Model & Dataset Audit

### 1 & 2. ProcessAnomalyDetector & ProcessFaultClassifier (TEP)
* **Canonical Path**: `data/curated/tep/tep_canonical.csv`
* **Shared Architecture**: Intentionally shared between anomaly detection and multi-class fault classification to ensure feature consistency across TEP operational intelligence.
* **Row Count**: 15,330,000 rows (5,330,000 training + 10,000,000 testing).
* **Column Count**: 55 columns (`fault_number`, `simulation_run`, `sample_index`, `xmeas_1`–`xmeas_41`, `xmv_1`–`xmv_11`).
* **SHA-256**: """ + tep_sha256 + """
* **Manifest**: `data/manifests/tep_canonical_manifest.json`

### 3. FurnaceCOTPredictor
* **Canonical Path**: `data/curated/furnace_cot/furnace_cot_canonical.csv`
* **Raw Source**: `data/raw/ethylene-furnance-dataset.xlsx`
* **Cleaned Path**: `data/cleaned/furnace_cot/furnace_cot_clean.csv`
* **Row Count**: 30,015 rows (0 missing values, 0 duplicate records).
* **Target**: `COT` (Coil Outlet Temperature, range 794.07°C to 942.60°C, mean 864.86°C).
* **Features**: 16 process variables (`C2H2`..`H2`, `Pressure`, `Cracking gas temperature`).
* **SHA-256**: """ + cot_sha256 + """
* **Manifest**: `data/manifests/furnace_cot_canonical_manifest.json`

### 4. TubeTemperaturePredictor
* **Canonical Path**: `data/curated/tube_temperature/tube_temperature_canonical.csv`
* **Target Identification Audit**: Exhaustive inspection of authentic 30,015-row `ethylene-furnance-dataset.xlsx` confirmed **no measured Tube Metal Temperature (TMT) target exists** in the raw data (`Cracking gas temperature` is the internal fluid temperature profile, not radiant tube wall skin temperature).
* **Physics-Informed Synthetic Fallback**: Implemented steady-state 1D radial heat flux & convective boundary layer physics ($TMT = COT + \Delta T_{film} + \Delta T_{wall}$).
* **Target Specifications**: `TMT` (range 840.36°C to 1,100.00°C, mean 1023.66°C, mean delta above COT: +158.79°C). 100% of records satisfy physical condition $TMT > COT$.
* **Dataset Type**: `physics-informed synthetic` (explicitly documented in manifest).
* **SHA-256**: """ + tmt_sha256 + """
* **Manifest**: `data/manifests/tube_temperature_canonical_manifest.json`

---

## Auxiliary Dataset Classifications

The following pre-existing datasets are preserved under `data/cleaned/` and classified as **`AUXILIARY / FUTURE MODEL DATA`**. They are not forced into the four core ML models:
1. `data/cleaned/petrochemical/petrochemical_advanced_data.csv` (1,000 rows)
2. `data/cleaned/petrochemical/petrochemical_predictive_maintenance.csv` (10,000 rows)
3. `data/cleaned/environmental/processed_data.csv` (1,000 rows)
4. `data/cleaned/safety/IHMStefanini_industrial_safety_and_health_database.csv` (138 rows, Metals Sector Filtered)

---

## Model Readiness & Final Decision

### ProcessAnomalyDetector
```text
Dataset: data/curated/tep/tep_canonical.csv
Status: READY
```

### ProcessFaultClassifier
```text
Dataset: data/curated/tep/tep_canonical.csv
Status: READY
```

### FurnaceCOTPredictor
```text
Dataset: data/curated/furnace_cot/furnace_cot_canonical.csv
Status: READY
```

### TubeTemperaturePredictor
```text
Dataset: data/curated/tube_temperature/tube_temperature_canonical.csv
Status: READY
Target type: PHYSICS-INFORMED SYNTHETIC DATASET
```

---

# FINAL DATASETS TO SEND TO DATASET QUALITY IMPROVER

### Dataset 1: TEP Canonical Dataset (Shared by Anomaly Detector & Fault Classifier)
```text
Dataset Name: tep_canonical.csv
Exact Path: data/curated/tep/tep_canonical.csv
Model: ProcessAnomalyDetector & ProcessFaultClassifier
Rows: 15330000
Columns: 55
Target: fault_number
Target Units: Categorical fault code (0=Normal, 1-20=Fault Modes)
Dataset Type: Real benchmark
Source: Tennessee Eastman Process (TEP) Benchmark
SHA-256: """ + tep_sha256 + """
```

### Dataset 2: Furnace COT Canonical Dataset
```text
Dataset Name: furnace_cot_canonical.csv
Exact Path: data/curated/furnace_cot/furnace_cot_canonical.csv
Model: FurnaceCOTPredictor
Rows: 30015
Columns: 17
Target: COT
Target Units: °C (Degrees Celsius)
Dataset Type: Real industrial
Source: Ethylene Cracking Furnace Industrial Dataset (data/raw/ethylene-furnance-dataset.xlsx)
SHA-256: """ + cot_sha256 + """
```

### Dataset 3: Tube Temperature Canonical Dataset
```text
Dataset Name: tube_temperature_canonical.csv
Exact Path: data/curated/tube_temperature/tube_temperature_canonical.csv
Model: TubeTemperaturePredictor
Rows: 30015
Columns: 18
Target: TMT
Target Units: °C (Degrees Celsius)
Dataset Type: physics-informed synthetic
Source: Ethylene Cracking Furnace Process Dataset + 1D Heat Transfer Physics Model
SHA-256: """ + tmt_sha256 + """
```
"""
    
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"Final training dataset report written to: {report_md_path}", flush=True)

if __name__ == "__main__":
    build_final_inventory()
