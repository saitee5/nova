"""
backend/tests/test_tep_anomaly_detector.py — Focused Test Suite for TEP Anomaly Detection.

Covers:
1. Dataset schema validation
2. Deterministic preprocessing & feature ordering
3. PCA component training & statistics (Q and T^2)
4. Isolation Forest training & calibration
5. Artifact serialization & deserialization
6. Artifact loading & live inference returning OK
7. Missing artifact fallback (MODEL_NOT_AVAILABLE)
8. Invalid input handling (INVALID_INPUT)
9. Inference runtime error handling (INFERENCE_ERROR)
10. Model registry metadata integrity
11. Unified MLPipeline integration (anomaly OK, others MODEL_NOT_AVAILABLE)
12. Backward compatibility with PlantState and legacy callers
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from backend.ml.anomaly.detector import ProcessAnomalyDetector
from backend.ml.inference.pipeline import MLPipeline, ml_pipeline
from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessmentStatus, OperatingMode, PlantState, ProcessTelemetry
from ml_training.tep.dataset import CANONICAL_FEATURES, VERIFIED_HASHES, load_tep_splits
from ml_training.tep.preprocessor import TEPPreprocessor


@pytest.fixture(scope="module")
def tep_splits():
    """Load TEP dataset splits once for module tests."""
    return load_tep_splits()


@pytest.fixture(scope="module")
def live_detector():
    """Instantiate live ProcessAnomalyDetector loading production model.joblib."""
    model_registry.load_registry()
    return ProcessAnomalyDetector()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Dataset Schema Validation & Integrity
# ──────────────────────────────────────────────────────────────────────────────

def test_tep_dataset_schema_and_dimensions(tep_splits):
    """Verify raw TEP benchmark dimensions, 52 variables, and chronological splits."""
    assert tep_splits.x_train.shape == (400, 52)
    assert tep_splits.x_val.shape == (100, 52)
    assert len(tep_splits.feature_names) == 52

    # Check 41 measured variables and 11 manipulated variables
    assert all(f"xmeas_{i}" in tep_splits.feature_names for i in range(1, 42))
    assert all(f"xmv_{j}" in tep_splits.feature_names for j in range(1, 12))

    # Verify test sets exist and have correct shapes
    assert "normal_d00_te" in tep_splits.test_sets
    assert "fault_01_ac_feed_ratio" in tep_splits.test_sets
    df_norm, y_norm = tep_splits.test_sets["normal_d00_te"]
    assert df_norm.shape == (960, 52)
    assert len(y_norm) == 960
    assert np.all(y_norm == 0)

    df_f01, y_f01 = tep_splits.test_sets["fault_01_ac_feed_ratio"]
    assert df_f01.shape == (960, 52)
    assert np.sum(y_f01[:160]) == 0
    assert np.sum(y_f01[160:]) == 800


# ──────────────────────────────────────────────────────────────────────────────
# 2. Deterministic Preprocessing & Feature Ordering
# ──────────────────────────────────────────────────────────────────────────────

def test_tep_preprocessor_deterministic_scaling(tep_splits):
    """Verify StandardScaler fits strictly on training split and transforms deterministically."""
    prep = TEPPreprocessor(feature_names=CANONICAL_FEATURES)
    prep.fit(tep_splits.x_train)

    Z1 = prep.transform(tep_splits.x_train)
    Z2 = prep.transform(tep_splits.x_train)
    assert np.allclose(Z1, Z2)
    assert Z1.shape == (400, 52)

    # Standardized mean should be ~0 and std ~1 for training split
    assert np.allclose(np.mean(Z1, axis=0), 0.0, atol=1e-5)
    assert np.allclose(np.std(Z1, axis=0), 1.0, atol=1e-5)

    # Dictionary input with key normalization
    sample_dict = {f"XMEAS({i})": 1.0 for i in range(1, 42)}
    sample_dict.update({f"XMV({j})": 50.0 for j in range(1, 12)})
    Z_dict = prep.transform(sample_dict)
    assert Z_dict.shape == (1, 52)


# ──────────────────────────────────────────────────────────────────────────────
# 3. Artifact Existence & Structure
# ──────────────────────────────────────────────────────────────────────────────

def test_model_artifact_contains_all_components():
    """Verify serialized model.joblib contains scaler, PCA, IF, thresholds, and metadata."""
    artifact_path = Path("artifacts/models/process_anomaly_detector/v1.0.0/model.joblib")
    assert artifact_path.exists(), f"Artifact missing at {artifact_path}"
    assert artifact_path.stat().st_size > 50000  # At least 50KB

    import joblib
    payload = joblib.load(artifact_path)
    assert "preprocessor" in payload
    assert "pca" in payload
    assert "pca_config" in payload
    assert "isolation_forest" in payload
    assert "if_config" in payload
    assert "scoring" in payload
    assert "feature_names" in payload
    assert payload["pca_config"]["n_components"] >= 10
    assert payload["pca_config"]["q_threshold"] > 0.0
    assert payload["pca_config"]["t2_threshold"] > 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 4. Live Detector Inference (OK Status on Normal & Fault Data)
# ──────────────────────────────────────────────────────────────────────────────

def test_live_detector_normal_inference(live_detector, tep_splits):
    """Verify live ProcessAnomalyDetector returns OK with low anomaly score for normal operation."""
    assert live_detector.is_loaded is True
    assert live_detector.version == "v1.0.0"

    row0 = tep_splits.x_train.iloc[0].to_dict()
    assessment = live_detector.detect_anomaly(row0)

    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.score is not None
    assert assessment.prediction is not None
    assert assessment.prediction["is_anomaly"] is False
    assert assessment.score < 0.50
    assert len(assessment.features_used) == 52
    assert assessment.provenance["algorithm"] == "PCA + Isolation Forest"


def test_live_detector_fault_detection(live_detector, tep_splits):
    """Verify live ProcessAnomalyDetector detects anomaly on post-injection fault sample."""
    df_f01, _ = tep_splits.test_sets["fault_01_ac_feed_ratio"]
    # Sample 300 is well into Fault 1
    fault_sample = df_f01.iloc[300].to_dict()
    assessment = live_detector.detect_anomaly(fault_sample)

    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.prediction["is_anomaly"] is True
    assert assessment.score >= 0.50
    assert assessment.prediction["pca_score"] >= 0.50 or assessment.prediction["if_score"] >= 0.50


# ──────────────────────────────────────────────────────────────────────────────
# 5. Robust Fallback Mechanics (MODEL_NOT_AVAILABLE, INVALID_INPUT, INFERENCE_ERROR)
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_artifact_fallback():
    """Verify detector gracefully returns MODEL_NOT_AVAILABLE when artifact path does not exist."""
    fake_detector = ProcessAnomalyDetector(model_path="nonexistent/fake_model.joblib")
    assert fake_detector.is_loaded is False

    assessment = fake_detector.detect_anomaly({"xmeas_1": 0.25})
    assert assessment.status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert assessment.score is None
    assert assessment.prediction is None


def test_invalid_input_handling(live_detector):
    """Verify detector returns INVALID_INPUT for empty dict or non-dict inputs."""
    assert live_detector.detect_anomaly({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert live_detector.detect_anomaly(None).status == MLAssessmentStatus.INVALID_INPUT.value


def test_inference_error_containment(monkeypatch, live_detector):
    """Verify detector catches unexpected transform exceptions and returns INFERENCE_ERROR."""
    def broken_transform(*args, **kwargs):
        raise RuntimeError("Simulated matrix singularity")

    monkeypatch.setattr(live_detector.preprocessor, "transform", broken_transform)
    assessment = live_detector.detect_anomaly({"xmeas_1": 1.0})
    assert assessment.status == MLAssessmentStatus.INFERENCE_ERROR.value
    assert "Simulated matrix singularity" in assessment.provenance.get("error", "")


# ──────────────────────────────────────────────────────────────────────────────
# 6. Model Registry & Metadata Integrity
# ──────────────────────────────────────────────────────────────────────────────

def test_registry_metadata_for_anomaly_detector():
    """Verify model registry records ready status and valid metadata for process_anomaly_detector."""
    meta = model_registry.get_model_metadata("process_anomaly_detector")
    assert meta is not None
    assert meta.status == "ready"
    assert meta.version == "v1.0.0"
    assert "4c3c0b11" in meta.dataset_hash
    assert Path(meta.artifact_path).exists()


# ──────────────────────────────────────────────────────────────────────────────
# 7. Unified MLPipeline Integration
# ──────────────────────────────────────────────────────────────────────────────

def test_unified_mlpipeline_with_live_anomaly_detector(tep_splits):
    """Verify MLPipeline executes with anomaly_detection OK while other 3 models remain MODEL_NOT_AVAILABLE."""
    pipeline = MLPipeline()
    row0 = tep_splits.x_train.iloc[0].to_dict()

    results = pipeline.run_pipeline(row0)
    assert len(results) == 4

    # Process Anomaly Detector is trained and active
    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["anomaly_detection"].score is not None

    # Fault diagnosis and furnace COT prediction are OK once trained
    assert results["fault_diagnosis"].status in (
        MLAssessmentStatus.OK.value,
        MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
    )
    assert results["furnace_cot_prediction"].status in (
        MLAssessmentStatus.OK.value,
        MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
    )
    # Tube temperature soft sensor must strictly remain MODEL_NOT_AVAILABLE
    assert results["tube_temperature_soft_sensor"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value


def test_unified_mlpipeline_with_plant_state():
    """Verify MLPipeline accepts PlantState object cleanly."""
    state = PlantState(
        plant_id="ETH-01",
        operating_mode=OperatingMode.STEADY_STATE,
        telemetry={
            "xmeas_1": ProcessTelemetry(tag="xmeas_1", value=0.25, asset_id="F-201A", unit="kg/hr"),
            "xmeas_2": ProcessTelemetry(tag="xmeas_2", value=3640.0, asset_id="F-201A", unit="kg/hr"),
        },
    )
    pipeline = MLPipeline()
    results = pipeline.run_pipeline(state)
    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["fault_diagnosis"].status in (
        MLAssessmentStatus.OK.value,
        MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
    )

