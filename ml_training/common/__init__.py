"""
ml_training/common package — Training Gates and Evaluation Artifact Persistence.
"""
from ml_training.common.metrics import save_evaluation_artifacts
from ml_training.common.training_gate import (
    CANONICAL_DATASET_CONFIGS,
    CuratedDatasetSecurityError,
    DatasetIntegrityError,
    TargetLeakageError,
    TrainingGate,
    compute_file_sha256,
)

__all__ = [
    "TrainingGate",
    "CuratedDatasetSecurityError",
    "DatasetIntegrityError",
    "TargetLeakageError",
    "CANONICAL_DATASET_CONFIGS",
    "compute_file_sha256",
    "save_evaluation_artifacts",
]
