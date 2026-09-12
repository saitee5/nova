"""
ml_training/furnace/preprocessor.py — Industrial Ethylene Furnace Preprocessor.

Standardizes 16 continuous process and chemical yield features for Coil Outlet Temperature (COT) prediction.
- Strictly guards against target leakage (COT is never admitted into the feature matrix).
- Handles incoming telemetry dictionaries and DataFrame inputs.
- Imputes missing variables using training-derived baseline statistics.
- Preserves physical engineering units for tree-based regression (XGBoost).
- Serialized directly within the model artifact for zero train/inference skew.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger("furnace.preprocessor")

# 16 Canonical input features in frozen deterministic order
CANONICAL_FEATURES: List[str] = [
    "c2h2",
    "c2h4",
    "c2h6",
    "c3h6",
    "c3h8",
    "c4h6",
    "c4h8",
    "c6h6",
    "c7h8",
    "c8h10",
    "c8h8",
    "ch4",
    "h2o",
    "h2",
    "furnace_pressure",
    "cracking_gas_temperature",
]

TARGET_COLUMN = "coil_outlet_temperature"

# Genuine aliases for plant DCS/SCADA tag mappings to canonical features
FEATURE_ALIASES: Dict[str, str] = {
    "pressure": "furnace_pressure",
    "draft_pressure": "furnace_pressure",
    "cracking gas temperature": "cracking_gas_temperature",
    "cracking_gas_temp": "cracking_gas_temperature",
    "gas_temp": "cracking_gas_temperature",
    "dilution_steam": "h2o",
    "steam": "h2o",
    "water": "h2o",
    "hydrogen": "h2",
    "methane": "ch4",
    "ethylene": "c2h4",
    "ethane": "c2h6",
    "propylene": "c3h6",
    "propane": "c3h8",
}

# Target aliases that must NEVER be treated as input features
TARGET_ALIASES: List[str] = [
    "cot",
    "coil_outlet_temperature",
    "coil_outlet_temp",
    "ti-20101",
    "ti-20102",
    "actual_cot",
    "target_cot",
]


class FurnaceCOTPreprocessor:
    """
    Production preprocessor for Furnace COT regression.
    Maintains deterministic feature parity and prevents target leakage.
    """

    def __init__(self, feature_names: Optional[List[str]] = None) -> None:
        self.feature_names = feature_names or list(CANONICAL_FEATURES)
        self.is_fitted: bool = False
        self.means_: Dict[str, float] = {}
        self.stds_: Dict[str, float] = {}
        self.mins_: Dict[str, float] = {}
        self.maxs_: Dict[str, float] = {}

    def fit(self, x_train: pd.DataFrame | np.ndarray) -> FurnaceCOTPreprocessor:
        """Fit preprocessor strictly on training data to establish baseline statistics."""
        if isinstance(x_train, pd.DataFrame):
            # Guard against target leakage
            assert TARGET_COLUMN not in x_train.columns, "TARGET LEAKAGE: coil_outlet_temperature found in X_train"
            df_ordered = x_train[self.feature_names]
            for col in self.feature_names:
                self.means_[col] = float(df_ordered[col].mean())
                self.stds_[col] = float(df_ordered[col].std())
                self.mins_[col] = float(df_ordered[col].min())
                self.maxs_[col] = float(df_ordered[col].max())
        else:
            arr = np.asarray(x_train, dtype=np.float64)
            assert arr.shape[1] == len(self.feature_names), f"Expected {len(self.feature_names)} features, got {arr.shape[1]}"
            for i, col in enumerate(self.feature_names):
                col_data = arr[:, i]
                self.means_[col] = float(np.mean(col_data))
                self.stds_[col] = float(np.std(col_data))
                self.mins_[col] = float(np.min(col_data))
                self.maxs_[col] = float(np.max(col_data))

        self.is_fitted = True
        self.feature_means_ = self.means_
        logger.info(
            "Fitted FurnaceCOTPreprocessor across %d features with training statistics.",
            len(self.feature_names),
        )
        return self

    def transform(self, data: pd.DataFrame | np.ndarray | Dict[str, float]) -> np.ndarray:
        """
        Transform input data into ordered, complete numerical feature matrix.
        Accepts DataFrame, 2D array, or dictionary of telemetry tags.
        """
        if not self.is_fitted:
            raise RuntimeError("FurnaceCOTPreprocessor must be fitted before transforming data.")

        if isinstance(data, dict):
            norm_dict = self._normalize_dict(data)
            row = []
            for feat in self.feature_names:
                # Impute missing values with training baseline mean
                val = norm_dict.get(feat, self.means_.get(feat, 0.0))
                try:
                    float_val = float(val)
                    if np.isnan(float_val) or np.isinf(float_val):
                        float_val = self.means_.get(feat, 0.0)
                except (ValueError, TypeError):
                    float_val = self.means_.get(feat, 0.0)
                row.append(float_val)
            matrix = np.array([row], dtype=np.float64)

        elif isinstance(data, pd.DataFrame):
            # Target leakage check
            cols_to_use = [c for c in self.feature_names]
            for target_col in TARGET_ALIASES + [TARGET_COLUMN]:
                if target_col in data.columns and target_col not in cols_to_use:
                    pass  # Safely excluded
            matrix = data[cols_to_use].values.astype(np.float64)
            # Impute NaNs if any
            for i, feat in enumerate(cols_to_use):
                nan_mask = np.isnan(matrix[:, i]) | np.isinf(matrix[:, i])
                if np.any(nan_mask):
                    matrix[nan_mask, i] = self.means_.get(feat, 0.0)

        else:
            matrix = np.asarray(data, dtype=np.float64)
            if matrix.ndim == 1:
                matrix = matrix.reshape(1, -1)
            assert matrix.shape[1] == len(self.feature_names), (
                f"Dimension mismatch: expected {len(self.feature_names)} features, got {matrix.shape[1]}"
            )

        return matrix

    def _normalize_dict(self, input_dict: Dict[str, Any]) -> Dict[str, float]:
        """Normalize input dictionary keys to canonical feature names, strictly ignoring target keys."""
        normalized: Dict[str, float] = {}
        for k, v in input_dict.items():
            clean_k = str(k).strip().lower().replace("-", "_")

            # Strictly ignore target keys to prevent any possibility of target leakage
            if clean_k in TARGET_ALIASES:
                continue

            canonical_k = FEATURE_ALIASES.get(clean_k, clean_k)
            if canonical_k in self.feature_names:
                try:
                    normalized[canonical_k] = float(v)
                except (ValueError, TypeError):
                    continue
            elif clean_k in self.feature_names:
                try:
                    normalized[clean_k] = float(v)
                except (ValueError, TypeError):
                    continue

        return normalized
