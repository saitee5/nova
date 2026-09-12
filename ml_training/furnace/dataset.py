"""
ml_training/furnace/dataset.py — Industrial Ethylene Cracking Furnace Dataset Loader.

Loads, validates, and splits the authentic 30,015-sample ethylene cracking furnace dataset
(Figshare Article 29804525, DOI: 10.6084/m9.figshare.29804525).

Features:
- 12 Hydrocarbon stream component yields (C2H2 to C8H8, CH4)
- 2 Chemical components (H2O dilution steam, H2 hydrogen)
- 2 Process parameters (furnace_pressure, cracking_gas_temperature)
- 1 Target parameter (coil_outlet_temperature, °C)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("furnace.dataset")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DATA_PATH = REPO_ROOT / "data" / "raw" / "furnace_cot" / "ethylene_furnace_30015_samples.xlsx"

EXPECTED_SHA256 = "8591f494a6dabf63e28084c191f430993fc03781a25644941c601dc7561f6371"

# Mapping from raw Excel column names to clean canonical lower-snake-case
COLUMN_MAPPING = {
    "C2H2": "c2h2",
    "C2H4": "c2h4",
    "C2H6": "c2h6",
    "C3H6": "c3h6",
    "C3H8": "c3h8",
    "C4H6": "c4h6",
    "C4H8": "c4h8",
    "C6H6": "c6h6",
    "C7H8": "c7h8",
    "C8H10": "c8h10",
    "C8H8": "c8h8",
    "CH4": "ch4",
    "H2O": "h2o",
    "H2": "h2",
    "Pressure": "furnace_pressure",
    "Cracking gas temperature": "cracking_gas_temperature",
    "COT": "coil_outlet_temperature",
}

CANONICAL_FEATURE_NAMES = [
    "c2h2", "c2h4", "c2h6", "c3h6", "c3h8",
    "c4h6", "c4h8", "c6h6", "c7h8", "c8h10",
    "c8h8", "ch4", "h2o", "h2",
    "furnace_pressure", "cracking_gas_temperature",
]
CANONICAL_FEATURES = CANONICAL_FEATURE_NAMES
TARGET_NAME = "coil_outlet_temperature"
TARGET_COLUMN = "COT"
RAW_DATASET_PATH = RAW_DATA_PATH
EXPECTED_RAW_COLUMNS = list(COLUMN_MAPPING.keys())


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class FurnaceDatasetSplit:
    """Container for chronological train, validation, and test splits."""
    x_train: pd.DataFrame
    y_train: pd.Series
    x_val: pd.DataFrame
    y_val: pd.Series
    x_test: pd.DataFrame
    y_test: pd.Series
    feature_names: List[str]
    target_name: str
    metadata: Dict[str, any]


def load_furnace_cot_dataset(
    filepath: Path = RAW_DATA_PATH,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> FurnaceDatasetSplit:
    """
    Load, validate, and chronologically split the ethylene cracking furnace dataset.
    - 70% earliest -> Training set (21,010 samples)
    - 15% intermediate -> Validation set (4,502 samples)
    - 15% latest -> Held-out Test set (4,503 samples)
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Furnace dataset file not found at {filepath}")

    actual_hash = compute_file_sha256(filepath)
    if actual_hash != EXPECTED_SHA256:
        raise ValueError(
            f"Integrity check failed for {filepath.name}. Expected {EXPECTED_SHA256}, got {actual_hash}"
        )

    df = pd.read_excel(filepath)
    if df.shape != (30015, 17):
        raise ValueError(f"Expected shape (30015, 17) for furnace dataset, got {df.shape}")

    # Rename columns to canonical names
    df = df.rename(columns=COLUMN_MAPPING)

    # Check for missing values
    if df.isnull().any().any():
        raise ValueError("Unexpected missing values encountered in furnace dataset.")

    # Chronological splitting (no shuffling to prevent temporal data leakage)
    n_total = len(df)
    train_end = int(n_total * train_ratio)
    val_end = int(n_total * (train_ratio + val_ratio))

    df_train = df.iloc[:train_end].copy()
    df_val = df.iloc[train_end:val_end].copy()
    df_test = df.iloc[val_end:].copy()

    x_train = df_train[CANONICAL_FEATURE_NAMES]
    y_train = df_train[TARGET_NAME]

    x_val = df_val[CANONICAL_FEATURE_NAMES]
    y_val = df_val[TARGET_NAME]

    x_test = df_test[CANONICAL_FEATURE_NAMES]
    y_test = df_test[TARGET_NAME]

    metadata = {
        "dataset_name": "Industrial Ethylene Cracking Furnace Telemetry (30,015 sets)",
        "source": "Figshare Article 29804525 / PLOS ONE Benchmark",
        "sha256": actual_hash,
        "total_samples": n_total,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
        "features_count": len(CANONICAL_FEATURE_NAMES),
        "target": TARGET_NAME,
        "target_unit": "celsius",
        "target_mean": float(df[TARGET_NAME].mean()),
        "target_std": float(df[TARGET_NAME].std()),
        "target_min": float(df[TARGET_NAME].min()),
        "target_max": float(df[TARGET_NAME].max()),
    }

    logger.info(
        "Loaded furnace dataset: %d train, %d val, %d test samples across %d features",
        len(x_train),
        len(x_val),
        len(x_test),
        len(CANONICAL_FEATURE_NAMES),
    )

    return FurnaceDatasetSplit(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        x_test=x_test,
        y_test=y_test,
        feature_names=list(CANONICAL_FEATURE_NAMES),
        target_name=TARGET_NAME,
        metadata=metadata,
    )


def load_and_verify_furnace_dataset(filepath: Path = RAW_DATA_PATH) -> pd.DataFrame:
    """Load and cryptographically verify authentic furnace dataset."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset missing at {filepath}")
    sha = compute_file_sha256(filepath)
    if sha != EXPECTED_SHA256:
        raise ValueError(f"Checksum mismatch: expected {EXPECTED_SHA256}, got {sha}")
    df = pd.read_excel(filepath)
    if df.shape != (30015, 17):
        raise ValueError(f"Unexpected shape {df.shape}")
    return df


def prepare_chronological_splits(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> FurnaceDatasetSplit:
    """Chronologically split DataFrame into train, val, test splits."""
    df_clean = df.rename(columns=COLUMN_MAPPING) if "COT" in df.columns else df.copy()
    n_total = len(df_clean)
    train_end = int(n_total * train_ratio)
    val_end = int(n_total * (train_ratio + val_ratio))

    df_train = df_clean.iloc[:train_end].copy()
    df_val = df_clean.iloc[train_end:val_end].copy()
    df_test = df_clean.iloc[val_end:].copy()

    x_train = df_train[CANONICAL_FEATURE_NAMES]
    y_train = df_train[TARGET_NAME]
    x_val = df_val[CANONICAL_FEATURE_NAMES]
    y_val = df_val[TARGET_NAME]
    x_test = df_test[CANONICAL_FEATURE_NAMES]
    y_test = df_test[TARGET_NAME]

    metadata = {
        "total_samples": n_total,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
    }

    return FurnaceDatasetSplit(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        x_test=x_test,
        y_test=y_test,
        feature_names=list(CANONICAL_FEATURE_NAMES),
        target_name=TARGET_NAME,
        metadata=metadata,
    )
