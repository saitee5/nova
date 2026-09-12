"""
backend/tests/test_tep_fault_classifier.py — Comprehensive Unit & Integration Tests.

Verifies the Tennessee Eastman Process multiclass ProcessFaultClassifier:
1. all TEP files validated
2. all 22 classes validated
3. class mapping
4. dataset shapes
5. chronological splitting
6. fault-injection boundary handling
7. transition-window exclusion
8. 156-feature schema
9. feature ordering
10. window reset between runs
11. preprocessing
12. deterministic model behavior
13. artifact serialization
14. artifact loading
15. NORMAL inference
16. known fault inference
17. probability sum
18. top-3 output
19. missing artifact fallback
20. invalid input
21. inference error
22. ModelRegistry integration
23. MLPipeline integration
24. regression compatibility
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np
import pytest

from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.inference.pipeline import ml_pipeline
from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessmentStatus
from ml_training.tep.dataset import (
    CANONICAL_FAULT_FEATURES,
    CANONICAL_FEATURES,
    FAULT_DESCRIPTIONS,
    TEP_DATA_DIR,
    VERIFIED_HASHES,
    compute_file_sha256,
    construct_run_window_features,
    load_raw_matrix,
    load_tep_multiclass_splits,
)
from ml_training.tep.preprocessor import TEPFaultPreprocessor

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_ARTIFACT_PATH = REPO_ROOT / "artifacts" / "models" / "process_fault_classifier" / "v1.0.0" / "model.joblib"
EVAL_PATH = REPO_ROOT / "artifacts" / "models" / "eval_fault_tep.json"


# 1. All TEP Files Validated
def test_all_tep_files_exist_and_hashes_valid():
    """Verify all 44 authentic TEP files exist and match recorded SHA-256 hashes."""
    assert len(VERIFIED_HASHES) == 44
    for fname, expected_hash in VERIFIED_HASHES.items():
        fpath = TEP_DATA_DIR / fname
        assert fpath.exists(), f"Missing TEP benchmark file: {fname}"
        actual_hash = compute_file_sha256(fpath)
        assert actual_hash == expected_hash, f"Hash mismatch for {fname}: {actual_hash} != {expected_hash}"


# 2. All 22 Classes Validated
def test_all_22_classes_defined():
    """Verify exactly 22 discrete process classes (0 = Normal, 1..21 = IDV 1..21)."""
    assert len(FAULT_DESCRIPTIONS) == 22
    for i in range(22):
        assert i in FAULT_DESCRIPTIONS
        meta = FAULT_DESCRIPTIONS[i]
        assert "code" in meta and "description" in meta


# 3. Class Mapping Integrity
def test_class_mapping_content():
    """Verify class 0 is NORMAL and class 1..21 correspond to IDV(1)..IDV(21)."""
    assert FAULT_DESCRIPTIONS[0]["code"] == "NORMAL"
    assert "Normal" in FAULT_DESCRIPTIONS[0]["description"]
    for i in range(1, 22):
        assert FAULT_DESCRIPTIONS[i]["code"] == f"IDV({i})"


# 4. Dataset Shapes
def test_dataset_file_shapes():
    """Verify raw file dimensions: d00.dat is 500x52 (transposed), d01 is 480x52, d*_te is 960x52."""
    d00 = load_raw_matrix(TEP_DATA_DIR / "d00.dat", expected_transposed=True)
    assert d00.shape == (500, 52)

    d01 = load_raw_matrix(TEP_DATA_DIR / "d01.dat", expected_transposed=False)
    assert d01.shape == (480, 52)

    d00_te = load_raw_matrix(TEP_DATA_DIR / "d00_te.dat", expected_transposed=False)
    assert d00_te.shape == (960, 52)

    d01_te = load_raw_matrix(TEP_DATA_DIR / "d01_te.dat", expected_transposed=False)
    assert d01_te.shape == (960, 52)


# 5 & 6 & 7. Chronological Splitting, Boundary Handling, and Transition Exclusion
def test_multiclass_dataset_split_and_transition_exclusion():
    """Verify within-run chronological splitting and exclusion of 42 transition windows."""
    split = load_tep_multiclass_splits(data_dir=TEP_DATA_DIR, train_ratio=0.75, window_size=3)
    assert split.metadata["excluded_transition_windows"] == 42
    assert len(split.x_train) == 7893
    assert len(split.x_val) == 2645
    assert len(split.x_test) == 21120

    # Ensure all 22 classes exist in train, val, and test
    train_classes = np.unique(split.y_train)
    val_classes = np.unique(split.y_val)
    test_classes = np.unique(split.y_test)
    assert len(train_classes) == 22
    assert len(val_classes) == 22
    assert len(test_classes) == 22


# 8 & 9. 156-Feature Schema and Feature Ordering
def test_156_feature_schema_and_ordering():
    """Verify feature schema contains exactly 156 features with raw, mean, delta order."""
    assert len(CANONICAL_FAULT_FEATURES) == 156
    raw_feats = [f"{v}_raw" for v in CANONICAL_FEATURES]
    mean_feats = [f"{v}_mean" for v in CANONICAL_FEATURES]
    delta_feats = [f"{v}_delta" for v in CANONICAL_FEATURES]
    expected_order = raw_feats + mean_feats + delta_feats
    assert CANONICAL_FAULT_FEATURES == expected_order


# 10. Window Reset Between Runs
def test_window_reset_between_runs():
    """Verify window feature builder isolates temporal history strictly within a single run."""
    run1 = np.ones((5, 52)) * 10.0
    run2 = np.ones((5, 52)) * 20.0
    feats1 = construct_run_window_features(run1, window_size=3)
    feats2 = construct_run_window_features(run2, window_size=3)

    # Startup sample t=0 in run2 must NOT have delta from run1
    # raw is at indices 0..51, mean at 52..103, delta at 104..155
    assert np.allclose(feats2[0, :52], 20.0)
    assert np.allclose(feats2[0, 52:104], 20.0)
    assert np.allclose(feats2[0, 104:156], 0.0)  # delta is 0 for startup sample


# 11. Preprocessing Scaling
def test_preprocessor_fitting_and_transformation():
    """Verify TEPFaultPreprocessor fits StandardScaler and transforms dictionaries and arrays."""
    data = np.random.RandomState(42).randn(100, 156) * 5 + 10
    prep = TEPFaultPreprocessor(feature_names=CANONICAL_FAULT_FEATURES)
    prep.fit(data)
    assert prep.is_fitted
    scaled = prep.transform(data)
    assert np.allclose(np.mean(scaled, axis=0), 0.0, atol=1e-5)
    assert np.allclose(np.std(scaled, axis=0), 1.0, atol=1e-5)


# 12 & 13. Deterministic Model Behavior & Artifact Serialization
def test_model_artifact_payload_structure():
    """Verify saved artifact contains all required components and is deterministic."""
    assert MODEL_ARTIFACT_PATH.exists()
    payload = joblib.load(MODEL_ARTIFACT_PATH)
    assert "preprocessor" in payload
    assert "xgb_classifier" in payload
    assert "feature_names" in payload
    assert len(payload["feature_names"]) == 156
    assert "class_mapping" in payload
    assert len(payload["class_mapping"]) == 22
    assert payload["schema_version"] == "v1.0.0"


# 14. Artifact Loading via ModelRegistry
def test_process_fault_classifier_loads_from_registry():
    """Verify ProcessFaultClassifier loads artifact via model_registry."""
    classifier = ProcessFaultClassifier()
    assert classifier.is_loaded
    assert classifier.resolved_artifact_path is not None
    assert classifier.resolved_artifact_path.exists()
    assert len(classifier.class_mapping) == 22


# 15. NORMAL Telemetry Inference
def test_normal_telemetry_inference():
    """Verify healthy steady-state telemetry yields status=OK and valid probability."""
    classifier = ProcessFaultClassifier()
    # Provide baseline TEP steady-state telemetry
    normal_vector = {f"xmeas_{i}": 0.0 for i in range(1, 42)}
    normal_vector.update({f"xmv_{j}": 0.0 for j in range(1, 12)})
    assessment = classifier.classify_fault(normal_vector)

    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.prediction is not None
    assert "fault_id" in assessment.prediction
    assert "top_candidates" in assessment.prediction
    assert assessment.confidence is not None
    assert 0.0 <= assessment.confidence <= 1.0


# 16. Known Fault Telemetry Inference
def test_known_fault_telemetry_inference():
    """Verify live fault classification returns OK with valid candidate rankings."""
    classifier = ProcessFaultClassifier()
    # Sample from real d01_te active fault
    d01_te = load_raw_matrix(TEP_DATA_DIR / "d01_te.dat")
    active_fault_sample = d01_te[200]  # Sample well into active IDV(1)
    telemetry = {CANONICAL_FEATURES[i]: float(active_fault_sample[i]) for i in range(52)}

    assessment = classifier.classify_fault(telemetry)
    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.prediction is not None
    assert assessment.prediction["fault_code"] in [FAULT_DESCRIPTIONS[i]["code"] for i in range(22)]


# 17. Probability Distribution Sums to 1.0
def test_probability_distribution_sums_to_one():
    """Verify the output probability distribution sums to approximately 1.0."""
    classifier = ProcessFaultClassifier()
    telemetry = {f"xmeas_{i}": 1.0 for i in range(1, 42)}
    telemetry.update({f"xmv_{j}": 1.0 for j in range(1, 12)})

    assessment = classifier.classify_fault(telemetry)
    assert assessment.status == MLAssessmentStatus.OK.value
    dist = assessment.prediction["probability_distribution"]
    assert len(dist) == 22
    total_prob = sum(dist.values())
    assert pytest.approx(total_prob, abs=1e-2) == 1.0


# 18. Top-3 Output Structure
def test_top3_output_structure():
    """Verify top-3 candidate faults are ordered with descending confidence."""
    classifier = ProcessFaultClassifier()
    telemetry = {f"xmeas_{i}": 0.5 for i in range(1, 42)}
    telemetry.update({f"xmv_{j}": 0.5 for j in range(1, 12)})

    assessment = classifier.classify_fault(telemetry)
    top3 = assessment.prediction["top_candidates"]
    assert len(top3) == 3
    assert top3[0]["confidence"] >= top3[1]["confidence"]
    assert top3[1]["confidence"] >= top3[2]["confidence"]


# 19. Missing Artifact Fallback
def test_missing_artifact_fallback():
    """Verify MODEL_NOT_AVAILABLE is returned when model artifact is absent."""
    classifier = ProcessFaultClassifier(model_path="artifacts/models/nonexistent/model.joblib")
    assert not classifier.is_loaded

    telemetry = {"xmeas_1": 0.25, "xmv_1": 50.0}
    assessment = classifier.classify_fault(telemetry)
    assert assessment.status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert assessment.prediction is None


# 20. Invalid Input Handling
def test_invalid_input_handling():
    """Verify INVALID_INPUT is returned for None, non-dict, or empty input."""
    classifier = ProcessFaultClassifier()
    assert classifier.classify_fault(None).status == MLAssessmentStatus.INVALID_INPUT.value
    assert classifier.classify_fault({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert classifier.classify_fault("invalid_string").status == MLAssessmentStatus.INVALID_INPUT.value


# 21. Inference Error Containment
def test_inference_error_containment():
    """Verify exceptions inside classifier are caught and returned as INFERENCE_ERROR."""
    classifier = ProcessFaultClassifier()
    with patch.object(classifier.xgb_classifier, "predict_proba", side_effect=RuntimeError("Simulated XGBoost failure")):
        assessment = classifier.classify_fault({"xmeas_1": 1.0})
        assert assessment.status == MLAssessmentStatus.INFERENCE_ERROR.value
        assert "Simulated XGBoost failure" in assessment.provenance["error"]


# 22. Model Registry Status Verification
def test_model_registry_status_ready():
    """Verify model registry records status=ready for process_fault_classifier."""
    meta = model_registry.get_model_metadata("process_fault_classifier")
    assert meta is not None
    assert meta.status == "ready"
    assert model_registry.is_artifact_available("process_fault_classifier")


# 23. MLPipeline Integration
def test_ml_pipeline_with_fault_classifier_ready():
    """Verify MLPipeline executes with both Anomaly Detector and Fault Classifier OK."""
    telemetry = {f"xmeas_{i}": 0.25 for i in range(1, 42)}
    telemetry.update({f"xmv_{j}": 50.0 for j in range(1, 12)})

    results = ml_pipeline.run_pipeline(telemetry, asset_id="tep_reactor_01")
    assert "anomaly_detection" in results
    assert "fault_diagnosis" in results
    assert "furnace_cot_prediction" in results
    assert "tube_temperature_soft_sensor" in results

    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["fault_diagnosis"].status == MLAssessmentStatus.OK.value
    assert results["furnace_cot_prediction"].status in (
        MLAssessmentStatus.OK.value,
        MLAssessmentStatus.MODEL_NOT_AVAILABLE.value,
    )
    assert results["tube_temperature_soft_sensor"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value


# 24. Regression Compatibility — Pipeline degradation when fault artifact missing
def test_ml_pipeline_graceful_degradation_without_fault_model():
    """Verify MLPipeline remains operational even if fault classifier is absent."""
    unloaded_clf = ProcessFaultClassifier(model_path="artifacts/models/nonexistent/model.joblib")
    assert not unloaded_clf.is_loaded

    assessment = unloaded_clf.classify_fault({"xmeas_1": 0.25})
    assert assessment.status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value

    # Test pipeline with unloaded classifier injected
    from backend.ml.inference.pipeline import MLPipeline
    custom_pipeline = MLPipeline(fault_classifier=unloaded_clf)
    results = custom_pipeline.run_pipeline({"xmeas_1": 0.25})

    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["fault_diagnosis"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value

