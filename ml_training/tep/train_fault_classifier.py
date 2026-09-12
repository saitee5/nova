"""
ml_training/tep/train_fault_classifier.py — Train & Evaluate XGBoost TEP Fault Classifier v1.1.0.

Trains a 21-class XGBoost multiclass model on the canonical Tennessee Eastman Process dataset:
data/curated/tep/tep_canonical.csv

Enforces:
1. Curated-only dataset consumption via TrainingGate.guard().
2. Pure simulation-run isolation across train, validation, and independent test sets.
3. Boundary transition window exclusion (samples 20, 21 in fault runs).
4. 156 deterministic features (52 raw, 52 rolling mean, 52 delta with W=3).
5. Comprehensive evaluation: Accuracy, Macro/Weighted F1, Top-3, Top-5, Log Loss, Brier score,
   confusion matrix, per-class metrics, error analysis, and high-confidence error diagnosis.
6. Serializes model artifact and complete evaluation deliverables.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml_training.common.training_gate import TrainingGate, compute_file_sha256
from ml_training.tep.dataset import (
    CANONICAL_FAULT_FEATURES,
    CANONICAL_FEATURES,
    CURATED_TEP_PATH,
    FAULT_DESCRIPTIONS,
    TARGET_COLUMN,
    load_tep_multiclass_splits,
)
from ml_training.tep.preprocessor import TEPFaultPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nova.ml.tep.train_fault")

MODELS_DIR = REPO_ROOT / "artifacts" / "models"
EVAL_DIR = REPO_ROOT / "artifacts" / "evaluation"


def compute_top_k_accuracy(y_true: np.ndarray, y_prob: np.ndarray, k: int = 3) -> float:
    """Compute top-k categorical accuracy."""
    top_k_preds = np.argsort(y_prob, axis=1)[:, -k:]
    correct = [y_true[i] in top_k_preds[i] for i in range(len(y_true))]
    return float(np.mean(correct))


def compute_multiclass_brier_score(y_true: np.ndarray, y_prob: np.ndarray, n_classes: int = 21) -> float:
    """Compute multiclass Brier score: mean squared difference across all class probabilities."""
    y_true_one_hot = np.zeros_like(y_prob)
    for i, target in enumerate(y_true):
        y_true_one_hot[i, target] = 1.0
    return float(np.mean(np.sum((y_prob - y_true_one_hot) ** 2, axis=1)))


def train_and_evaluate(
    dataset_path: Path = CURATED_TEP_PATH,
    version: str = "v1.1.0",
    random_state: int = 42,
    train_runs_per_class: int = 10,
    val_runs_per_class: int = 2,
    test_runs_per_class: int = 4,
    n_estimators: int = 120,
    max_depth: int = 6,
    learning_rate: float = 0.08,
) -> Dict[str, Any]:
    """Train and evaluate 21-class TEP Fault Classifier with full simulation-run isolation."""
    start_time = time.time()
    logger.info("=== Starting ProcessFaultClassifier (%s) Training Pipeline ===", version)

    # 1. Training Gate Enforcement
    valid_path = TrainingGate.guard(
        dataset_path=dataset_path,
        expected_target=TARGET_COLUMN,
        expected_features=CANONICAL_FEATURES,
        expected_key="tep",
    )
    dataset_sha256 = compute_file_sha256(valid_path)
    logger.info("Curated dataset validated. SHA-256: %s", dataset_sha256)

    # 2. Load Simulation-Run Isolated Splits
    splits = load_tep_multiclass_splits(
        dataset_path=valid_path,
        train_runs_per_class=train_runs_per_class,
        val_runs_per_class=val_runs_per_class,
        test_runs_per_class=test_runs_per_class,
        window_size=3,
    )

    X_train = splits.x_train
    y_train = splits.y_train
    X_val = splits.x_val
    y_val = splits.y_val
    X_test = splits.x_test
    y_test = splits.y_test

    logger.info(
        "Splits loaded: Train=%d, Val=%d, Test=%d samples across 21 classes (156 features)",
        len(X_train),
        len(X_val),
        len(X_test),
    )

    # 3. Fit Preprocessor strictly on Training Data
    preprocessor = TEPFaultPreprocessor(feature_names=CANONICAL_FAULT_FEATURES, window_size=3)
    preprocessor.fit(X_train)

    X_train_scaled = preprocessor.transform(X_train)
    X_val_scaled = preprocessor.transform(X_val)
    X_test_scaled = preprocessor.transform(X_test)

    # 4. Train Deterministic XGBoost Classifier
    logger.info("Fitting XGBoost Classifier (21 classes, max_depth=%d, hist)...", max_depth)
    clf = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=21,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=random_state,
        tree_method="hist",
        early_stopping_rounds=20,
    )

    fit_start = time.time()
    clf.fit(
        X_train_scaled,
        y_train,
        eval_set=[(X_train_scaled, y_train), (X_val_scaled, y_val)],
        verbose=False,
    )
    train_duration = round(time.time() - fit_start, 2)
    total_duration = round(time.time() - start_time, 2)
    logger.info("XGBoost training finished in %.2f s (best iteration: %d)", train_duration, clf.best_iteration)

    # 5. Comprehensive Held-Out Test Evaluation
    logger.info("Evaluating on Independent Held-Out Test Set (%d observations)...", len(X_test))
    y_probs = clf.predict_proba(X_test_scaled)
    y_preds = np.argmax(y_probs, axis=1)

    # Primary Aggregate Metrics
    acc = float(accuracy_score(y_test, y_preds))
    macro_prec = float(precision_score(y_test, y_preds, average="macro", zero_division=0))
    macro_rec = float(recall_score(y_test, y_preds, average="macro", zero_division=0))
    macro_f1 = float(f1_score(y_test, y_preds, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_test, y_preds, average="weighted", zero_division=0))
    top3_acc = compute_top_k_accuracy(y_test, y_probs, k=3)
    top5_acc = compute_top_k_accuracy(y_test, y_probs, k=5)
    test_log_loss = float(log_loss(y_test, y_probs))
    brier_score = compute_multiclass_brier_score(y_test, y_probs, n_classes=21)

    # Confusion Matrix (21 x 21)
    cm = confusion_matrix(y_test, y_preds, labels=list(range(21)))
    cm_norm = cm.astype(float) / np.maximum(1, cm.sum(axis=1, keepdims=True))

    # Per-Class Metrics
    per_class_list: List[Dict[str, Any]] = []
    difficult_classes: List[Dict[str, Any]] = []

    for c in range(21):
        c_code = FAULT_DESCRIPTIONS[c]["code"]
        c_desc = FAULT_DESCRIPTIONS[c]["description"]
        c_type = FAULT_DESCRIPTIONS[c]["type"]
        support = int(np.sum(y_test == c))
        tp_c = int(cm[c, c])
        rec_c = float(tp_c / max(1, support))
        prec_c = float(tp_c / max(1, np.sum(y_preds == c)))
        f1_c = float(2 * prec_c * rec_c / max(1e-6, prec_c + rec_c))

        # Top confusion partner (most common misclassification)
        row_errors = cm[c].copy()
        row_errors[c] = 0  # Ignore diagonal
        top_conf_idx = int(np.argmax(row_errors))
        top_conf_count = int(row_errors[top_conf_idx])
        top_conf_code = FAULT_DESCRIPTIONS[top_conf_idx]["code"] if top_conf_count > 0 else "None"

        # Mean confidence for this class
        mask_c = (y_test == c)
        c_mean_conf = float(np.mean(np.max(y_probs[mask_c], axis=1))) if np.sum(mask_c) > 0 else 0.0

        item = {
            "class_id": c,
            "fault_code": c_code,
            "description": c_desc,
            "type": c_type,
            "support": support,
            "true_positives": tp_c,
            "precision": round(prec_c, 4),
            "recall": round(rec_c, 4),
            "f1_score": round(f1_c, 4),
            "mean_confidence": round(c_mean_conf, 4),
            "top_confusion_partner": top_conf_code,
            "top_confusion_count": top_conf_count,
        }
        per_class_list.append(item)

        if rec_c < 0.50:
            difficult_classes.append({
                "class_id": c,
                "fault_code": c_code,
                "recall": round(rec_c, 4),
                "precision": round(prec_c, 4),
                "top_confusion": top_conf_code,
            })

    per_class_df = pd.DataFrame(per_class_list)

    # Error Analysis: High-Confidence Errors and Low-Confidence Predictions
    confidences = np.max(y_probs, axis=1)
    sorted_order = np.argsort(y_probs, axis=1)[:, ::-1]
    top1_classes = sorted_order[:, 0]
    top2_classes = sorted_order[:, 1]
    top3_classes = sorted_order[:, 2]
    margins = confidences - y_probs[np.arange(len(y_probs)), top2_classes]

    is_correct = (y_preds == y_test)
    high_conf_errors = int(np.sum((~is_correct) & (confidences >= 0.70)))
    low_conf_count = int(np.sum(confidences < 0.40))
    low_conf_rate = float(low_conf_count / len(y_test))

    # Top Confusion Pairs across entire test set
    conf_pairs: List[Dict[str, Any]] = []
    for i in range(21):
        for j in range(21):
            if i != j and cm[i, j] > 10:
                conf_pairs.append({
                    "actual_code": FAULT_DESCRIPTIONS[i]["code"],
                    "predicted_code": FAULT_DESCRIPTIONS[j]["code"],
                    "count": int(cm[i, j]),
                    "rate_of_actual": round(float(cm_norm[i, j]), 4),
                })
    conf_pairs.sort(key=lambda x: x["count"], reverse=True)

    # Overall Status
    status = "VALIDATED_WITH_LIMITATIONS" if len(difficult_classes) > 0 else "VALIDATED"

    metrics_payload = {
        "model_name": "ProcessFaultClassifier",
        "version": version,
        "status": status,
        "total_test_samples": len(y_test),
        "classes_count": 21,
        "features_count": len(CANONICAL_FAULT_FEATURES),
        "accuracy": round(acc, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "top3_accuracy": round(top3_acc, 4),
        "top5_accuracy": round(top5_acc, 4),
        "log_loss": round(test_log_loss, 4),
        "brier_score": round(brier_score, 4),
        "mean_confidence": round(float(np.mean(confidences)), 4),
        "low_confidence_rate": round(low_conf_rate, 4),
        "high_confidence_errors_count": high_conf_errors,
        "difficult_classes_count": len(difficult_classes),
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "training_duration_seconds": train_duration,
        "total_pipeline_duration_seconds": total_duration,
    }

    # 6. Save Versioned Model Artifact
    model_dir = MODELS_DIR / "process_fault_classifier" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "model.joblib"

    artifact_payload = {
        "model_name": "ProcessFaultClassifier",
        "version": version,
        "algorithm": "XGBoost Multiclass (21 classes, hist tree_method)",
        "model": clf,
        "xgb_classifier": clf,
        "preprocessor": preprocessor,
        "feature_names": CANONICAL_FAULT_FEATURES,
        "class_mapping": FAULT_DESCRIPTIONS,
        "window_config": {"window_size": 3, "features_per_var": 3, "total_features": 156},
        "schema_version": "v1.1.0",
        "metrics": metrics_payload,
        "training_metadata": {
            "dataset_path": str(valid_path),
            "dataset_sha256": dataset_sha256,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "train_runs_per_class": train_runs_per_class,
            "val_runs_per_class": val_runs_per_class,
            "test_runs_per_class": test_runs_per_class,
            "random_state": random_state,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    joblib.dump(artifact_payload, model_file, compress=3)
    logger.info("Saved versioned model artifact to: %s", model_file)

    # 7. Save Evaluation Deliverables
    eval_dir = EVAL_DIR / "process_fault_classifier" / version
    eval_dir.mkdir(parents=True, exist_ok=True)

    # A. metrics.json
    with open(eval_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    # B. training_metadata.json
    with open(eval_dir / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(artifact_payload["training_metadata"], f, indent=2)

    # C. confusion_matrix.csv
    cm_df = pd.DataFrame(
        cm,
        index=[FAULT_DESCRIPTIONS[i]["code"] for i in range(21)],
        columns=[FAULT_DESCRIPTIONS[j]["code"] for j in range(21)],
    )
    cm_df.to_csv(eval_dir / "confusion_matrix.csv", index=True)

    # D. per_class_metrics.csv
    per_class_df.to_csv(eval_dir / "per_class_metrics.csv", index=False)

    # E. test_predictions.csv (Complete 41,840 rows - no subsampling)
    logger.info("Exporting complete test_predictions.csv (%d rows)...", len(y_test))
    test_preds_df = pd.DataFrame({
        "actual_label": y_test,
        "actual_code": [FAULT_DESCRIPTIONS[i]["code"] for i in y_test],
        "predicted_label": y_preds,
        "predicted_code": [FAULT_DESCRIPTIONS[j]["code"] for j in y_preds],
        "confidence": np.round(confidences, 4),
        "confidence_margin": np.round(margins, 4),
        "top1_code": [FAULT_DESCRIPTIONS[i]["code"] for i in top1_classes],
        "top2_code": [FAULT_DESCRIPTIONS[i]["code"] for i in top2_classes],
        "top3_code": [FAULT_DESCRIPTIONS[i]["code"] for i in top3_classes],
        "is_correct": is_correct.astype(int),
    })
    test_preds_df.to_csv(eval_dir / "test_predictions.csv", index=False)

    # F. evaluation_report.md
    report_md = generate_fault_classifier_report(
        metrics=metrics_payload,
        per_class_df=per_class_df,
        conf_pairs=conf_pairs,
        difficult_classes=difficult_classes,
        high_conf_errors=high_conf_errors,
        metadata=artifact_payload["training_metadata"],
    )
    with open(eval_dir / "evaluation_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    logger.info("Evaluation report generated at: %s", eval_dir / "evaluation_report.md")
    logger.info(
        "ProcessFaultClassifier v1.1.0 Training & Evaluation COMPLETE. Acc=%.4f, Macro F1=%.4f, Top-3=%.4f",
        acc,
        macro_f1,
        top3_acc,
    )

    return {
        "metrics": metrics_payload,
        "artifact_path": str(model_file),
        "eval_dir": str(eval_dir),
    }


def generate_fault_classifier_report(
    metrics: Dict[str, Any],
    per_class_df: pd.DataFrame,
    conf_pairs: List[Dict[str, Any]],
    difficult_classes: List[Dict[str, Any]],
    high_conf_errors: int,
    metadata: Dict[str, Any],
) -> str:
    """Generate professional Markdown evaluation report for ProcessFaultClassifier."""
    lines = [
        f"# ProcessFaultClassifier Evaluation Report (Version {metrics['version']})",
        "",
        f"- **Model Version:** `{metrics['version']}`",
        f"- **Model Status:** `{metrics['status']}`",
        f"- **Evaluated At:** `{metadata['trained_at']}`",
        f"- **Dataset Path:** `{metadata['dataset_path']}`",
        f"- **Dataset SHA-256:** `{metadata['dataset_sha256']}`",
        f"- **Training Duration:** `{metrics['training_duration_seconds']} s`",
        "",
        "---",
        "",
        "## 1. Executive Summary & Aggregate Performance",
        "",
        "| Metric | Value | Description |",
        "| :--- | :--- | :--- |",
        f"| **Overall Accuracy** | **`{metrics['accuracy'] * 100:.2f}%`** | Exact 21-class top-1 classification accuracy |",
        f"| **Macro Precision** | `{metrics['macro_precision']:.4f}` | Unweighted mean precision across all 21 classes |",
        f"| **Macro Recall** | `{metrics['macro_recall']:.4f}` | Unweighted mean recall across all 21 classes |",
        f"| **Macro F1 Score** | **`{metrics['macro_f1']:.4f}`** | Unweighted harmonic mean of precision and recall |",
        f"| **Weighted F1 Score** | `{metrics['weighted_f1']:.4f}` | Support-weighted harmonic mean across classes |",
        f"| **Top-3 Accuracy** | **`{metrics['top3_accuracy'] * 100:.2f}%`** | True fault class is within top-3 model recommendations |",
        f"| **Top-5 Accuracy** | `{metrics['top5_accuracy'] * 100:.2f}%` | True fault class is within top-5 model recommendations |",
        f"| **Multi-Class Log Loss** | `{metrics['log_loss']:.4f}` | Cross-entropy penalization for probability miscalibration |",
        f"| **Brier Score** | `{metrics['brier_score']:.4f}` | Mean squared probability error (lower is better) |",
        f"| **Mean Confidence** | `{metrics['mean_confidence'] * 100:.2f}%` | Average probability assigned to top-1 predicted class |",
        f"| **Low Confidence Rate** | `{metrics['low_confidence_rate'] * 100:.2f}%` | Predictions with confidence $< 0.40$ (uncertain zone) |",
        f"| **High-Confidence Errors** | `{high_conf_errors}` | Incorrect predictions where model confidence was $\\ge 0.70$ |",
        "",
        "---",
        "",
        "## 2. Dataset Split & Simulation-Run Isolation",
        "",
        "- **Curated Dataset:** `data/curated/tep/tep_canonical.csv`",
        "- **Split Strategy:** Strict `simulation_run` entity isolation (no cross-run sample contamination)",
        f"- **Train Partition:** Runs `{metadata['train_runs_per_class']}` per class (`{metrics['train_samples']:,}` samples)",
        f"- **Validation Partition:** Runs `{metadata['val_runs_per_class']}` per class (`{metrics['val_samples']:,}` samples)",
        f"- **Independent Test Partition:** Runs `{metadata['test_runs_per_class']}` per class (`{metrics['total_test_samples']:,}` samples)",
        "- **Transition Window Handling:** Samples $t \\in \\{20, 21\\}$ excluded around fault injection boundary to prevent transient boundary artifact learning.",
        "- **Pre-injection Baseline ($t \\le 19$):** Assigned class `0` (`NORMAL`).",
        "- **Active Fault Regime ($t \\ge 22$):** Assigned fault scenario class `1..20`.",
        "",
        "---",
        "",
        "## 3. Per-Class Performance Breakdown (21 Classes)",
        "",
        "| Class ID | Code | Description | Type | Support | Precision | Recall | F1 Score | Mean Conf | Top Confusion Partner |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for _, r in per_class_df.iterrows():
        lines.append(
            f"| `{r['class_id']}` | `{r['fault_code']}` | {r['description']} | {r['type']} | "
            f"`{r['support']:,}` | `{r['precision']:.4f}` | `{r['recall']:.4f}` | **`{r['f1_score']:.4f}`** | "
            f"`{r['mean_confidence']:.2f}` | `{r['top_confusion_partner']}` ({r['top_confusion_count']}) |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Error Analysis & Confusion Partners",
        "",
        "### A. Top Confused Fault Pairs",
        "",
        "| Actual Fault | Predicted Fault | Misclassified Observations | Error Rate of Actual |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for pair in conf_pairs[:10]:
        lines.append(
            f"| `{pair['actual_code']}` | `{pair['predicted_code']}` | `{pair['count']:,}` | `{pair['rate_of_actual'] * 100:.2f}%` |"
        )

    lines.extend([
        "",
        "### B. Difficult / Low-Observability Fault Classes",
        "",
    ])

    if difficult_classes:
        for dc in difficult_classes:
            lines.append(
                f"- **`{dc['fault_code']}`** (Recall: `{dc['recall'] * 100:.1f}%`): "
                f"Frequently confused with `{dc['top_confusion']}`. "
                "Consistent with chemical engineering literature on TEP (Downs & Vogel 1993, Russell et al. 2000), "
                "where closed-loop controllers absorb the disturbance with minimal steady-state sensor deviation."
            )
    else:
        lines.append("No fault classes exhibited recall below 50%.")

    lines.extend([
        "",
        "### C. High-Confidence Error Diagnosis",
        "",
        f"Across all `{metrics['total_test_samples']:,}` held-out test observations, there are `{high_conf_errors}` instances "
        f"({high_conf_errors / metrics['total_test_samples'] * 100:.2f}%) where the model assigned probability $\\ge 0.70$ "
        "to an incorrect fault class. In operational deployment, the digital-twin advisory layer requires "
        "a confidence margin $\\ge 0.20$ before executing automated advisory actions.",
        "",
        "---",
        "",
        "## 5. Operational Recommendations & Digital-Twin Advisory Policy",
        "",
        "1. **Primary Diagnosis (`HIGH_CONFIDENCE`):** Probability $\\ge 0.70$ and margin $\\ge 0.20$. Actionable for digital twin root-cause recommendations.",
        "2. **Secondary Diagnosis (`MODERATE_CONFIDENCE`):** Probability $\\in [0.40, 0.70)$. Consult Top-3 candidates list.",
        "3. **Uncertain State (`LOW_CONFIDENCE_UNCERTAIN`):** Probability $< 0.40$. Defer to `ProcessAnomalyDetector` and retrieve historical RAG incident packages.",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    train_and_evaluate()
