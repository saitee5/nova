"""
ml_training/common/training_gate.py — Curated Dataset Security & Integrity Gate.

Enforces strict compliance with NOVA ML training policy:
1. Datasets MUST reside strictly under data/curated/
2. Training directly from data/raw/ or data/cleaned/ is strictly forbidden and fails closed.
3. Canonical file names and manifest specifications must match.
4. Schema, target existence, and target leakage protections are strictly validated.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import pandas as pd

logger = logging.getLogger("nova.ml.training_gate")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CURATED_DATA_DIR = REPO_ROOT / "data" / "curated"
MANIFESTS_DIR = REPO_ROOT / "data" / "manifests"

CANONICAL_DATASET_CONFIGS = {
    "tep": {
        "canonical_filename": "tep_canonical.csv",
        "relative_path": "data/curated/tep/tep_canonical.csv",
        "manifest_file": "tep_canonical_manifest.json",
        "target_column": "fault_number",
        "expected_columns_count": 55,
        "models": ["ProcessAnomalyDetector", "ProcessFaultClassifier"],
    },
    "furnace_cot": {
        "canonical_filename": "furnace_cot_canonical.csv",
        "relative_path": "data/curated/furnace_cot/furnace_cot_canonical.csv",
        "manifest_file": "furnace_cot_canonical_manifest.json",
        "target_column": "COT",
        "expected_columns_count": 17,
        "models": ["FurnaceCOTPredictor"],
    },
    "tube_temperature": {
        "canonical_filename": "tube_temperature_canonical.csv",
        "relative_path": "data/curated/tube_temperature/tube_temperature_canonical.csv",
        "manifest_file": "tube_temperature_canonical_manifest.json",
        "target_column": "TMT",
        "expected_columns_count": 18,
        "models": ["TubeTemperaturePredictor"],
    },
}


class CuratedDatasetSecurityError(ValueError):
    """Raised when an unauthorized, raw, cleaned, or invalid dataset path is supplied."""
    pass


class DatasetIntegrityError(ValueError):
    """Raised when dataset fails manifest validation, checksum, or schema requirements."""
    pass


class TargetLeakageError(ValueError):
    """Raised when the target variable is present in the input feature set."""
    pass


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 checksum of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class TrainingGate:
    """Reusable guard that enforces curated-only training and strict schema integrity."""

    @staticmethod
    def validate_dataset_path(
        supplied_path: Union[str, Path],
        expected_key: Optional[str] = None,
        expected_filename: Optional[str] = None,
    ) -> Path:
        """
        Validate that supplied_path:
        1. Resolves strictly within data/curated/
        2. Does not reference data/raw/ or data/cleaned/
        3. Exists on disk
        4. Matches expected canonical filename
        """
        path_obj = Path(supplied_path)
        if not path_obj.is_absolute():
            resolved = (REPO_ROOT / path_obj).resolve()
        else:
            resolved = path_obj.resolve()

        resolved_str = str(resolved).replace("\\", "/")
        repo_root_str = str(REPO_ROOT.resolve()).replace("\\", "/")
        curated_root_str = str(CURATED_DATA_DIR.resolve()).replace("\\", "/")

        # 1. Reject any raw or cleaned path references
        if "/data/raw" in resolved_str or "\\data\\raw" in str(resolved):
            raise CuratedDatasetSecurityError(
                f"SECURITY VIOLATION: Training from raw datasets is strictly forbidden. Path: {supplied_path}"
            )

        if "/data/cleaned" in resolved_str or "\\data\\cleaned" in str(resolved):
            raise CuratedDatasetSecurityError(
                f"SECURITY VIOLATION: Training from intermediate cleaned datasets is strictly forbidden. Path: {supplied_path}"
            )

        # 2. Enforce that path resides strictly inside data/curated/
        try:
            resolved.relative_to(CURATED_DATA_DIR.resolve())
        except ValueError:
            raise CuratedDatasetSecurityError(
                f"SECURITY VIOLATION: Final model training requires datasets strictly within {CURATED_DATA_DIR}. Got: {supplied_path}"
            )

        # 3. File existence
        if not resolved.exists():
            raise FileNotFoundError(f"Curated dataset file does not exist: {resolved}")

        # 4. Check expected filename if provided
        if expected_filename and resolved.name != expected_filename:
            raise DatasetIntegrityError(
                f"Filename mismatch: expected canonical dataset '{expected_filename}', got '{resolved.name}'"
            )

        # 5. Check expected dataset key
        if expected_key and expected_key in CANONICAL_DATASET_CONFIGS:
            config_filename = CANONICAL_DATASET_CONFIGS[expected_key]["canonical_filename"]
            if resolved.name != config_filename:
                raise DatasetIntegrityError(
                    f"Dataset key '{expected_key}' requires filename '{config_filename}', got '{resolved.name}'"
                )

        logger.info("TrainingGate: Path validation PASSED for %s", resolved)
        return resolved

    @staticmethod
    def validate_manifest(
        dataset_path: Path,
        verify_sha256: bool = False,
        manifest_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Verify that a manifest exists for the curated dataset and optionally verify checksum.
        """
        target_manifest = manifest_path
        if target_manifest is None:
            # Look in data/manifests/ for matching manifest
            stem = dataset_path.stem
            candidate = MANIFESTS_DIR / f"{stem}_manifest.json"
            if candidate.exists():
                target_manifest = candidate
            else:
                # Check inventory
                inv_path = MANIFESTS_DIR / "final_training_dataset_inventory.json"
                if inv_path.exists():
                    target_manifest = inv_path

        if target_manifest is None or not target_manifest.exists():
            raise DatasetIntegrityError(
                f"Curated dataset manifest is missing for {dataset_path}. Looked in {MANIFESTS_DIR}"
            )

        with open(target_manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        if verify_sha256 and "sha256" in manifest_data:
            expected_hash = manifest_data["sha256"]
            actual_hash = compute_file_sha256(dataset_path)
            if actual_hash != expected_hash:
                raise DatasetIntegrityError(
                    f"SHA-256 hash mismatch for {dataset_path.name}! Manifest: {expected_hash}, Actual: {actual_hash}"
                )

        logger.info("TrainingGate: Manifest validation PASSED using %s", target_manifest)
        return manifest_data

    @staticmethod
    def validate_schema_and_leakage(
        columns: Sequence[str],
        expected_target: str,
        expected_features: Sequence[str],
    ) -> None:
        """
        Verify:
        1. Target column is present in dataset columns
        2. All expected feature columns are present in dataset columns
        3. Target column is strictly NOT in expected feature columns (zero target leakage)
        """
        columns_set = set(columns)

        # 1. Target presence
        if expected_target not in columns_set:
            raise DatasetIntegrityError(
                f"Required target column '{expected_target}' is missing from dataset columns: {list(columns)}"
            )

        # 2. Features presence
        missing_features = [feat for feat in expected_features if feat not in columns_set]
        if missing_features:
            raise DatasetIntegrityError(
                f"Dataset is missing required feature columns: {missing_features}"
            )

        # 3. Target leakage guard
        if expected_target in expected_features:
            raise TargetLeakageError(
                f"CRITICAL TARGET LEAKAGE: Target '{expected_target}' is included in input feature list!"
            )

        logger.info("TrainingGate: Schema & target leakage validation PASSED.")

    @classmethod
    def guard(
        cls,
        dataset_path: Union[str, Path],
        expected_target: str,
        expected_features: Sequence[str],
        expected_key: Optional[str] = None,
        expected_filename: Optional[str] = None,
        verify_sha256: bool = False,
    ) -> Path:
        """Complete unified gate guard execution."""
        valid_path = cls.validate_dataset_path(
            supplied_path=dataset_path,
            expected_key=expected_key,
            expected_filename=expected_filename,
        )
        cls.validate_manifest(valid_path, verify_sha256=verify_sha256)

        # Quick header check without loading huge files into memory
        header_df = pd.read_csv(valid_path, nrows=2)
        cls.validate_schema_and_leakage(
            columns=header_df.columns,
            expected_target=expected_target,
            expected_features=expected_features,
        )
        return valid_path
