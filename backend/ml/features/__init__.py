"""
backend/ml/features — Industrial Feature Engineering & Time-Series Extraction Infrastructure.

Provides standardized feature extraction abstractions:
- FeatureWindow: Temporal sliding window of multi-variate process sensor telemetry.
- FeatureExtractor: Stateless & stateful transformer calculating raw values, deltas,
  rates of change, rolling statistical metrics (mean, std, min, max), baseline deviations,
  and operating-mode categorical encodings.
"""
from __future__ import annotations

from backend.ml.features.extractor import FeatureExtractor, FeatureWindow

__all__ = ["FeatureWindow", "FeatureExtractor"]
