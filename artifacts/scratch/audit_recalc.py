import joblib, json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import numpy as np
from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)

from ml_training.tep.train_anomaly_detector import (
    load_tep_anomaly_splits,
    CURATED_TEP_PATH,
    CANONICAL_FEATURES,
    compute_pca_statistics,
    FAULT_DESCRIPTIONS,
)

# 1. Load saved model artifact
model_path = Path("artifacts/models/process_anomaly_detector/v1.1.0/model.joblib")
artifact = joblib.load(model_path)
preprocessor = artifact["preprocessor"]
pca = artifact["pca"]
iso_forest = artifact["isolation_forest"]
q_threshold = artifact["pca_config"]["q_threshold"]
t2_threshold = artifact["pca_config"]["t2_threshold"]
if_threshold = artifact["if_config"]["threshold"]
df_std = artifact["if_config"]["df_std"]
combined_threshold = artifact["scoring"]["combined_threshold"]
uncertain_lower = artifact["scoring"]["uncertain_lower_threshold"]
uncertain_upper = artifact["scoring"]["uncertain_upper_threshold"]

print("=== Artifact Parameters ===")
print(f"PCA components: {pca.n_components_}")
print(f"PCA Q-threshold: {q_threshold:.4f}")
print(f"PCA T2-threshold: {t2_threshold:.4f}")
print(f"IF threshold: {if_threshold:.6f}")
print(f"IF df_std: {df_std:.6f}")
print(f"Combined threshold: {combined_threshold}")
print(f"Uncertainty range: [{uncertain_lower}, {uncertain_upper})")

# 2. Score helper
def score_matrix(X_mat: np.ndarray):
    Z_mat = preprocessor.transform(X_mat)
    Q_m, T2_m = compute_pca_statistics(Z_mat, pca)
    r_pca_m = np.maximum(Q_m / q_threshold, T2_m / t2_threshold)
    s_pca_m = 1.0 - np.power(0.5, r_pca_m)

    df_m = iso_forest.decision_function(Z_mat)
    s_if_m = 1.0 / (1.0 + np.exp(10.0 * (df_m - if_threshold) / df_std))

    s_comb_m = 0.50 * s_pca_m + 0.50 * s_if_m
    return s_comb_m, s_pca_m, s_if_m, Z_mat

# 3. Load splits
print("\nLoading test splits from curated TEP dataset...")
splits = load_tep_anomaly_splits(CURATED_TEP_PATH, 400, 100, 50, 5)
df_test_normal = splits["test_normal"]
test_faults_dict = splits["test_faults"]

# 4. Score normal test set
s_norm, _, _, _ = score_matrix(df_test_normal[CANONICAL_FEATURES].values)
y_pred_normal = (s_norm >= combined_threshold).astype(int)
fp_normal = int(np.sum(y_pred_normal == 1))
tn_normal = int(np.sum(y_pred_normal == 0))
fpr_normal = fp_normal / len(s_norm)
spec_normal = tn_normal / len(s_norm)
print(f"\n--- PURE NORMAL TEST SET (50 runs, N={len(s_norm)}) ---")
print(f"TN: {tn_normal}")
print(f"FP: {fp_normal}")
print(f"FPR: {fpr_normal:.6f} ({fpr_normal * 100:.4f}%)")
print(f"Specificity: {spec_normal:.6f} ({spec_normal * 100:.4f}%)")

# 5. Faults
all_records = []
all_y_true = [np.zeros(len(s_norm), dtype=int)]
all_y_pred = [y_pred_normal]
all_scores = [s_norm]

norm_rec = pd.DataFrame({
    "scenario": "NORMAL_TEST",
    "fault_id": 0,
    "sample_index": df_test_normal["sample_index"].values,
    "actual_label": 0,
    "anomaly_score": np.round(s_norm, 4),
    "predicted_anomaly": y_pred_normal,
})
all_records.append(norm_rec)

per_fault_metrics = []
pre_fp_total = 0
pre_total = 0

for f_id in range(1, 21):
    df_f = test_faults_dict[f_id]
    s_f, _, _, _ = score_matrix(df_f[CANONICAL_FEATURES].values)
    y_true_f = np.where(df_f["sample_index"].values > 160, 1, 0)
    y_pred_f = (s_f >= combined_threshold).astype(int)

    all_y_true.append(y_true_f)
    all_y_pred.append(y_pred_f)
    all_scores.append(s_f)

    f_rec = pd.DataFrame({
        "scenario": f"FAULT_{f_id:02d}",
        "fault_id": f_id,
        "sample_index": df_f["sample_index"].values,
        "actual_label": y_true_f,
        "anomaly_score": np.round(s_f, 4),
        "predicted_anomaly": y_pred_f,
    })
    all_records.append(f_rec)

    active_mask = df_f["sample_index"].values > 160
    pre_mask = df_f["sample_index"].values <= 160
    n_active = int(np.sum(active_mask))
    n_detected = int(np.sum(y_pred_f[active_mask] == 1))
    detection_rate = float(n_detected / max(1, n_active))

    pre_fps = int(np.sum(y_pred_f[pre_mask] == 1))
    pre_fp_total += pre_fps
    pre_total += int(np.sum(pre_mask))
    far_pre = float(pre_fps / max(1, np.sum(pre_mask)))

    delays_samples = []
    for run_id, grp in df_f.groupby("simulation_run"):
        post_grp = grp[grp["sample_index"] > 160]
        grp_scores, _, _, _ = score_matrix(post_grp[CANONICAL_FEATURES].values)
        det_idx = np.where(grp_scores >= combined_threshold)[0]
        if len(det_idx) > 0:
            delays_samples.append(int(det_idx[0]))
        else:
            delays_samples.append(len(post_grp))
    mean_delay_samples = float(np.mean(delays_samples))
    mean_delay_minutes = mean_delay_samples * 3.0

    if detection_rate >= 0.85 and mean_delay_minutes <= 60.0:
        observability = "RELIABLY_DETECTABLE"
    elif detection_rate >= 0.50:
        observability = "WEAKLY_DETECTABLE"
    else:
        observability = "DIFFICULT_UNOBSERVABLE"

    per_fault_metrics.append({
        "fault_id": f_id,
        "fault_code": FAULT_DESCRIPTIONS.get(f_id, {}).get("code", f"IDV({f_id})"),
        "description": FAULT_DESCRIPTIONS.get(f_id, {}).get("description", f"Fault {f_id}"),
        "total_samples": len(df_f),
        "active_fault_samples": n_active,
        "detected_samples": n_detected,
        "detection_rate": round(detection_rate, 4),
        "false_alarm_rate_pre_injection": round(far_pre, 4),
        "mean_detection_delay_samples": round(mean_delay_samples, 2),
        "mean_detection_delay_minutes": round(mean_delay_minutes, 2),
        "observability_classification": observability,
        "pre_fps": pre_fps,
    })

print(f"\n--- PRE-INJECTION PERIODS IN FAULT RUNS (100 runs, N={pre_total}) ---")
print(f"Pre-injection FP: {pre_fp_total}")
print(f"Pre-injection TN: {pre_total - pre_fp_total}")
print(f"Pre-injection FAR: {pre_fp_total / pre_total:.6f} ({pre_fp_total / pre_total * 100:.4f}%)")

# Full test set
full_y_true = np.concatenate(all_y_true)
full_y_pred = np.concatenate(all_y_pred)
full_scores = np.concatenate(all_scores)

cm = confusion_matrix(full_y_true, full_y_pred)
tn, fp, fn, tp = cm.ravel()
print(f"\n--- FULL TEST SET (N={len(full_y_true)}) ---")
print(f"Confusion Matrix:\n{cm}")
print(f"TN: {tn}")
print(f"FP: {fp} (sum of pure normal FP {fp_normal} + pre-injection FP {pre_fp_total} = {fp_normal + pre_fp_total})")
print(f"FN: {fn}")
print(f"TP: {tp}")
print(f"Total Normal (TN + FP): {tn + fp} (48,000 pure normal + 16,000 pre-injection)")
print(f"Total Anomalous (FN + TP): {fn + tp} (34,000 active fault)")
full_fpr = fp / (fp + tn)
full_spec = tn / (fp + tn)
prec = precision_score(full_y_true, full_y_pred)
rec = recall_score(full_y_true, full_y_pred)
f1 = f1_score(full_y_true, full_y_pred)
pr_auc = average_precision_score(full_y_true, full_scores)
roc_auc = roc_auc_score(full_y_true, full_scores)
uncertain_count = int(np.sum((full_scores >= uncertain_lower) & (full_scores < uncertain_upper)))
uncertain_rate = uncertain_count / len(full_scores)

print(f"Full-set FPR: {full_fpr:.6f} ({full_fpr * 100:.4f}%)")
print(f"Full-set Specificity: {full_spec:.6f} ({full_spec * 100:.4f}%)")
print(f"Precision: {prec:.6f}")
print(f"Recall: {rec:.6f}")
print(f"F1 Score: {f1:.6f}")
print(f"PR-AUC: {pr_auc:.6f}")
print(f"ROC-AUC: {roc_auc:.6f}")
print(f"Uncertainty Rate: {uncertain_rate:.6f} ({uncertain_rate * 100:.4f}%)")

print("\n--- PER-FAULT METRICS CHECK ---")
pf_saved = pd.read_csv("artifacts/evaluation/process_anomaly_detector/v1.1.0/per_fault_metrics.csv")
all_match = True
for idx, r in pf_saved.iterrows():
    c = per_fault_metrics[idx]
    match = (
        r["detection_rate"] == c["detection_rate"]
        and r["mean_detection_delay_minutes"] == c["mean_detection_delay_minutes"]
        and r["false_alarm_rate_pre_injection"] == c["false_alarm_rate_pre_injection"]
    )
    if not match:
        all_match = False
        print(f"MISMATCH for Fault {r['fault_id']}: saved={dict(r)}, recomputed={c}")
if all_match:
    print("All 20 fault metrics match per_fault_metrics.csv perfectly!")

# Save full predictions to scratch for verification
all_full_df = pd.concat(all_records, ignore_index=True)
print(f"\nTotal full predictions generated: {len(all_full_df)}")
all_full_df.to_parquet("artifacts/scratch/full_test_predictions.parquet", index=False)
