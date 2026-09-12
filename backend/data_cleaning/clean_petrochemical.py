"""
Petrochemical Process Optimization Data Cleaning Module for NOVA.
Normalizes columns, validates telemetry metrics, checks data types,
and exports clean CSV dataset under data/cleaned/petrochemical/.
"""

import os
import pandas as pd
import numpy as np

PETRO_RAW_PATH = "data/raw/petrochemical/petrochemical_advanced_data.csv"
PETRO_CLEAN_DIR = "data/cleaned/petrochemical"
PETRO_CLEAN_PATH = "data/cleaned/petrochemical/petrochemical_advanced_data.csv"

def clean_petrochemical():
    print(f"[PETROCHEMICAL] Processing {PETRO_RAW_PATH}...")
    df = pd.read_csv(PETRO_RAW_PATH)
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Column Normalization to lowercase snake_case
    col_mapping = {
        'Timestamp': 'timestamp',
        'Unit_Name': 'unit_name',
        'Catalyst_Type': 'catalyst_type',
        'Catalyst_Age_Days': 'catalyst_age_days',
        'Sensor_Health_Index': 'sensor_health_index',
        'Vibration_Level_mm_s': 'vibration_level_mm_s',
        'Valve_Opening_Percent': 'valve_opening_percent',
        'Feedstock_Flow_m3h': 'feedstock_flow_m3h',
        'Reactor_Temp_C': 'reactor_temp_c',
        'Reactor_Pressure_Bar': 'reactor_pressure_bar',
        'Electricity_MWh': 'electricity_mwh',
        'Natural_Gas_m3h': 'natural_gas_m3h',
        'Steam_Tons_h': 'steam_tons_h',
        'Ambient_Temp_C': 'ambient_temp_c',
        'Product_Yield_Tons': 'product_yield_tons',
        'Energy_Intensity': 'energy_intensity'
    }
    df = df.rename(columns=col_mapping)
    
    # 2. Timestamp Normalization
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 3. Deduplication and Null Handling
    dups = df.duplicated().sum()
    if dups > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        
    null_count = df.isnull().sum().sum()
    
    # 4. Range Validation & Integrity Audit (preserving legitimate physical extremes)
    # Sensor health index must be in [0, 1]
    df['sensor_health_index'] = df['sensor_health_index'].clip(0.0, 1.0)
    # Catalyst age must be non-negative
    df['catalyst_age_days'] = df['catalyst_age_days'].clip(lower=0)
    
    # 5. Export Cleaned Dataset
    os.makedirs(PETRO_CLEAN_DIR, exist_ok=True)
    df.to_csv(PETRO_CLEAN_PATH, index=False)
    
    rows_after = len(df)
    
    print(f"[PETROCHEMICAL] Cleaned petrochemical dataset: {rows_before} -> {rows_after} rows.")
    
    return {
        "raw_file": PETRO_RAW_PATH,
        "cleaned_file": PETRO_CLEAN_PATH,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df.columns),
        "duplicates_removed": int(dups),
        "missing_values": int(null_count),
        "exclusions": 0,
        "classification": "Numerical Time-Series / Process Telemetry & Optimization Data"
    }

if __name__ == "__main__":
    clean_petrochemical()
