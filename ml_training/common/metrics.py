"""
ml_training/common/metrics.py — Standard ML Evaluation Metric Persistence.

Implements standard serialization structure for model evaluation deliverables:
artifacts/evaluation/<model_name>/<version>/
├── metrics.json
├── evaluation_report.md
├── test_predictions.csv (optional)
├── confusion_matrix.csv (optional)
└── training_metadata.json
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
import numpy as np
import pandas as pd

logger = logging.getLogger("nova.ml.metrics_persistence")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVALUATION_ROOT = REPO_ROOT / "artifacts" / "evaluation"


def _json_serializable(obj: Any) -> Any:
    """Convert numpy / pandas scalar types to native Python JSON serializable types."""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


def save_evaluation_artifacts(
    model_name: str,
    version: str,
    metrics: Dict[str, Any],
    training_metadata: Dict[str, Any],
    predictions_df: Optional[pd.DataFrame] = None,
    confusion_matrix_df: Optional[pd.DataFrame] = None,
    report_markdown: Optional[str] = None,
    eval_root: Optional[Path] = None,
) -> Path:
    """
    Persist standardized evaluation artifacts to disk.
    Directory: artifacts/evaluation/<model_name>/<version>/
    """
    base_dir = eval_root or EVALUATION_ROOT
    target_dir = base_dir / model_name / version
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. metrics.json
    clean_metrics = {k: _json_serializable(v) for k, v in metrics.items()}
    metrics_path = target_dir / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(clean_metrics, f, indent=2)

    # 2. training_metadata.json
    clean_meta = {k: _json_serializable(v) for k, v in training_metadata.items()}
    if "saved_at" not in clean_meta:
        clean_meta["saved_at"] = datetime.now(timezone.utc).isoformat()
    clean_meta["model_name"] = model_name
    clean_meta["version"] = version

    meta_path = target_dir / "training_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(clean_meta, f, indent=2)

    # 3. test_predictions.csv
    if predictions_df is not None:
        pred_path = target_dir / "test_predictions.csv"
        predictions_df.to_csv(pred_path, index=False)

    # 4. confusion_matrix.csv
    if confusion_matrix_df is not None:
        cm_path = target_dir / "confusion_matrix.csv"
        confusion_matrix_df.to_csv(cm_path, index=True)

    # 5. evaluation_report.md
    if report_markdown:
        report_content = report_markdown
    else:
        # Generate default markdown report
        lines = [
            f"# Evaluation Report: {model_name} ({version})",
            "",
            f"- **Generated At:** {datetime.now(timezone.utc).isoformat()}",
            f"- **Model Name:** `{model_name}`",
            f"- **Model Version:** `{version}`",
            "",
            "## Summary Metrics",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
        ]
        for k, v in clean_metrics.items():
            if isinstance(v, (int, float, str)):
                lines.append(f"| `{k}` | {v} |")
        lines.append("")
        lines.append("## Training Metadata")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(clean_meta, indent=2))
        lines.append("```")
        lines.append("")
        report_content = "\n".join(lines)

    report_path = target_dir / "evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    logger.info("Saved standardized evaluation artifacts to %s", target_dir)
    return target_dir
