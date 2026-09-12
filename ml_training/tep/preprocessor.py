"""
ml_training/tep/preprocessor.py — Standardized TEP Preprocessor & Scaler.

Fits StandardScaler strictly on normal steady-state training data (d00 80% split).
Ensures zero feature-order mismatch between offline training and online production inference.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ml_training.tep.dataset import CANONICAL_FEATURES

logger = logging.getLogger("tep.preprocessor")


class TEPPreprocessor:
    """
    Standardizes raw 52-variable TEP observations.
    Fitted exclusively on normal steady-state training data.
    """

    def __init__(self, feature_names: Optional[List[str]] = None) -> None:
        self.feature_names = feature_names or list(CANONICAL_FEATURES)
        self.scaler: StandardScaler = StandardScaler()
        self.is_fitted: bool = False
        self.means_: Dict[str, float] = {}
        self.scales_: Dict[str, float] = {}

    def fit(self, x_train: pd.DataFrame | np.ndarray) -> TEPPreprocessor:
        """Fit StandardScaler on normal training data."""
        if isinstance(x_train, pd.DataFrame):
            # Ensure correct column ordering
            x_ordered = x_train[self.feature_names].values
        else:
            x_ordered = x_train

        self.scaler.fit(x_ordered)
        self.is_fitted = True

        for idx, feat in enumerate(self.feature_names):
            self.means_[feat] = float(self.scaler.mean_[idx])
            # Prevent divide-by-zero on invariant channels
            self.scales_[feat] = float(self.scaler.scale_[idx]) if self.scaler.scale_[idx] > 1e-9 else 1.0

        logger.info(
            "Fitted TEPPreprocessor across %d features on %d samples",
            len(self.feature_names),
            len(x_ordered),
        )
        return self

    def transform(self, data: pd.DataFrame | np.ndarray | Dict[str, float]) -> np.ndarray:
        """
        Transform raw data into standardized feature matrix.
        Accepts DataFrame, numpy array, or dictionary of feature readings.
        """
        if not self.is_fitted:
            raise RuntimeError("TEPPreprocessor must be fitted before transforming data.")

        if isinstance(data, dict):
            # Normalize dictionary keys (handle case-insensitivity and formatting)
            norm_dict = self._normalize_dict_keys(data)
            row = []
            for feat in self.feature_names:
                val = norm_dict.get(feat, self.means_.get(feat, 0.0))
                row.append(float(val))
            matrix = np.array([row], dtype=np.float64)
        elif isinstance(data, pd.DataFrame):
            # Reorder columns to match canonical feature list
            matrix = data[self.feature_names].values.astype(np.float64)
        else:
            matrix = np.asarray(data, dtype=np.float64)
            if matrix.ndim == 1:
                matrix = matrix.reshape(1, -1)

        return self.scaler.transform(matrix)

    def _normalize_dict_keys(self, input_dict: Dict[str, Any]) -> Dict[str, float]:
        """Normalize various telemetry key formats to canonical xmeas_i and xmv_j."""
        normalized: Dict[str, float] = {}
        for k, v in input_dict.items():
            clean_k = str(k).strip().lower()
            # Replace parentheses: xmeas(1) -> xmeas_1
            clean_k = clean_k.replace("(", "_").replace(")", "").replace("-", "_")
            try:
                normalized[clean_k] = float(v)
            except (ValueError, TypeError):
                continue
        return normalized


class TEPFaultPreprocessor:
    """
    Standardizes 156-feature TEP observations (52 variables x 3 families: raw, mean, delta).
    Fitted strictly on training data (75% within-run split of d00.dat..d21.dat).
    """

    def __init__(self, feature_names: Optional[List[str]] = None, window_size: int = 3) -> None:
        from ml_training.tep.dataset import CANONICAL_FAULT_FEATURES, CANONICAL_FEATURES
        self.feature_names = feature_names or list(CANONICAL_FAULT_FEATURES)
        self.raw_var_names = list(CANONICAL_FEATURES)
        self.window_size = window_size
        self.scaler: StandardScaler = StandardScaler()
        self.is_fitted: bool = False
        self.means_: Dict[str, float] = {}
        self.scales_: Dict[str, float] = {}

    def fit(self, x_train: pd.DataFrame | np.ndarray) -> TEPFaultPreprocessor:
        """Fit StandardScaler on 156-feature training data."""
        if isinstance(x_train, pd.DataFrame):
            x_ordered = x_train[self.feature_names].values
        else:
            x_ordered = x_train

        self.scaler.fit(x_ordered)
        self.is_fitted = True

        for idx, feat in enumerate(self.feature_names):
            self.means_[feat] = float(self.scaler.mean_[idx])
            self.scales_[feat] = float(self.scaler.scale_[idx]) if self.scaler.scale_[idx] > 1e-9 else 1.0

        logger.info(
            "Fitted TEPFaultPreprocessor across %d features on %d samples",
            len(self.feature_names),
            len(x_ordered),
        )
        return self

    def transform(
        self,
        data: pd.DataFrame | np.ndarray | Dict[str, float],
        history_buffer: Optional[List[Dict[str, float]]] = None,
    ) -> np.ndarray:
        """
        Transform raw observations or feature matrices into standardized 156-feature space.
        - If DataFrame or 2D array: assumes 156-feature matrix matching feature_names.
        - If Dict:
            - If keys match 156 features (contains _raw, _mean, _delta): maps directly.
            - If keys match 52 process variables: uses history_buffer (if provided) to construct
              [raw, mean, delta] features according to W=3 definition.
        """
        if not self.is_fitted:
            raise RuntimeError("TEPFaultPreprocessor must be fitted before transforming data.")

        if isinstance(data, dict):
            norm_dict = self._normalize_dict_keys(data)
            # Check if dict already contains 156 engineered features
            has_window_keys = any(k.endswith("_raw") or k.endswith("_mean") for k in norm_dict.keys())
            if has_window_keys:
                row = [norm_dict.get(f, self.means_.get(f, 0.0)) for f in self.feature_names]
                matrix = np.array([row], dtype=np.float64)
            else:
                # Raw 52 process variables: construct 156 features using history_buffer
                # Current raw values
                current_raw = [norm_dict.get(v, self.means_.get(f"{v}_raw", 0.0)) for v in self.raw_var_names]

                # If history buffer provided, extract up to window_size samples
                if history_buffer and len(history_buffer) > 0:
                    past_samples = [self._extract_raw_vector(b) for b in history_buffer[-self.window_size + 1:]]
                    all_window = np.array(past_samples + [current_raw], dtype=np.float64)  # (K, 52)
                    raw_vec = all_window[-1]
                    mean_vec = np.mean(all_window, axis=0)
                    delta_vec = all_window[-1] - all_window[0]
                else:
                    # Incomplete single-sample window fallback
                    raw_vec = np.array(current_raw, dtype=np.float64)
                    mean_vec = raw_vec.copy()
                    delta_vec = np.zeros_like(raw_vec)

                full_156 = np.concatenate([raw_vec, mean_vec, delta_vec])
                matrix = np.array([full_156], dtype=np.float64)

        elif isinstance(data, pd.DataFrame):
            matrix = data[self.feature_names].values.astype(np.float64)
        else:
            matrix = np.asarray(data, dtype=np.float64)
            if matrix.ndim == 1:
                matrix = matrix.reshape(1, -1)

        return self.scaler.transform(matrix)

    def _extract_raw_vector(self, d: Dict[str, Any]) -> List[float]:
        norm = self._normalize_dict_keys(d)
        return [norm.get(v, self.means_.get(f"{v}_raw", 0.0)) for v in self.raw_var_names]

    def _normalize_dict_keys(self, input_dict: Dict[str, Any]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        for k, v in input_dict.items():
            clean_k = str(k).strip().lower()
            clean_k = clean_k.replace("(", "_").replace(")", "").replace("-", "_")
            try:
                normalized[clean_k] = float(v)
            except (ValueError, TypeError):
                continue
        return normalized

