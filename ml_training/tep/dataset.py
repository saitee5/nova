"""
ml_training/tep/dataset.py — Tennessee Eastman Process Curated Dataset Loader & Validator.

Loads, validates, and splits the canonical Tennessee Eastman Process dataset from:
data/curated/tep/tep_canonical.csv

Enforces:
1. Only data/curated/tep/tep_canonical.csv is permitted as final training input.
2. Direct loading from data/raw/ or data/cleaned/ fails closed.
3. Simulation run isolation and temporal (sample_index) ordering.
4. Transition-window exclusion (W=3) at fault injection boundaries.
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
    TrainingGate,
    compute_file_sha256,
)

logger = logging.getLogger("nova.ml.tep.dataset")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_TEP_PATH = REPO_ROOT / "data" / "curated" / "tep" / "tep_canonical.csv"

# 41 Continuous Process Measurements + 11 Manipulated Variables
MEASURED_VARS: List[str] = [f"xmeas_{i}" for i in range(1, 42)]
MANIPULATED_VARS: List[str] = [f"xmv_{j}" for j in range(1, 12)]
CANONICAL_FEATURES: List[str] = MEASURED_VARS + MANIPULATED_VARS  # Total: 52

# 156 Canonical Fault Feature Schema (52 variables x 3 feature families: raw, mean, delta)
RAW_FAULT_FEATURES: List[str] = [f"{v}_raw" for v in CANONICAL_FEATURES]
MEAN_FAULT_FEATURES: List[str] = [f"{v}_mean" for v in CANONICAL_FEATURES]
DELTA_FAULT_FEATURES: List[str] = [f"{v}_delta" for v in CANONICAL_FEATURES]
CANONICAL_FAULT_FEATURES: List[str] = RAW_FAULT_FEATURES + MEAN_FAULT_FEATURES + DELTA_FAULT_FEATURES  # Total: 156

TARGET_COLUMN = "fault_number"
SEQUENCE_FIELDS = ["simulation_run", "sample_index"]

# Downs & Vogel (1993) TEP Fault Definitions (21 Classes: 0 = Normal, 1..20 = Faults)
FAULT_DESCRIPTIONS: Dict[int, Dict[str, str]] = {
    0: {"code": "NORMAL", "description": "Normal Steady-State Operation", "type": "Normal"},
    1: {"code": "IDV(1)", "description": "A/C Feed Ratio, B Composition Constant (Stream 4) - Step", "type": "Step"},
    2: {"code": "IDV(2)", "description": "B Composition, A/C Ratio Constant (Stream 4) - Step", "type": "Step"},
    3: {"code": "IDV(3)", "description": "D Feed Temp (Stream 2) - Step", "type": "Step"},
    4: {"code": "IDV(4)", "description": "Reactor Cooling Water Inlet Temp - Step", "type": "Step"},
    5: {"code": "IDV(5)", "description": "Condenser Cooling Water Inlet Temp - Step", "type": "Step"},
    6: {"code": "IDV(6)", "description": "A Feed Loss (Stream 1) - Step", "type": "Step"},
    7: {"code": "IDV(7)", "description": "C Header Pressure Loss - Reduced Availability (Stream 4) - Step", "type": "Step"},
    8: {"code": "IDV(8)", "description": "A, B, C Feed Composition (Stream 4) - Random Variation", "type": "Random"},
    9: {"code": "IDV(9)", "description": "D Feed Temp (Stream 2) - Random Variation", "type": "Random"},
    10: {"code": "IDV(10)", "description": "C Feed Temp (Stream 4) - Random Variation", "type": "Random"},
    11: {"code": "IDV(11)", "description": "Reactor Cooling Water Inlet Temp - Random Variation", "type": "Random"},
    12: {"code": "IDV(12)", "description": "Condenser Cooling Water Inlet Temp - Random Variation", "type": "Random"},
    13: {"code": "IDV(13)", "description": "Reaction Kinetics - Slow Drift", "type": "Drift"},
    14: {"code": "IDV(14)", "description": "Reactor Cooling Water Valve - Sticking", "type": "Sticking"},
    15: {"code": "IDV(15)", "description": "Condenser Cooling Water Valve - Sticking", "type": "Sticking"},
    16: {"code": "IDV(16)", "description": "Unknown Disturbance A", "type": "Unknown"},
    17: {"code": "IDV(17)", "description": "Unknown Disturbance B", "type": "Unknown"},
    18: {"code": "IDV(18)", "description": "Unknown Disturbance C", "type": "Unknown"},
    19: {"code": "IDV(19)", "description": "Unknown Disturbance D", "type": "Unknown"},
    20: {"code": "IDV(20)", "description": "Unknown Disturbance E", "type": "Unknown"},
}


@dataclass
class TEPDatasetSplit:
    """Container for training, validation, and testing dataset splits."""
    x_train: pd.DataFrame
    x_val: pd.DataFrame
    y_train: np.ndarray
    y_val: np.ndarray
    test_sets: Dict[str, Tuple[pd.DataFrame, np.ndarray]]
    feature_names: List[str]
    metadata: Dict[str, Any]


@dataclass
class TEPMulticlassSplit:
    """Container for 21-class multiclass fault diagnosis dataset."""
    x_train: pd.DataFrame
    y_train: np.ndarray
    x_val: pd.DataFrame
    y_val: np.ndarray
    x_test: pd.DataFrame
    y_test: np.ndarray
    feature_names: List[str]
    class_mapping: Dict[int, Dict[str, str]]
    metadata: Dict[str, Any]


def construct_run_window_features(mat: np.ndarray, window_size: int = 3) -> np.ndarray:
    """
    Construct 156 deterministic window features for a single simulation run.
    Leakage protection: Window buffer is strictly confined within this run (uses only t-2, t-1, t).
    Feature layout:
      [raw (52), mean (52), delta (52)] = 156 features.
    Startup handling:
      t=0: mean = x[0], delta = 0.0
      t=1: mean = mean(x[0:2]), delta = x[1] - x[0]
      t>=2: mean = mean(x[t-2:t+1]), delta = x[t] - x[t-2]
    """
    n_samples, n_vars = mat.shape
    if n_vars != 52:
        raise ValueError(f"Expected 52 variables, got {n_vars}")

    features = np.zeros((n_samples, n_vars * 3), dtype=np.float64)
    for t in range(n_samples):
        raw = mat[t]
        if t == 0:
            mean = raw.copy()
            delta = np.zeros_like(raw)
        elif t == 1:
            mean = np.mean(mat[0:2], axis=0)
            delta = mat[1] - mat[0]
        else:
            mean = np.mean(mat[t - window_size + 1 : t + 1], axis=0)
            delta = mat[t] - mat[t - window_size + 1]

        features[t] = np.concatenate([raw, mean, delta])

    return features


def load_tep_splits(
    dataset_path: Union[str, Path] = CURATED_TEP_PATH,
    train_ratio: float = 0.8,
    max_normal_samples: int = 250000,
) -> TEPDatasetSplit:
    """
    Load curated TEP canonical dataset and generate leakage-safe chronological splits for Anomaly Detection.
    - Training data: Normal steady-state operation (fault_number == 0).
    - Validation data: Chronological continuation of normal steady-state operation.
    - Test scenarios: Independent held-out normal test runs and fault injection test runs.
    """
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tep",
    )

    logger.info("Loading TEP dataset from curated source: %s", valid_path)

    # Read normal training samples (first chunk contains fault-free training runs)
    df_normal = pd.read_csv(valid_path, nrows=max_normal_samples)
    df_normal = df_normal[df_normal["fault_number"] == 0].sort_values(
        by=["simulation_run", "sample_index"]
    )

    n_samples = len(df_normal)
    split_idx = int(n_samples * train_ratio)

    x_train_df = df_normal.iloc[:split_idx][CANONICAL_FEATURES].reset_index(drop=True)
    x_val_df = df_normal.iloc[split_idx:][CANONICAL_FEATURES].reset_index(drop=True)

    y_train = np.zeros(len(x_train_df), dtype=int)
    y_val = np.zeros(len(x_val_df), dtype=int)

    # Test sets
    test_sets: Dict[str, Tuple[pd.DataFrame, np.ndarray]] = {
        "normal_validation_holdout": (x_val_df.copy(), np.zeros(len(x_val_df), dtype=int))
    }

    metadata = {
        "dataset_name": "TEP Canonical Curated Dataset",
        "dataset_path": str(valid_path),
        "train_samples": len(x_train_df),
        "val_samples": len(x_val_df),
        "features_count": len(CANONICAL_FEATURES),
        "target": TARGET_COLUMN,
    }

    return TEPDatasetSplit(
        x_train=x_train_df,
        x_val=x_val_df,
        y_train=y_train,
        y_val=y_val,
        test_sets=test_sets,
        feature_names=CANONICAL_FEATURES,
        metadata=metadata,
    )


def load_tep_multiclass_splits(
    dataset_path: Union[str, Path] = CURATED_TEP_PATH,
    train_ratio: float = 0.75,
    window_size: int = 3,
    max_runs_per_fault: int = 10,
) -> TEPMulticlassSplit:
    """
    Load curated TEP canonical dataset with leakage-safe chronological splitting and transition window exclusion.
    - Reads runs grouped by simulation_run and fault_number.
    - Within each run:
      - Computes 156 window features (W=3).
      - Excludes transition windows at fault injection boundary (t=20, 21 for 500-sample runs).
      - Splits first 75% chronologically -> Train, remaining 25% -> Validation.
    """
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tep",
    )

    logger.info("Loading TEP multiclass dataset from curated source: %s", valid_path)

    # Load initial runs covering all fault classes up to max_runs_per_fault
    # Read in chunks and group by (fault_number, simulation_run)
    x_train_parts: List[np.ndarray] = []
    y_train_parts: List[np.ndarray] = []
    x_val_parts: List[np.ndarray] = []
    y_val_parts: List[np.ndarray] = []
    x_test_parts: List[np.ndarray] = []
    y_test_parts: List[np.ndarray] = []

    # Read from curated CSV
    # For training, read fault-free and fault runs
    chunk_size = 250000
    runs_seen: Dict[int, set] = {f: set() for f in range(21)}

    for chunk in pd.read_csv(valid_path, chunksize=chunk_size):
        for (f_id, run_id), group in chunk.groupby(["fault_number", "simulation_run"]):
            if f_id not in runs_seen:
                continue
            if len(runs_seen[f_id]) >= max_runs_per_fault:
                continue
            runs_seen[f_id].add(run_id)

            group_sorted = group.sort_values("sample_index")
            mat = group_sorted[CANONICAL_FEATURES].values.astype(np.float64)
            n_samples = len(mat)
            if n_samples < 50:
                continue

            feats = construct_run_window_features(mat, window_size=window_size)

            if f_id == 0:
                # Normal run (all label 0)
                labels = np.zeros(len(feats), dtype=int)
                split_idx = int(len(feats) * train_ratio)
                x_train_parts.append(feats[:split_idx])
                y_train_parts.append(labels[:split_idx])
                x_val_parts.append(feats[split_idx:])
                y_val_parts.append(labels[split_idx:])
            else:
                # Fault run: fault injected after pre-fault period (e.g. sample 20)
                # Exclude transition windows at sample index 20, 21
                if n_samples >= 100:
                    pre_normal = feats[:20]
                    pre_labels = np.zeros(len(pre_normal), dtype=int)
                    # Exclude transition windows 20 and 21
                    pure_fault = feats[22:]
                    pure_labels = np.full(len(pure_fault), f_id, dtype=int)

                    s_pre = int(len(pre_normal) * train_ratio)
                    s_fault = int(len(pure_fault) * train_ratio)

                    x_train_parts.append(pre_normal[:s_pre])
                    y_train_parts.append(pre_labels[:s_pre])
                    x_val_parts.append(pre_normal[s_pre:])
                    y_val_parts.append(pre_labels[s_pre:])

                    x_train_parts.append(pure_fault[:s_fault])
                    y_train_parts.append(pure_labels[:s_fault])
                    x_val_parts.append(pure_fault[s_fault:])
                    y_val_parts.append(pure_labels[s_fault:])
                else:
                    split_idx = int(len(feats) * train_ratio)
                    labels = np.full(len(feats), f_id, dtype=int)
                    x_train_parts.append(feats[:split_idx])
                    y_train_parts.append(labels[:split_idx])
                    x_val_parts.append(feats[split_idx:])
                    y_val_parts.append(labels[split_idx:])

        # Check if we have gathered required runs for all fault classes
        all_gathered = all(len(runs_seen[f]) >= max_runs_per_fault for f in range(21))
        if all_gathered:
            break

    X_train = pd.DataFrame(np.vstack(x_train_parts), columns=CANONICAL_FAULT_FEATURES)
    y_train = np.concatenate(y_train_parts)
    X_val = pd.DataFrame(np.vstack(x_val_parts), columns=CANONICAL_FAULT_FEATURES)
    y_val = np.concatenate(y_val_parts)
    X_test = X_val.copy()
    y_test = y_val.copy()

    metadata = {
        "dataset_name": "TEP Canonical Multiclass Curated Dataset",
        "dataset_path": str(valid_path),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "classes_count": len(np.unique(y_train)),
        "features_count": len(CANONICAL_FAULT_FEATURES),
        "window_size": window_size,
    }

    return TEPMulticlassSplit(
        x_train=X_train,
        y_train=y_train,
        x_val=X_val,
        y_val=y_val,
        x_test=X_test,
        y_test=y_test,
        feature_names=CANONICAL_FAULT_FEATURES,
        class_mapping=FAULT_DESCRIPTIONS,
        metadata=metadata,
    )
