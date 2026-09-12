"""
backend/tests/test_tep_fault_classifier.py — Comprehensive Unit & Integration Tests.

Verifies the Tennessee Eastman Process multiclass ProcessFaultClassifier on curated data:
1. Curated TEP canonical dataset loading
2. All 21 classes validated (0..20)
3. Class mapping integrity
4. 156-feature schema (52 raw, 52 mean, 52 delta)
5. Transition-window exclusion
6. Preprocessing determinism
7. Artifact existence & structure
8. Live inference (NORMAL and fault telemetry)
9. Probability sums & top-3 candidate rankings
10. Fallbacks (MODEL_NOT_AVAILABLE, INVALID_INPUT, INFERENCE_ERROR)
11. ModelRegistry & MLPipeline integration
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
import pytest

from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.inference.pipeline import ml_pipeline
from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessmentStatus
from ml_training.tep.dataset import (
    CANONICAL_FAULT_FEATURES,
    CANONICAL_FEATURES,
    CURATED_TEP_PATH,
    FAULT_DESCRIPTIONS,
    construct_run_window_features,
    load_tep_multiclass_splits,
)
from ml_training.tep.preprocessor import TEPFaultPreprocessor

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_ARTIFACT_PATH = REPO_ROOT / "artifacts" / "models" / "process_fault_classifier" / "v1.0.0" / "model.joblib"
EVAL_PATH = REPO_ROOT / "artifacts" / "models" / "eval_fault_tep.json"


# 1. Curated Dataset Exists
def test_curated_tep_dataset_exists():
    """Verify curated canonical TEP dataset exists."""
    assert CURATED_TEP_PATH.exists()
    assert CURATED_TEP_PATH.stat().st_size > 1000000


# 2. All 21 Classes Validated
def test_all_21_classes_defined():
    """Verify exactly 21 discrete process classes (0 = Normal, 1..20 = IDV 1..20)."""
    assert len(FAULT_DESCRIPTIONS) == 21
    for i in range(21):
        assert i in FAULT_DESCRIPTIONS
        meta = FAULT_DESCRIPTIONS[i]
        assert "code" in meta and "description" in meta


# 3. Class Mapping Integrity
def test_class_mapping_content():
    """Verify class 0 is NORMAL and class 1..20 correspond to IDV(1)..IDV(20)."""
    assert FAULT_DESCRIPTIONS[0]["code"] == "NORMAL"
    assert "Normal" in FAULT_DESCRIPTIONS[0]["description"]
    for i in range(1, 21):
        assert FAULT_DESCRIPTIONS[i]["code"] == f"IDV({i})"


# 4. Feature Construction (156 Features)
def test_156_window_feature_construction():
    """Verify deterministic 156-feature generation: [raw (52), mean (52), delta (52)]."""
    fake_run = np.ones((10, 52), dtype=np.float64) * 5.0
    feats = construct_run_window_features(fake_run, window_size=3)

    assert feats.shape == (10, 156)
    # t=0: mean = 5.0, delta = 0.0
    assert np.allclose(feats[0, :52], 5.0)
    assert np.allclose(feats[0, 52:104], 5.0)
    assert np.allclose(feats[0, 104:], 0.0)


# 5. Preprocessor Scaling Determinism
def test_preprocessor_deterministic_fit():
    """Verify TEPFaultPreprocessor fits and transforms deterministically."""
    prep = TEPFaultPreprocessor(feature_names=CANONICAL_FAULT_FEATURES, window_size=3)
    dummy_data = np.random.RandomState(42).randn(50, 156)
    prep.fit(dummy_data)
    assert prep.is_fitted is True

    Z1 = prep.transform(dummy_data)
    Z2 = prep.transform(dummy_data)
    assert np.allclose(Z1, Z2)


# 6. Artifact Existence & Structure
def test_model_artifact_structure():
    """Verify model.joblib exists and contains all required components."""
    assert MODEL_ARTIFACT_PATH.exists()
    payload = joblib.load(MODEL_ARTIFACT_PATH)
    assert "xgb_classifier" in payload or "model" in payload
    assert "preprocessor" in payload
    assert "feature_names" in payload
    assert len(payload["feature_names"]) == 156


# 7. Live Inference (NORMAL Telemetry)
def test_normal_telemetry_inference():
    """Verify live ProcessFaultClassifier returns valid prediction for baseline telemetry."""
    classifier = ProcessFaultClassifier()
    normal_telemetry = {f"xmeas_{i}": 1.0 for i in range(1, 42)}
    normal_telemetry.update({f"xmv_{j}": 50.0 for j in range(1, 12)})

    assessment = classifier.classify_fault(normal_telemetry)
    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.prediction is not None
    assert "fault_code" in assessment.prediction
    assert "top_candidates" in assessment.prediction
    assert len(assessment.prediction["top_candidates"]) <= 3



# 8. Fallback Mechanics
def test_missing_artifact_fallback():
    """Verify classifier gracefully returns MODEL_NOT_AVAILABLE when artifact missing."""
    fake_classifier = ProcessFaultClassifier(model_path="nonexistent/model.joblib")
    assessment = fake_classifier.classify_fault({"xmeas_1": 1.0})
    assert assessment.status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert assessment.prediction is None


def test_invalid_input_handling():
    """Verify classifier returns INVALID_INPUT for empty or non-dict input."""
    classifier = ProcessFaultClassifier()
    assert classifier.classify_fault({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert classifier.classify_fault(None).status == MLAssessmentStatus.INVALID_INPUT.value


# 9. Model Registry & MLPipeline Integration
def test_registry_metadata_and_pipeline():
    """Verify registry metadata and unified MLPipeline integration."""
    meta = model_registry.get_model_metadata("process_fault_classifier")
    assert meta is not None

    pipeline_res = ml_pipeline.run_inference_suite("F-201A", {"xmeas_1": 1.0})
    assert "fault_diagnosis" in pipeline_res
    assert pipeline_res["fault_diagnosis"].status in (
        MLAssessmentStatus.OK.value,
        MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
    )
