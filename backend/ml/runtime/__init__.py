"""
backend/ml/runtime — ML Runtime Integration Layer.

This package provides:
  - Canonical MLEvidence contract (contracts.py)
  - MLRuntime orchestrator that wraps the four ML models (runtime.py)
  - Mock implementations for parallel development (mocks.py)

Architecture:
  Real Models (Arushi)   OR   Mock Models (dev/test)
           ↓                           ↓
      MLRuntime.run()  ──────────────────
           ↓
      MLEvidence (canonical, typed)
           ↓
  Context / Risk / Episode / Agents  (model-agnostic)

When Arushi delivers trained artifacts, replace the mock adapter with the
real model adapter in MLRuntime configuration — no changes to intelligence
services required.
"""
from __future__ import annotations

from backend.ml.runtime.contracts import (
    MLEvidence,
    MLEvidenceStatus,
    MLEvidenceQuality,
    MLPredictionType,
    AnomalyPayload,
    FaultPayload,
    COTPredictionPayload,
    TubeTemperaturePayload,
)
from backend.ml.runtime.runtime import MLRuntime, ml_runtime
from backend.ml.runtime.mocks import (
    MockAnomalyModel,
    MockFaultModel,
    MockCOTModel,
    MockTubeTemperatureModel,
    build_mock_ml_runtime,
)

__all__ = [
    # Contracts
    "MLEvidence",
    "MLEvidenceStatus",
    "MLEvidenceQuality",
    "MLPredictionType",
    "AnomalyPayload",
    "FaultPayload",
    "COTPredictionPayload",
    "TubeTemperaturePayload",
    # Runtime
    "MLRuntime",
    "ml_runtime",
    # Mocks
    "MockAnomalyModel",
    "MockFaultModel",
    "MockCOTModel",
    "MockTubeTemperatureModel",
    "build_mock_ml_runtime",
]
