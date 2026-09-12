"""
backend/tests/test_furnace_cot_predictor.py — Test suite for Industrial Ethylene Cracking Furnace COT Predictor.

Comprehensive test coverage covering Prompt 04 requirements:
1. Dataset exists
2. Dataset SHA-256
3. 17-column schema
4. zero-null validation
5. COT target range
6. chronological split
7. split sizes
8. zero leakage
9. canonical 16-feature schema
10. canonical feature ordering
11. preprocessor alias behavior
12. missing-input imputation
13. deterministic prediction
14. artifact serialization/deserialization
15. ModelRegistry loading
16. successful OK prediction
17. target unit metadata
18. residual when actual COT supplied
19. residual absent when actual COT absent
20. missing artifact → MODEL_NOT_AVAILABLE
21. invalid input → INVALID_INPUT
22. inference exception → INFERENCE_ERROR
23. registry status ready
24. MLPipeline integration
25. pipeline degradation when artifact missing
26. stream/asset isolation
27. target leakage prevention
28. production feature ordering
29. no actuation behavior
"""
import hashlib
import json
import os
import joblib
import numpy as np
import pandas as pd
import pytest
from typing import Any

from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor, furnace_cot_predictor
from backend.ml.inference.pipeline import MLPipeline
from backend.ml.registry.registry import model_registry
from backend.models.industrial_domain import MLAssessment, MLAssessmentStatus
from ml_training.furnace.dataset import (
    CANONICAL_FEATURES,
    EXPECTED_RAW_COLUMNS,
    EXPECTED_SHA256,
    RAW_DATASET_PATH,
    TARGET_COLUMN,
    load_and_verify_furnace_dataset,
    prepare_chronological_splits,
)
from ml_training.furnace.preprocessor import FurnaceCOTPreprocessor


@pytest.fixture(scope="module")
def furnace_df() -> pd.DataFrame:
    """Load authentic furnace dataset once for module-level verification."""
    return pd.read_csv(RAW_DATASET_PATH)


@pytest.fixture(scope="module")
def furnace_splits(furnace_df) -> Any:
    """Compute chronological splits once for module-level verification."""
    return prepare_chronological_splits(furnace_df)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Dataset Verification & Provenance (Tests 1-5)
# ──────────────────────────────────────────────────────────────────────────────

def test_01_dataset_file_exists():
    """Verify raw ethylene furnace Excel file exists at expected path."""
    assert os.path.exists(RAW_DATASET_PATH), f"Furnace dataset missing at {RAW_DATASET_PATH}"
    file_size = os.path.getsize(RAW_DATASET_PATH)
    assert file_size > 1_000_000, f"File size unexpectedly small: {file_size} bytes"


def test_02_dataset_sha256():
    """Verify cryptographic SHA-256 checksum matches authentic Figshare publication."""
    hasher = hashlib.sha256()
    with open(RAW_DATASET_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()
    assert actual_hash == EXPECTED_SHA256, f"Checksum mismatch: {actual_hash} != {EXPECTED_SHA256}"


def test_03_raw_dataset_17_column_schema(furnace_df):
    """Verify raw dataset has exactly 30,015 rows and 17 columns with exact names."""
    assert len(furnace_df) == 30015, f"Expected 30015 rows, got {len(furnace_df)}"
    assert list(furnace_df.columns) == EXPECTED_RAW_COLUMNS, f"Column mismatch: {list(furnace_df.columns)}"


def test_04_zero_null_validation(furnace_df):
    """Verify authentic dataset contains zero missing/null values across all columns."""
    null_counts = furnace_df.isnull().sum()
    assert null_counts.sum() == 0, f"Dataset contains unexpected nulls:\n{null_counts[null_counts > 0]}"


def test_05_cot_target_range(furnace_df):
    """Verify COT target exhibits realistic industrial cracking temperature range (790-950 °C)."""
    cot_vals = furnace_df[TARGET_COLUMN]
    assert cot_vals.min() >= 790.0, f"COT min too low: {cot_vals.min()} °C"
    assert cot_vals.max() <= 950.0, f"COT max too high: {cot_vals.max()} °C"
    assert 850.0 <= cot_vals.mean() <= 880.0, f"COT mean out of range: {cot_vals.mean()} °C"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Chronological Splitting & Leakage Controls (Tests 6-8, 27)
# ──────────────────────────────────────────────────────────────────────────────

def test_06_chronological_split(furnace_df, furnace_splits):
    """Verify split preserves chronological row ordering with zero random shuffling."""
    # First row of train must match first row of original data
    c2h4_val = furnace_splits.x_train.iloc[0].get("C2H4", furnace_splits.x_train.iloc[0].get("c2h4", 0.0))
    assert c2h4_val == pytest.approx(furnace_df.iloc[0]["C2H4"], abs=1e-6)
    # Target values must align identically
    assert furnace_splits.y_train.iloc[0] == pytest.approx(furnace_df.iloc[0][TARGET_COLUMN], abs=1e-6)
    # Val begins where train ends
    n_train = len(furnace_splits.x_train)
    assert furnace_splits.y_val.iloc[0] == pytest.approx(furnace_df.iloc[n_train][TARGET_COLUMN], abs=1e-6)
    # Test begins where val ends
    n_val = len(furnace_splits.x_val)
    assert furnace_splits.y_test.iloc[0] == pytest.approx(furnace_df.iloc[n_train + n_val][TARGET_COLUMN], abs=1e-6)



def test_07_split_sizes(furnace_splits):
    """Verify exact chronological split boundaries: 70% train (21010), 15% val (4502), 15% test (4503)."""
    assert len(furnace_splits.x_train) == 21010
    assert len(furnace_splits.y_train) == 21010
    assert len(furnace_splits.x_val) == 4502
    assert len(furnace_splits.y_val) == 4502
    assert len(furnace_splits.x_test) == 4503
    assert len(furnace_splits.y_test) == 4503
    assert len(furnace_splits.x_train) + len(furnace_splits.x_val) + len(furnace_splits.x_test) == 30015


def test_08_zero_data_leakage(furnace_splits):
    """Verify test and validation data do not contaminate training preprocessor statistics."""
    preprocessor = FurnaceCOTPreprocessor()
    preprocessor.fit(furnace_splits.x_train)

    # Check that preprocessor statistics are derived strictly from x_train
    for feature in CANONICAL_FEATURES:
        expected_mean = float(furnace_splits.x_train[feature].mean())
        assert preprocessor.feature_means_[feature] == pytest.approx(expected_mean, abs=1e-6)


def test_27_target_leakage_prevention():
    """Verify target COT is strictly excluded from preprocessed feature matrices."""
    preprocessor = FurnaceCOTPreprocessor()
    # Fit with canonical features
    dummy_train = pd.DataFrame([{col: 1.0 for col in CANONICAL_FEATURES}])
    preprocessor.fit(dummy_train)

    # Input with target present in various aliases
    telemetry_with_leak = {col: 1.0 for col in CANONICAL_FEATURES}
    telemetry_with_leak["COT"] = 850.0
    telemetry_with_leak["cot"] = 850.0
    telemetry_with_leak["coil_outlet_temperature"] = 850.0
    telemetry_with_leak["TI-20101"] = 850.0

    X = preprocessor.transform(telemetry_with_leak)
    assert X.shape == (1, 16), f"Feature matrix shape mismatch: {X.shape}"
    # Target columns must not be in preprocessor features
    assert "cot" not in preprocessor.feature_names
    assert "coil_outlet_temperature" not in preprocessor.feature_names
    assert "COT" not in preprocessor.feature_names


# ──────────────────────────────────────────────────────────────────────────────
# 3. Canonical Features, Preprocessing & Imputation (Tests 9-12, 28)
# ──────────────────────────────────────────────────────────────────────────────

def test_09_canonical_16_feature_schema():
    """Verify exactly 16 canonical production features are defined."""
    assert len(CANONICAL_FEATURES) == 16
    expected = [
        "c2h2", "c2h4", "c2h6", "c3h6", "c3h8", "c4h6", "c4h8",
        "c6h6", "c7h8", "c8h10", "c8h8", "ch4", "h2o", "h2",
        "furnace_pressure", "cracking_gas_temperature",
    ]
    # Check normalized lower-snake-case feature matching
    normalized_features = [
        "furnace_pressure" if f.lower() == "pressure" else f.lower().replace(" ", "_")
        for f in CANONICAL_FEATURES
    ]
    assert normalized_features == expected




def test_10_and_28_canonical_feature_ordering():
    """Verify strict, deterministic feature ordering in preprocessed 2D arrays."""
    preprocessor = FurnaceCOTPreprocessor()
    dummy_train = pd.DataFrame([{col: float(i + 1) for i, col in enumerate(CANONICAL_FEATURES)}])
    preprocessor.fit(dummy_train)

    # Feed arbitrary dict with scrambled key order
    scrambled = {
        "cracking_gas_temperature": 16.0,
        "h2": 14.0,
        "c2h2": 1.0,
        "c2h4": 2.0,
        "c2h6": 3.0,
        "c3h6": 4.0,
        "c3h8": 5.0,
        "c4h6": 6.0,
        "c4h8": 7.0,
        "c6h6": 8.0,
        "c7h8": 9.0,
        "c8h10": 10.0,
        "c8h8": 11.0,
        "ch4": 12.0,
        "h2o": 13.0,
        "furnace_pressure": 15.0,
    }
    arr = preprocessor.transform(scrambled)
    assert arr.shape == (1, 16)
    expected_order = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]])
    np.testing.assert_allclose(arr, expected_order)


def test_11_preprocessor_alias_behavior():
    """Verify preprocessor resolves documented telemetry aliases accurately."""
    preprocessor = FurnaceCOTPreprocessor()
    dummy_train = pd.DataFrame([{col: 10.0 for col in CANONICAL_FEATURES}])
    preprocessor.fit(dummy_train)

    # Pass aliases for pressure and cracking gas temp
    telemetry = {col: 5.0 for col in CANONICAL_FEATURES if col not in ("furnace_pressure", "cracking_gas_temperature")}
    telemetry["Pressure"] = 0.18
    telemetry["Cracking gas temperature"] = 620.5

    arr = preprocessor.transform(telemetry)
    # Check that pressure (index 14) and gas temp (index 15) got mapped
    assert arr[0, 14] == pytest.approx(0.18)
    assert arr[0, 15] == pytest.approx(620.5)


def test_12_missing_input_imputation():
    """Verify missing inputs are imputed using training-derived statistics, never live data."""
    preprocessor = FurnaceCOTPreprocessor()
    # Fit with known means
    known_data = pd.DataFrame([{col: 100.0 * (i + 1) for i, col in enumerate(CANONICAL_FEATURES)}])
    preprocessor.fit(known_data)

    # Empty/partial input
    partial = {"c2h4": 25.0}
    arr = preprocessor.transform(partial)

    # c2h4 (index 1) should be 25.0
    assert arr[0, 1] == pytest.approx(25.0)
    # c2h2 (index 0) was missing, should be training mean 100.0
    assert arr[0, 0] == pytest.approx(100.0)
    # cracking_gas_temperature (index 15) missing, should be training mean 1600.0
    assert arr[0, 15] == pytest.approx(1600.0)


# ──────────────────────────────────────────────────────────────────────────────
# 4. Artifact & Registry Verification (Tests 13-15, 23)
# ──────────────────────────────────────────────────────────────────────────────

def test_13_deterministic_prediction():
    """Verify repeated predictions on identical telemetry yield identical results."""
    predictor = FurnaceCOTPredictor()
    telemetry = {
        "c2h2": 0.5, "c2h4": 30.0, "c2h6": 35.0, "c3h6": 15.0, "c3h8": 1.0,
        "c4h6": 4.0, "c4h8": 2.0, "c6h6": 5.0, "c7h8": 2.5, "c8h10": 1.5,
        "c8h8": 0.8, "ch4": 12.0, "h2o": 45.0, "h2": 1.2,
        "furnace_pressure": 0.17, "cracking_gas_temperature": 600.0,
    }
    pred1 = predictor.predict_cot(telemetry)
    pred2 = predictor.predict_cot(telemetry)

    assert pred1.status == MLAssessmentStatus.OK.value
    assert pred2.status == MLAssessmentStatus.OK.value
    assert pred1.prediction["predicted_cot_celsius"] == pytest.approx(
        pred2.prediction["predicted_cot_celsius"], abs=1e-6
    )


def test_14_artifact_serialization_and_deserialization():
    """Verify saved joblib model artifact loads cleanly and matches schema."""
    artifact_path = "artifacts/models/furnace_cot_predictor/v1.0.0/model.joblib"
    assert os.path.exists(artifact_path)
    assert os.path.getsize(artifact_path) > 100_000

    pkg = joblib.load(artifact_path)
    assert "model" in pkg
    assert "preprocessor" in pkg
    assert "metadata" in pkg
    assert pkg["metadata"]["model_name"] == "furnace_cot_predictor"
    assert pkg["metadata"]["version"] == "v1.0.0"
    assert pkg["metadata"]["target"] == "coil_outlet_temperature"


def test_15_and_23_model_registry_status_ready():
    """Verify ModelRegistry loads furnace_cot_predictor with status 'ready' or validated."""
    spec = model_registry.get_model_metadata("furnace_cot_predictor")
    assert spec is not None
    assert spec.status in ("ready", "VALIDATED", "VALIDATED_WITH_LIMITATIONS")
    assert spec.version in ("v1.0.0", "v1.1.0")
    assert spec.target in ("coil_outlet_temperature", "coil_outlet_temperature_celsius")
    # Evaluation metrics
    metrics = getattr(spec, "evaluation_metrics", None) or getattr(spec, "metrics", {})
    mae = metrics.get("mae_celsius", metrics.get("mae"))
    assert mae is not None and mae < 3.0, f"Expected industrial MAE < 3.0 °C, got {mae}"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Production Inference & Contracts (Tests 16-22)
# ──────────────────────────────────────────────────────────────────────────────

def test_16_and_17_successful_ok_prediction_with_metadata():
    """Verify predict_cot returns OK status, realistic temperature, and target unit metadata."""
    predictor = FurnaceCOTPredictor()
    telemetry = {
        "c2h2": 0.5, "c2h4": 30.0, "c2h6": 35.0, "c3h6": 15.0, "c3h8": 1.0,
        "c4h6": 4.0, "c4h8": 2.0, "c6h6": 5.0, "c7h8": 2.5, "c8h10": 1.5,
        "c8h8": 0.8, "ch4": 12.0, "h2o": 45.0, "h2": 1.2,
        "furnace_pressure": 0.17, "cracking_gas_temperature": 600.0,
    }
    assessment = predictor.predict_cot(telemetry)

    assert assessment.status == MLAssessmentStatus.OK.value
    cot_val = assessment.prediction["predicted_cot_celsius"]
    assert 780.0 <= cot_val <= 960.0
    assert assessment.prediction["target_unit"] == "celsius"
    assert assessment.model_version in ("v1.0.0", "v1.1.0")
    assert "Industrial Ethylene Cracking" in assessment.provenance["dataset"]


def test_18_residual_when_actual_cot_supplied():
    """Verify residual_celsius is computed accurately when actual COT is supplied."""
    predictor = FurnaceCOTPredictor()
    telemetry = {
        "c2h2": 0.5, "c2h4": 30.0, "c2h6": 35.0, "c3h6": 15.0, "c3h8": 1.0,
        "c4h6": 4.0, "c4h8": 2.0, "c6h6": 5.0, "c7h8": 2.5, "c8h10": 1.5,
        "c8h8": 0.8, "ch4": 12.0, "h2o": 45.0, "h2": 1.2,
        "furnace_pressure": 0.17, "cracking_gas_temperature": 600.0,
        "COT": 860.0,
    }
    assessment = predictor.predict_cot(telemetry)
    assert assessment.status == MLAssessmentStatus.OK.value
    expected_residual = 860.0 - assessment.prediction["predicted_cot_celsius"]
    assert assessment.prediction["residual_celsius"] == pytest.approx(expected_residual, abs=1e-2)


def test_19_residual_absent_when_actual_cot_absent():
    """Verify residual_celsius is strictly None when actual COT is not in telemetry."""
    predictor = FurnaceCOTPredictor()
    telemetry = {
        "c2h2": 0.5, "c2h4": 30.0, "c2h6": 35.0, "c3h6": 15.0, "c3h8": 1.0,
        "c4h6": 4.0, "c4h8": 2.0, "c6h6": 5.0, "c7h8": 2.5, "c8h10": 1.5,
        "c8h8": 0.8, "ch4": 12.0, "h2o": 45.0, "h2": 1.2,
        "furnace_pressure": 0.17, "cracking_gas_temperature": 600.0,
    }
    assessment = predictor.predict_cot(telemetry)
    assert assessment.status == MLAssessmentStatus.OK.value
    assert assessment.prediction["residual_celsius"] is None


def test_20_missing_artifact_returns_model_not_available():
    """Verify predictor gracefully returns MODEL_NOT_AVAILABLE when artifact is absent."""
    unloaded = FurnaceCOTPredictor(model_path="artifacts/models/nonexistent/model.joblib")
    assert not unloaded.is_loaded

    assessment = unloaded.predict_cot({"c2h4": 30.0})
    assert assessment.status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert assessment.prediction is None
    assert assessment.confidence == 0.0


def test_21_invalid_input_returns_invalid_input():
    """Verify predictor returns INVALID_INPUT for None, empty dict, or non-dict input."""
    predictor = FurnaceCOTPredictor()

    # None
    assert predictor.predict_cot(None).status == MLAssessmentStatus.INVALID_INPUT.value
    # Empty dict
    assert predictor.predict_cot({}).status == MLAssessmentStatus.INVALID_INPUT.value
    # Non-dict
    assert predictor.predict_cot([1, 2, 3]).status == MLAssessmentStatus.INVALID_INPUT.value
    assert predictor.predict_cot("telemetry").status == MLAssessmentStatus.INVALID_INPUT.value


def test_22_inference_exception_returns_inference_error():
    """Verify unexpected runtime errors are caught and return INFERENCE_ERROR without crashing."""
    predictor = FurnaceCOTPredictor()
    # Corrupt model references deliberately
    predictor._model = "not_a_model"
    predictor.xgb_regressor = "not_a_model"

    assessment = predictor.predict_cot({"c2h4": 30.0})
    assert assessment.status == MLAssessmentStatus.INFERENCE_ERROR.value
    assert assessment.prediction is None


# ──────────────────────────────────────────────────────────────────────────────
# 6. Pipeline Integration & Stream Isolation (Tests 24-26, 29)
# ──────────────────────────────────────────────────────────────────────────────

def test_24_mlpipeline_integration():
    """Verify MLPipeline produces OK for anomaly, fault, and furnace COT, while tube temp remains NOT_AVAILABLE."""
    pipeline = MLPipeline()
    telemetry = {
        "c2h2": 0.5, "c2h4": 30.0, "c2h6": 35.0, "c3h6": 15.0, "c3h8": 1.0,
        "c4h6": 4.0, "c4h8": 2.0, "c6h6": 5.0, "c7h8": 2.5, "c8h10": 1.5,
        "c8h8": 0.8, "ch4": 12.0, "h2o": 45.0, "h2": 1.2,
        "furnace_pressure": 0.17, "cracking_gas_temperature": 600.0,
    }
    results = pipeline.run_pipeline(telemetry, asset_id="F-201A")

    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["fault_diagnosis"].status == MLAssessmentStatus.OK.value
    assert results["furnace_cot_prediction"].status == MLAssessmentStatus.OK.value
    assert results["tube_temperature_soft_sensor"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value


def test_25_pipeline_graceful_degradation_when_furnace_artifact_missing():
    """Verify missing furnace model does not crash pipeline or degrade unrelated detectors."""
    pipeline = MLPipeline()
    # Temporarily substitute missing furnace predictor
    pipeline.furnace_cot_predictor = FurnaceCOTPredictor(model_path="nonexistent.joblib")

    results = pipeline.run_pipeline({"xmeas_1": 0.25}, asset_id="F-201A")
    assert results["anomaly_detection"].status == MLAssessmentStatus.OK.value
    assert results["fault_diagnosis"].status == MLAssessmentStatus.OK.value
    assert results["furnace_cot_prediction"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert results["tube_temperature_soft_sensor"].status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value


def test_26_stream_asset_isolation():
    """Verify telemetry state is isolated across streams without cross-stream contamination."""
    predictor = FurnaceCOTPredictor()

    stream_a = {"c2h4": 20.0, "cracking_gas_temperature": 550.0}
    stream_b = {"c2h4": 40.0, "cracking_gas_temperature": 680.0}

    res_a1 = predictor.predict_cot(stream_a, asset_id="F-201A")
    res_b = predictor.predict_cot(stream_b, asset_id="F-201B")
    res_a2 = predictor.predict_cot(stream_a, asset_id="F-201A")

    # Predictor must be stateless or properly scoped by asset
    assert res_a1.prediction["predicted_cot_celsius"] == pytest.approx(
        res_a2.prediction["predicted_cot_celsius"], abs=1e-6
    )
    assert res_a1.prediction["predicted_cot_celsius"] != res_b.prediction["predicted_cot_celsius"]


def test_29_zero_industrial_actuation():
    """Verify FurnaceCOTPredictor only produces analytical assessments without actuation side effects."""
    predictor = FurnaceCOTPredictor()
    telemetry = {"c2h4": 30.0, "cracking_gas_temperature": 600.0}
    assessment = predictor.predict_cot(telemetry)

    # Assessment must be strictly informational/analytical
    assert isinstance(assessment, MLAssessment)
    assert not hasattr(assessment, "execute_control")
    assert not hasattr(assessment, "write_plc")
    assert not hasattr(assessment, "adjust_valves")
    assert assessment.status == MLAssessmentStatus.OK.value
