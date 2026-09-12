"""
ml_training/tube_temperature/dataset.py — Furnace Tube Metal Temperature (TMT) Dataset Loader.

Loads, validates, and chronologically splits the canonical tube temperature dataset:
data/curated/tube_temperature/tube_temperature_canonical.csv

Target Provenance:
- target_column: "TMT" (Tube Metal Temperature, °C)
- target_type: "physics-informed synthetic"
- Explicitly documented: Derived from 1D radial heat-transfer physics equations (film + wall gradient).
- This is NOT measured plant data and NOT a coking detector.
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

logger = logging.getLogger("nova.ml.tube_temp.dataset")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_TUBE_TEMP_PATH = (
    REPO_ROOT / "data" / "curated" / "tube_temperature" / "tube_temperature_canonical.csv"
)

# 17 Canonical input features (16 process/gas features + Coil Outlet Temperature COT)
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
    "COT",
]

TARGET_COLUMN = "TMT"
TARGET_TYPE = "physics-informed synthetic"
TARGET_UNITS = "°C"
EXPECTED_COLUMNS = CANONICAL_FEATURES + [TARGET_COLUMN]  # 18 columns


@dataclass
class TubeTempDatasetSplit:
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


def load_and_verify_tube_temp_dataset(
    filepath: Union[str, Path] = CURATED_TUBE_TEMP_PATH,
    verify_sha256: bool = False,
) -> pd.DataFrame:
    """
    Validate and load curated tube temperature dataset.
    Fails closed if the path is raw/cleaned or if target is missing.
    """
    valid_path = TrainingGate.guard(
        dataset_path=filepath,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tube_temperature",
        verify_sha256=verify_sha256,
    )

    df = pd.read_csv(valid_path)
    if len(df) == 0:
        raise DatasetIntegrityError(f"Tube temperature dataset at {valid_path} is empty.")

    # Target leakage protection: TMT must not be in feature set
    if TARGET_COLUMN in CANONICAL_FEATURES:
        raise TargetLeakageError("CRITICAL: Target 'TMT' found in input feature set!")

    logger.info("Loaded and verified %d tube temperature records from %s", len(df), valid_path)
    return df


def prepare_chronological_splits(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> TubeTempDatasetSplit:
    """
    Split the dataset chronologically into train (70%), validation (15%), and test (15%).
    Strict historical ordering: no random shuffling.
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
        "dataset_name": "Tube Temperature Canonical Curated Dataset",
        "total_samples": n,
        "train_samples": len(x_train),
        "val_samples": len(x_val),
        "test_samples": len(x_test),
        "target_column": TARGET_COLUMN,
        "target_units": TARGET_UNITS,
        "target_type": TARGET_TYPE,
        "provenance_note": (
            "Target 'TMT' is a physics-informed synthetic estimation computed via 1D radial heat transfer equations. "
            "It is NOT measured industrial plant TMT."
        ),
    }

    return TubeTempDatasetSplit(
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


def load_tube_temp_dataset(
    filepath: Union[str, Path] = CURATED_TUBE_TEMP_PATH,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> TubeTempDatasetSplit:
    """Complete loader and chronological splitter for Tube Temperature model."""
    df = load_and_verify_tube_temp_dataset(filepath=filepath)
    return prepare_chronological_splits(df=df, train_ratio=train_ratio, val_ratio=val_ratio)
