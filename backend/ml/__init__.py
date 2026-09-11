"""
backend/ml — Industrial ML Model Architecture & Interface Contracts.

Modules:
- anomaly: Process anomaly detection interfaces (PCA + Isolation Forest)
- fault: Process fault diagnosis interfaces (XGBoost Multiclass Classifier on TEP)
- furnace: Furnace COT & Tube Temperature prediction interfaces
- inference: Unified ML inference pipeline with graceful fallbacks
"""
from __future__ import annotations
