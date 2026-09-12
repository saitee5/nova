"""
backend/ml/registry/registry.py — Industrial ML Model Registry.

Tracks machine learning model versions, artifact paths, training status,
feature schemas, datasets, and provenance across all planned industrial models.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("nova.ml.registry")

_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent.parent / "artifacts" / "models" / "registry.yaml"


class ModelMetadata(BaseModel):
    """Metadata specification for a registered ML model."""
    model_config = {"extra": "allow"}

    name: str
    version: str
    model_type: str
    algorithm: str
    status: str = "not_trained"  # "not_trained", "ready", "placeholder", "trained", "deprecated"
    dataset: str
    dataset_hash: str
    feature_schema: str
    target: str
    artifact_path: str
    preprocessing_artifact: Optional[str] = None
    evaluation_artifact: Optional[str] = None
    created_at: str
    description: str = ""


class ModelRegistry:
    """Central registry manager for pluggable industrial ML models."""

    def __init__(self, registry_yaml_path: Optional[str | Path] = None) -> None:
        self.manifest_path = Path(
            registry_yaml_path or os.environ.get("MODEL_REGISTRY_PATH", str(_DEFAULT_REGISTRY_PATH))
        )
        self._models: Dict[str, ModelMetadata] = {}
        self.load_registry()

    def load_registry(self) -> None:
        """Load registered models from YAML configuration manifest."""
        if not self.manifest_path.exists():
            logger.warning("Model registry manifest not found at %s. Initializing empty registry.", self.manifest_path)
            return

        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            models_data = data.get("models", {})
            for key, entry in models_data.items():
                self._models[key] = ModelMetadata(**entry)

            logger.info("Loaded %d model definitions from ML registry at %s", len(self._models), self.manifest_path)
        except Exception as exc:
            logger.error("Failed to parse model registry manifest: %s", exc)

    def get_model_metadata(self, model_key: str) -> Optional[ModelMetadata]:
        """Retrieve metadata for a specific model key."""
        return self._models.get(model_key)

    get_model_spec = get_model_metadata

    def list_models(self) -> List[ModelMetadata]:
        """List all registered models in the catalog."""
        return list(self._models.values())

    def is_artifact_available(self, model_key: str) -> bool:
        """Check if trained model binary / weights exist on disk."""
        meta = self.get_model_metadata(model_key)
        if not meta or meta.status == "not_trained":
            return False

        # Resolve artifact path relative to workspace root if needed
        art_path = Path(meta.artifact_path)
        if not art_path.is_absolute():
            repo_root = self.manifest_path.parent.parent.parent
            art_path = repo_root / art_path

        return art_path.exists()

    def register_model(self, model_key: str, metadata: ModelMetadata) -> None:
        """Programmatically register or update a model specification."""
        self._models[model_key] = metadata


# Global singleton instance
model_registry = ModelRegistry()
