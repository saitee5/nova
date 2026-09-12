"""
Industrial Safety and Health Analytics Data Cleaning Module for NOVA.
Cleans industrial safety datasets, filters strictly for metal-industry records
(Industry Sector == 'Metals'), excludes mining and non-metal records with explicit logging,
deduplicates records, normalizes schemas, and exports to data/cleaned/safety/.
"""

import os
import pandas as pd

SAFETY_RAW_DIR = "data/raw/safety"
SAFETY_CLEAN_DIR = "data/cleaned/safety"

BASE_RAW = os.path.join(SAFETY_RAW_DIR, "IHMStefanini_industrial_safety_and_health_database.csv")
BASE_CLEAN = os.path.join(SAFETY_CLEAN_DIR, "IHMStefanini_industrial_safety_and_health_database.csv")

DESC_RAW = os.path.join(SAFETY_RAW_DIR, "IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv")
DESC_CLEAN = os.path.join(SAFETY_CLEAN_DIR, "IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv")

def clean_safety_base():
    print(f"[SAFETY] Processing {BASE_RAW}...")
    df = pd.read_csv(BASE_RAW)
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Column Normalization
    col_mapping = {
        'Data': 'timestamp',
        'Countries': 'country',
        'Local': 'plant_location',
        'Industry Sector': 'industry_sector',
        'Accident Level': 'accident_level',
        'Potential Accident Level': 'potential_accident_level',
        'Genre': 'gender',
        'Employee ou Terceiro': 'employee_or_third_party',
        'Risco Critico': 'critical_risk'
    }
    df = df.rename(columns=col_mapping)
    
    # 2. Timestamp Normalization
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 3. Industry Sector Audit & Filtering (Metal Industry Records ONLY)
    sector_counts_before = df['industry_sector'].value_counts().to_dict()
    mining_excluded = sector_counts_before.get('Mining', 0)
    others_excluded = sector_counts_before.get('Others', 0)
    total_excluded = mining_excluded + others_excluded
    
    # Retain metal-industry records only
    df_metals = df[df['industry_sector'].str.strip() == 'Metals'].copy()
    
    # 4. Deduplication on Metals records
    dups = df_metals.duplicated().sum()
    if dups > 0:
        df_metals = df_metals.drop_duplicates().reset_index(drop=True)
        
    null_count = int(df_metals.isnull().sum().sum())
    
    os.makedirs(SAFETY_CLEAN_DIR, exist_ok=True)
    df_metals.to_csv(BASE_CLEAN, index=False)
    
    rows_after = len(df_metals)
    
    print(f"[SAFETY] Cleaned safety base dataset: {rows_before} -> {rows_after} rows. Excluded Mining: {mining_excluded}, Others: {others_excluded}. Dups removed: {dups}.")
    
    return {
        "raw_file": BASE_RAW,
        "cleaned_file": BASE_CLEAN,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df_metals.columns),
        "duplicates_removed": int(dups),
        "missing_values": null_count,
        "exclusions": total_excluded,
        "exclusion_details": f"Excluded {mining_excluded} Mining records and {others_excluded} Others records to retain only Metal-industry safety records.",
        "classification": "Event / Incident & Industrial Safety Analytics Data"
    }

def clean_safety_desc():
    print(f"[SAFETY] Processing {DESC_RAW}...")
    df = pd.read_csv(DESC_RAW)
    
    rows_before = len(df)
    cols_before = len(df.columns)
    
    # 1. Drop index artifact column
    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])
        
    # 2. Column Normalization
    col_mapping = {
        'Data': 'timestamp',
        'Countries': 'country',
        'Local': 'plant_location',
        'Industry Sector': 'industry_sector',
        'Accident Level': 'accident_level',
        'Potential Accident Level': 'potential_accident_level',
        'Genre': 'gender',
        'Employee or Third Party': 'employee_or_third_party',
        'Critical Risk': 'critical_risk',
        'Description': 'description'
    }
    df = df.rename(columns=col_mapping)
    
    # 3. Timestamp Normalization
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 4. Industry Sector Audit & Filtering (Metal Industry Records ONLY)
    sector_counts_before = df['industry_sector'].value_counts().to_dict()
    mining_excluded = sector_counts_before.get('Mining', 0)
    others_excluded = sector_counts_before.get('Others', 0)
    total_excluded = mining_excluded + others_excluded
    
    # Retain metal-industry records only
    df_metals = df[df['industry_sector'].str.strip() == 'Metals'].copy()
    
    # 5. Deduplication
    dups = df_metals.duplicated().sum()
    if dups > 0:
        df_metals = df_metals.drop_duplicates().reset_index(drop=True)
        
    null_count = int(df_metals.isnull().sum().sum())
    
    os.makedirs(SAFETY_CLEAN_DIR, exist_ok=True)
    df_metals.to_csv(DESC_CLEAN, index=False)
    
    rows_after = len(df_metals)
    
    print(f"[SAFETY] Cleaned safety description dataset: {rows_before} -> {rows_after} rows. Excluded Mining: {mining_excluded}, Others: {others_excluded}.")
    
    return {
        "raw_file": DESC_RAW,
        "cleaned_file": DESC_CLEAN,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": cols_before,
        "columns_after": len(df_metals.columns),
        "duplicates_removed": int(dups),
        "missing_values": null_count,
        "exclusions": total_excluded,
        "exclusion_details": f"Excluded {mining_excluded} Mining records and {others_excluded} Others records to retain only Metal-industry safety records with accident descriptions.",
        "classification": "Event / Incident & Industrial Safety Analytics Data (with Incident Descriptions)"
    }

def clean_all_safety():
    res1 = clean_safety_base()
    res2 = clean_safety_desc()
    return [res1, res2]

if __name__ == "__main__":
    clean_all_safety()
