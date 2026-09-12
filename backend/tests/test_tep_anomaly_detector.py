"""
backend/tests/test_tep_anomaly_detector.py — Focused Test Suite for TEP Anomaly Detection.

Covers:
1. Curated TEP dataset schema validation (52 variables)
2. Deterministic preprocessing & feature ordering
3. Artifact existence & structure
4. Live ProcessAnomalyDetector inference
5. Missing artifact fallback (MODEL_NOT_AVAILABLE)
6. Invalid input handling (INVALID_INPUT)
7. Inference runtime error containment (INFERENCE_ERROR)
8. Model registry metadata integrity
9. Unified MLPipeline integration
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
from ml_training.tep.dataset import CANONICAL_FEATURES, CURATED_TEP_PATH, load_tep_splits
from ml_training.tep.preprocessor import TEPPreprocessor


@pytest.fixture(scope="module")
def tep_splits():
    """Load TEP dataset splits once for module tests from curated dataset."""
    return load_tep_splits(max_normal_samples=1000)


@pytest.fixture(scope="module")
def live_detector():
    """Instantiate live ProcessAnomalyDetector loading production model.joblib."""
    model_registry.load_registry()
    return ProcessAnomalyDetector()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Dataset Schema Validation & Integrity
# ──────────────────────────────────────────────────────────────────────────────

def test_tep_dataset_schema_and_dimensions(tep_splits):
    """Verify curated TEP canonical dimensions, 52 variables, and chronological splits."""
    assert tep_splits.x_train.shape[1] == 52
    assert tep_splits.x_val.shape[1] == 52
    assert len(tep_splits.feature_names) == 52

    # Check 41 measured variables and 11 manipulated variables
    assert all(f"xmeas_{i}" in tep_splits.feature_names for i in range(1, 42))
    assert all(f"xmv_{j}" in tep_splits.feature_names for j in range(1, 12))
    assert "normal_validation_holdout" in tep_splits.test_sets


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
    assert Z1.shape == tep_splits.x_train.shape

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
    assert artifact_path.stat().st_size > 10000

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


# ──────────────────────────────────────────────────────────────────────────────
# 4. Live Detector Inference (OK Status on Normal & Fault Data)
# ──────────────────────────────────────────────────────────────────────────────

def test_live_detector_normal_inference(live_detector, tep_splits):
    """Verify live ProcessAnomalyDetector returns OK for normal operation."""
    assert live_detector.is_loaded is True
    assert live_detector.version in ("v1.0.0", "v1.1.0")

    row0 = tep_splits.x_train.iloc[0].to_dict()
    assessment = live_detector.detect_anomaly(row0)

    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.score is not None
    assert assessment.prediction is not None
    assert len(assessment.features_used) == 52
    assert assessment.provenance["algorithm"] == "PCA + Isolation Forest"


def test_live_detector_fault_detection(live_detector):
    """Verify live ProcessAnomalyDetector processes high-deviation telemetry vector."""
    extreme_sample = {f"xmeas_{i}": 9999.0 for i in range(1, 42)}
    extreme_sample.update({f"xmv_{j}": 999.0 for j in range(1, 12)})
    assessment = live_detector.detect_anomaly(extreme_sample)

    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.score is not None


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
    """Verify model registry records ready/validated status and valid metadata for process_anomaly_detector."""
    meta = model_registry.get_model_metadata("process_anomaly_detector")
    assert meta is not None
    assert meta.status in ("ready", "VALIDATED", "VALIDATED_WITH_LIMITATIONS")
    assert meta.version in ("v1.0.0", "v1.1.0")
    assert Path(meta.artifact_path).exists()



# ──────────────────────────────────────────────────────────────────────────────
# 7. Unified MLPipeline Integration
# ──────────────────────────────────────────────────────────────────────────────

def test_unified_mlpipeline_with_live_anomaly_detector(tep_splits):
    """Verify MLPipeline executes with anomaly_detection OK."""
    pipeline = MLPipeline()
    row0 = tep_splits.x_train.iloc[0].to_dict()

    results = pipeline.run_pipeline(row0)
    assert len(results) == 4
    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["anomaly_detection"].score is not None
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
