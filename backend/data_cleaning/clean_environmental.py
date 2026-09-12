"""
Environmental Emission & Predictive Maintenance Data Cleaning Module for NOVA.
Cleans petrochemical_predictive_maintenance.csv and processed_data.csv.
Deduplicates records, handles artifact columns, fixes impossible negative ages,
imputes missing telemetry safely, and exports cleaned datasets under data/cleaned/environmental/.
"""

import os
import pandas as pd
import numpy as np

ENV_RAW_DIR = "data/raw/environmental"
ENV_CLEAN_DIR = "data/cleaned/environmental"

MAINTENANCE_RAW = os.path.join(ENV_RAW_DIR, "petrochemical_predictive_maintenance.csv")
MAINTENANCE_CLEAN = os.path.join(ENV_CLEAN_DIR, "petrochemical_predictive_maintenance.csv")

PROCESSED_RAW = os.path.join(ENV_RAW_DIR, "processed_data.csv")
PROCESSED_CLEAN = os.path.join(ENV_CLEAN_DIR, "processed_data.csv")

def clean_environmental_maintenance():
    print(f"[ENVIRONMENTAL] Processing {MAINTENANCE_RAW}...")
    df = pd.read_csv(MAINTENANCE_RAW)
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Column Normalization to lowercase snake_case
    df.columns = [col.strip().lower() for col in df.columns]
    
    # 2. Timestamp Normalization
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 3. Deduplication
    dups = df.duplicated().sum()
    if dups > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        
    # 4. Check Missing Values & Impossible Values
    null_count_before = int(df.isnull().sum().sum())
    
    # Fix impossible negative catalyst age values
    if 'catalyst_age' in df.columns:
        # Catalyst age cannot be negative
        df['catalyst_age'] = df['catalyst_age'].apply(lambda x: 0.0 if pd.notnull(x) and x < 0 else x)
        
    # Impute missing numerical values deterministically using median to ensure usable telemetry
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        if df[col].isnull().sum() > 0:
            df[col] = df[col].fillna(df[col].median())
            
    # Impute missing categorical values
    cat_cols = df.select_dtypes(include=['object']).columns
    for col in cat_cols:
        if df[col].isnull().sum() > 0:
            df[col] = df[col].fillna(df[col].mode()[0])
            
    os.makedirs(ENV_CLEAN_DIR, exist_ok=True)
    df.to_csv(MAINTENANCE_CLEAN, index=False)
    
    rows_after = len(df)
    
    print(f"[ENVIRONMENTAL] Cleaned maintenance dataset: {rows_before} -> {rows_after} rows, {dups} dups removed, {null_count_before} nulls resolved.")
    
    return {
        "raw_file": MAINTENANCE_RAW,
        "cleaned_file": MAINTENANCE_CLEAN,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df.columns),
        "duplicates_removed": int(dups),
        "missing_values": int(null_count_before),
        "exclusions": 0,
        "classification": "Numerical Time-Series & Environmental Predictive Maintenance Data"
    }

def clean_environmental_processed():
    print(f"[ENVIRONMENTAL] Processing {PROCESSED_RAW}...")
    df = pd.read_csv(PROCESSED_RAW)
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Remove index artifact columns
    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])
        
    # 2. Column Normalization
    df.columns = [col.strip().lower() for col in df.columns]
    
    # 3. Timestamp Normalization
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
    # 4. Deduplication & Null check
    dups = df.duplicated().sum()
    if dups > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        
    null_count = int(df.isnull().sum().sum())
    
    os.makedirs(ENV_CLEAN_DIR, exist_ok=True)
    df.to_csv(PROCESSED_CLEAN, index=False)
    
    rows_after = len(df)
    
    print(f"[ENVIRONMENTAL] Cleaned processed dataset: {rows_before} -> {rows_after} rows.")
    
    return {
        "raw_file": PROCESSED_RAW,
        "cleaned_file": PROCESSED_CLEAN,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df.columns),
        "duplicates_removed": int(dups),
        "missing_values": null_count,
        "exclusions": 0,
        "classification": "Environmental & Predictive Maintenance Feature-Engineered Dataset"
    }

def clean_all_environmental():
    res1 = clean_environmental_maintenance()
    res2 = clean_environmental_processed()
    return [res1, res2]

if __name__ == "__main__":
    clean_all_environmental()
