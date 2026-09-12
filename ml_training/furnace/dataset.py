"""
ml_training/furnace/dataset.py — Industrial Ethylene Cracking Furnace Curated Dataset Loader.

Loads, validates, and chronologically splits the canonical ethylene cracking furnace dataset:
data/curated/furnace_cot/furnace_cot_canonical.csv

Enforces:
1. Datasets MUST reside strictly under data/curated/
2. Direct loading from data/raw/ or data/cleaned/ is strictly forbidden and fails closed.
3. Frozen 16-feature schema and COT target variable.
4. Chronological 70% train / 15% val / 15% test split without future leakage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from ml_training.common.training_gate import (
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TargetLeakageError,
    TrainingGate,
    compute_file_sha256,
)

logger = logging.getLogger("nova.ml.furnace.dataset")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_FURNACE_COT_PATH = (
    REPO_ROOT / "data" / "curated" / "furnace_cot" / "furnace_cot_canonical.csv"
)

# 16 Canonical input features in frozen order (matching furnace_cot_canonical.csv headers)
CANONICAL_FEATURES: List[str] = [
    "C2H2",
    "C2H4",
    "C2H6",
    "C3H6",
    "C3H8",
    "C4H6",
    "C4H8",
    "C6H6",
    "C7H8",
    "C8H10",
    "C8H8",
    "CH4",
    "H2O",
    "H2",
    "Pressure",
    "Cracking gas temperature",
]

# Lowercase snake_case alias map for flexible production inference
FEATURE_ALIASES: Dict[str, str] = {
    "c2h2": "C2H2",
    "c2h4": "C2H4",
    "c2h6": "C2H6",
    "c3h6": "C3H6",
    "c3h8": "C3H8",
    "c4h6": "C4H6",
    "c4h8": "C4H8",
    "c6h6": "C6H6",
    "c7h8": "C7H8",
    "c8h10": "C8H10",
    "c8h8": "C8H8",
    "ch4": "CH4",
    "h2o": "H2O",
    "h2": "H2",
    "furnace_pressure": "Pressure",
    "pressure": "Pressure",
    "cracking_gas_temperature": "Cracking gas temperature",
    "cracking_gas_temp": "Cracking gas temperature",
    "cot": "COT",
    "coil_outlet_temperature": "COT",
}

CANONICAL_FEATURE_NAMES = CANONICAL_FEATURES
TARGET_COLUMN = "COT"
TARGET_NAME = TARGET_COLUMN
EXPECTED_COLUMNS = CANONICAL_FEATURES + [TARGET_COLUMN]  # 17 columns
EXPECTED_RAW_COLUMNS = EXPECTED_COLUMNS
RAW_DATASET_PATH = CURATED_FURNACE_COT_PATH
EXPECTED_SHA256 = "55c0a1c1653e8b034a0e0a03b1373879466d0c2001e0cbe08d03205ca4ddd5b8"



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
    metadata: Dict[str, Any]


def load_and_verify_furnace_dataset(
    filepath: Union[str, Path] = CURATED_FURNACE_COT_PATH,
    verify_sha256: bool = False,
) -> pd.DataFrame:
    """
    Validate and load curated ethylene cracking furnace dataset.
    Fails closed if the path is in data/raw or data/cleaned, or if columns are missing.
    """
    valid_path = TrainingGate.guard(
        dataset_path=filepath,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="furnace_cot",
        verify_sha256=verify_sha256,
    )

    df = pd.read_csv(valid_path)
    if len(df) == 0:
        raise DatasetIntegrityError(f"Furnace dataset at {valid_path} is empty.")

    # Strict target leakage check
    if TARGET_COLUMN in CANONICAL_FEATURES:
        raise TargetLeakageError("CRITICAL: Target column 'COT' is present in feature list!")

    logger.info("Loaded and verified %d furnace records from %s", len(df), valid_path)
    return df


def prepare_chronological_splits(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> FurnaceDatasetSplit:
    """
    Split the dataset chronologically into train (70%), validation (15%), and test (15%).
    Strict historical ordering: no shuffling, no future leakage.
    """
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    x_train = train_df[CANONICAL_FEATURES].copy()
    y_train = train_df[TARGET_COLUMN].copy()

    x_val = val_df[CANONICAL_FEATURES].copy()
    y_val = val_df[TARGET_COLUMN].copy()

    x_test = test_df[CANONICAL_FEATURES].copy()
    y_test = test_df[TARGET_COLUMN].copy()

    metadata = {
        "dataset_name": "Furnace COT Canonical Curated Dataset",
        "total_samples": n,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
        "target_column": TARGET_COLUMN,
        "target_units": "°C",
        "target_type": "Real industrial measured continuous variable",
    }

    return FurnaceDatasetSplit(
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        x_test=x_test,
        y_test=y_test,
        feature_names=CANONICAL_FEATURES,
        target_name=TARGET_COLUMN,
        metadata=metadata,
    )


def load_furnace_cot_dataset(
    filepath: Union[str, Path] = CURATED_FURNACE_COT_PATH,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> FurnaceDatasetSplit:
    """Complete loader and chronological splitter for Furnace COT model."""
    df = load_and_verify_furnace_dataset(filepath=filepath)
    return prepare_chronological_splits(df=df, train_ratio=train_ratio, val_ratio=val_ratio)
