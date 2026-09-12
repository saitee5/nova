"""
Tennessee Eastman Process (TEP) Data Cleaning Module for NOVA.
Handles parsing of RData benchmark files, schema normalization, type casting,
and exporting to clean CSV datasets under data/cleaned/tep/.
"""

import os
import pyreadr
import pandas as pd

TEP_RAW_DIR = "data/raw/tep"
TEP_CLEAN_DIR = "data/cleaned/tep"

TEP_FILES = {
    "TEP_FaultFree_Training.RData": ("fault_free_training", "tep_fault_free_training.csv"),
    "TEP_FaultFree_Testing.RData": ("fault_free_testing", "tep_fault_free_testing.csv"),
    "TEP_Faulty_Training.RData": ("faulty_training", "tep_faulty_training.csv"),
    "TEP_Faulty_Testing.RData": ("faulty_testing", "tep_faulty_testing.csv")
}

def clean_tep_file(raw_filename, key_name, clean_filename):
    raw_path = os.path.join(TEP_RAW_DIR, raw_filename)
    clean_path = os.path.join(TEP_CLEAN_DIR, clean_filename)
    
    print(f"[TEP] Processing {raw_filename}...")
    rdata = pyreadr.read_r(raw_path)
    df = rdata[key_name]
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Normalize Column Names to snake_case
    col_mapping = {
        'faultNumber': 'fault_number',
        'simulationRun': 'simulation_run',
        'sample': 'sample_index'
    }
    df = df.rename(columns=col_mapping)
    
    # 2. Type Casting & Normalization
    df['fault_number'] = df['fault_number'].astype(int)
    df['simulation_run'] = df['simulation_run'].astype(int)
    df['sample_index'] = df['sample_index'].astype(int)
    
    # 3. Check for duplicates and missing values
    dups = df.duplicated().sum()
    if dups > 0:
        df = df.drop_duplicates().reset_index(drop=True)
    
    null_count = df.isnull().sum().sum()
    
    # 4. Save cleaned output
    os.makedirs(TEP_CLEAN_DIR, exist_ok=True)
    df.to_csv(clean_path, index=False)
    
    rows_after = len(df)
    
    print(f"[TEP] Cleaned {clean_filename}: {rows_before} -> {rows_after} rows, {null_count} nulls, {dups} dups removed.")
    
    return {
        "raw_file": raw_path,
        "cleaned_file": clean_path,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df.columns),
        "duplicates_removed": int(dups),
        "missing_values": int(null_count),
        "exclusions": 0,
        "classification": "Numerical Time-Series / Process Anomaly Benchmark Data"
    }

def clean_all_tep():
    os.makedirs(TEP_CLEAN_DIR, exist_ok=True)
    results = []
    for raw_fn, (key, clean_fn) in TEP_FILES.items():
        res = clean_tep_file(raw_fn, key, clean_fn)
        results.append(res)
    return results

if __name__ == "__main__":
    clean_all_tep()
