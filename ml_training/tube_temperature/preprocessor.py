"""
ml_training/tube_temperature/preprocessor.py — Tube Temperature Model Preprocessor.

Standardizes 17 process and gas temperature features (including COT) for Tube Metal Temperature (TMT) prediction.
- Guards against target leakage (TMT is never admitted into the feature matrix).
- Fits exclusively on training data.
- Handles dictionaries, DataFrames, and numpy matrices.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml_training.tube_temperature.dataset import CANONICAL_FEATURES, TARGET_COLUMN

logger = logging.getLogger("nova.ml.tube_temp.preprocessor")


class TubeTempPreprocessor:
    """Production preprocessor for Tube Temperature estimation."""

    def __init__(self, feature_names: Optional[List[str]] = None) -> None:
        self.feature_names = feature_names or list(CANONICAL_FEATURES)
        self.is_fitted: bool = False
        self.means_: Dict[str, float] = {}
        self.stds_: Dict[str, float] = {}
        self.mins_: Dict[str, float] = {}
        self.maxs_: Dict[str, float] = {}

    def fit(self, x_train: pd.DataFrame | np.ndarray) -> TubeTempPreprocessor:
        """Fit baseline statistics strictly on training data."""
        if isinstance(x_train, pd.DataFrame):
            assert TARGET_COLUMN not in x_train.columns, "TARGET LEAKAGE: TMT found in training features"
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
        logger.info("Fitted TubeTempPreprocessor on %d features", len(self.feature_names))
        return self

    def transform(self, data: pd.DataFrame | np.ndarray | Dict[str, float]) -> np.ndarray:
        """Transform input data into ordered numerical feature matrix."""
        if not self.is_fitted:
            raise RuntimeError("TubeTempPreprocessor must be fitted before transforming data.")

        if isinstance(data, dict):
            row = []
            for feat in self.feature_names:
                # Check for direct key, lowercase key, or alias
                val = data.get(feat, data.get(feat.lower(), self.means_.get(feat, 0.0)))
                try:
                    float_val = float(val)
                    if np.isnan(float_val) or np.isinf(float_val):
                        float_val = self.means_.get(feat, 0.0)
                except (ValueError, TypeError):
                    float_val = self.means_.get(feat, 0.0)
                row.append(float_val)
            matrix = np.array([row], dtype=np.float64)

        elif isinstance(data, pd.DataFrame):
            cols_to_use = [c for c in self.feature_names]
            matrix = data[cols_to_use].values.astype(np.float64)
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
