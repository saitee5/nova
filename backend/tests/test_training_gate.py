"""
backend/tests/test_training_gate.py — Comprehensive Tests for Training Security Gate & Loader Integrity.

Verifies:
1. Raw dataset paths are strictly rejected (CuratedDatasetSecurityError)
2. Cleaned dataset paths are strictly rejected (CuratedDatasetSecurityError)
3. Non-curated arbitrary paths are strictly rejected (CuratedDatasetSecurityError)
4. Curated canonical paths are accepted
5. Target leakage (target inside feature list) is rejected (TargetLeakageError)
6. Missing target column is rejected (DatasetIntegrityError)
7. Missing feature columns are rejected (DatasetIntegrityError)
8. Missing manifests are rejected (DatasetIntegrityError)
9. Hash mismatch detection
10. Tube temperature physics-informed synthetic target metadata enforcement
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from ml_training.common.metrics import save_evaluation_artifacts
from ml_training.common.training_gate import (
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TargetLeakageError,
    TrainingGate,
    compute_file_sha256,
)
from ml_training.furnace.dataset import (
    CANONICAL_FEATURES as FURNACE_FEATURES,
    CURATED_FURNACE_COT_PATH,
    TARGET_COLUMN as FURNACE_TARGET,
    load_and_verify_furnace_dataset,
)
from ml_training.tep.dataset import (
    CANONICAL_FEATURES as TEP_FEATURES,
    CURATED_TEP_PATH,
    TARGET_COLUMN as TEP_TARGET,
    load_tep_splits,
)
from ml_training.tube_temperature.dataset import (
    CANONICAL_FEATURES as TUBE_FEATURES,
    CURATED_TUBE_TEMP_PATH,
    TARGET_COLUMN as TUBE_TARGET,
    TARGET_TYPE as TUBE_TARGET_TYPE,
    load_and_verify_tube_temp_dataset,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# 1. Raw Paths Rejected
def test_raw_path_rejected():
    """Verify that any path containing data/raw raises CuratedDatasetSecurityError."""
    raw_path = REPO_ROOT / "data" / "raw" / "ethylene-furnance-dataset.xlsx"
    with pytest.raises(CuratedDatasetSecurityError):
        TrainingGate.validate_dataset_path(raw_path)


# 2. Cleaned Paths Rejected
def test_cleaned_path_rejected():
    """Verify that any path containing data/cleaned raises CuratedDatasetSecurityError."""
    cleaned_path = REPO_ROOT / "data" / "cleaned" / "furnace_cot" / "furnace_cot_clean.csv"
    with pytest.raises(CuratedDatasetSecurityError):
        TrainingGate.validate_dataset_path(cleaned_path)


# 3. External Arbitrary Path Rejected
def test_external_path_rejected(tmp_path):
    """Verify that any file outside data/curated raises CuratedDatasetSecurityError."""
    fake_csv = tmp_path / "fake_dataset.csv"
    fake_csv.write_text("a,b,c\n1,2,3")
    with pytest.raises(CuratedDatasetSecurityError):
        TrainingGate.validate_dataset_path(fake_csv)


# 4. Curated Canonical Paths Accepted
def test_curated_paths_accepted():
    """Verify that valid curated dataset paths pass path validation."""
    p_tep = TrainingGate.validate_dataset_path(CURATED_TEP_PATH, expected_key="tep")
    assert p_tep == CURATED_TEP_PATH.resolve()

    p_furnace = TrainingGate.validate_dataset_path(CURATED_FURNACE_COT_PATH, expected_key="furnace_cot")
    assert p_furnace == CURATED_FURNACE_COT_PATH.resolve()

    p_tube = TrainingGate.validate_dataset_path(CURATED_TUBE_TEMP_PATH, expected_key="tube_temperature")
    assert p_tube == CURATED_TUBE_TEMP_PATH.resolve()


# 5. Target Leakage Rejected
def test_target_leakage_rejected():
    """Verify that having the target variable inside feature list raises TargetLeakageError."""
    with pytest.raises(TargetLeakageError):
        TrainingGate.validate_schema_and_leakage(
            columns=["C2H2", "Pressure", "COT"],
            expected_target="COT",
            expected_features=["C2H2", "Pressure", "COT"],  # Leakage!
        )


# 6. Missing Target Column Rejected
def test_missing_target_rejected():
    """Verify that missing expected target raises DatasetIntegrityError."""
    with pytest.raises(DatasetIntegrityError):
        TrainingGate.validate_schema_and_leakage(
            columns=["C2H2", "Pressure"],
            expected_target="COT",
            expected_features=["C2H2", "Pressure"],
        )


# 7. Missing Feature Columns Rejected
def test_missing_feature_rejected():
    """Verify that missing expected feature raises DatasetIntegrityError."""
    with pytest.raises(DatasetIntegrityError):
        TrainingGate.validate_schema_and_leakage(
            columns=["C2H2", "COT"],
            expected_target="COT",
            expected_features=["C2H2", "Pressure", "CH4"],
        )


# 8. Missing Manifest Rejected
def test_missing_manifest_rejected(tmp_path):
    """Verify that missing manifest raises DatasetIntegrityError."""
    fake_manifest = tmp_path / "nonexistent_manifest.json"
    with pytest.raises(DatasetIntegrityError):
        TrainingGate.validate_manifest(CURATED_FURNACE_COT_PATH, manifest_path=fake_manifest)


# 9. Hash Mismatch Detection
def test_hash_mismatch_detected(tmp_path):
    """Verify that SHA-256 mismatch in manifest is caught."""
    fake_manifest = tmp_path / "fake_manifest.json"
    fake_manifest.write_text(json.dumps({"sha256": "0000000000000000000000000000000000000000000000000000000000000000"}))

    with pytest.raises(DatasetIntegrityError):
        TrainingGate.validate_manifest(
            CURATED_FURNACE_COT_PATH,
            verify_sha256=True,
            manifest_path=fake_manifest,
        )


# 10. Tube Temperature Provenance Validation
def test_tube_temperature_provenance_metadata():
    """Verify TubeTemperaturePredictor metadata explicitly declares target_type as physics-informed synthetic."""
    assert TUBE_TARGET_TYPE == "physics-informed synthetic"
    split = load_and_verify_tube_temp_dataset(CURATED_TUBE_TEMP_PATH)
    assert len(split) == 30015
    assert "TMT" in split.columns
    assert "COT" in split.columns


# 11. Furnace Loader Fails on Raw Input
def test_furnace_loader_fails_on_raw():
    """Verify Furnace loader fails closed when raw file is passed."""
    raw_path = REPO_ROOT / "data" / "raw" / "ethylene-furnance-dataset.xlsx"
    with pytest.raises(CuratedDatasetSecurityError):
        load_and_verify_furnace_dataset(filepath=raw_path)


# 12. Standard Evaluation Artifact Saving
def test_evaluation_metric_persistence(tmp_path):
    """Verify save_evaluation_artifacts creates the expected directory structure and files."""
    metrics = {"mae": 1.25, "r2": 0.99}
    meta = {"dataset": "test"}
    preds = pd.DataFrame({"y_true": [1.0, 2.0], "y_pred": [1.1, 1.9]})

    saved_dir = save_evaluation_artifacts(
        model_name="TestModel",
        version="v1.0.0",
        metrics=metrics,
        training_metadata=meta,
        predictions_df=preds,
        eval_root=tmp_path,
    )

    assert (saved_dir / "metrics.json").exists()
    assert (saved_dir / "training_metadata.json").exists()
    assert (saved_dir / "test_predictions.csv").exists()
    assert (saved_dir / "evaluation_report.md").exists()
