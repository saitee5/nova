"""
backend/knowledge/evidence_bridge.py — Model Evidence Bridge & Evidence Adapters.

Converts ML model predictions and document retrieval results into canonical
Evidence objects (DOCUMENT_EVIDENCE and MODEL_EVIDENCE) for downstream reasoning.
Strictly preserves synthetic surrogate provenance for TubeTemperaturePredictor.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from backend.knowledge.models import (
    CanonicalEvidence,
    Citation,
    EvidenceType,
    RetrievalResult,
    RetrievedChunk,
)

logger = logging.getLogger("nova.knowledge.evidence_bridge")


class ModelEvidenceBridge:
    """
    Adapter converting ML model outputs and document retrieval results into
    standardized CanonicalEvidence objects.
    """

    @staticmethod
    def infer_evidence_type(chunk: RetrievedChunk) -> EvidenceType:
        """Infer granular industrial evidence type from chunk metadata and document type."""
        doc_type = str(chunk.metadata.get("document_type", "")).lower()
        doc_id = str(chunk.document_id).upper()
        if "PMT" in doc_id or "PERMIT" in doc_id or "permit" in doc_type:
            return EvidenceType.PERMIT_EVIDENCE
        if doc_type in ("safety_procedure", "emergency_procedure") or "SAF" in doc_id or "EMG" in doc_id:
            return EvidenceType.SAFETY_EVIDENCE
        if doc_type in ("maintenance_manual", "inspection_report", "work_order") or "MNT" in doc_id:
            return EvidenceType.MAINTENANCE_EVIDENCE
        if doc_type in ("incident_report", "near_miss") or "INC" in doc_id:
            return EvidenceType.INCIDENT_EVIDENCE
        if doc_type in ("equipment_datasheet", "p&id", "pid") or "DAT" in doc_id or "PID" in doc_id or "HRC" in doc_id:
            return EvidenceType.EQUIPMENT_EVIDENCE
        return EvidenceType.DOCUMENT_EVIDENCE

    @staticmethod
    def from_retrieved_chunk(
        chunk: RetrievedChunk,
        categorize: bool = False,
        override_type: Optional[EvidenceType] = None,
    ) -> CanonicalEvidence:
        """Convert a single retrieved document chunk into CanonicalEvidence."""
        evidence_id = f"ev_doc_{chunk.chunk_id}_{uuid.uuid4().hex[:8]}"
        ev_type = override_type or (
            ModelEvidenceBridge.infer_evidence_type(chunk)
            if categorize
            else EvidenceType.DOCUMENT_EVIDENCE
        )
        return CanonicalEvidence(
            evidence_id=evidence_id,
            evidence_type=ev_type,
            source_type=chunk.metadata.get("document_type", "document"),
            source_id=chunk.document_id,
            source_title=chunk.document_title,
            excerpt=chunk.text,
            relevance_score=chunk.score,
            timestamp=datetime.now(timezone.utc).isoformat(),
            provenance={
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "rank": chunk.rank,
                "section": chunk.section,
                "is_synthetic_demo": chunk.metadata.get("is_synthetic_demo", True),
                "authority": chunk.metadata.get("authority", "demo_only"),
                "industrial_validation": chunk.metadata.get("industrial_validation", False),
            },
            model_version=chunk.metadata.get("version"),
            metadata=chunk.metadata,
            citation=chunk.citation,
        )

    @staticmethod
    def from_retrieval_result(
        result: RetrievalResult,
        categorize: bool = False,
    ) -> List[CanonicalEvidence]:
        """Convert all retrieved chunks in a RetrievalResult into a list of CanonicalEvidence."""
        return [
            ModelEvidenceBridge.from_retrieved_chunk(chunk, categorize=categorize)
            for chunk in result.results
        ]


    @staticmethod
    def from_anomaly_prediction(
        prediction: Dict[str, Any],
        model_version: str = "v1.1.0",
    ) -> CanonicalEvidence:
        """Convert ProcessAnomalyDetector output into MODEL_EVIDENCE."""
        is_anomaly = bool(prediction.get("is_anomaly", False))
        score = float(prediction.get("anomaly_score", 0.0))
        status = str(prediction.get("status", "OK"))
        threshold = prediction.get("threshold", 0.5)

        excerpt = (
            f"ProcessAnomalyDetector {model_version}: "
            f"Anomaly detected={is_anomaly} (score={score:.4f}, threshold={threshold}). Status={status}."
        )

        return CanonicalEvidence(
            evidence_id=f"ev_mod_anomaly_{uuid.uuid4().hex[:8]}",
            evidence_type=EvidenceType.MODEL_EVIDENCE,
            source_type="ml_anomaly_detector",
            source_id="ProcessAnomalyDetector",
            source_title="Process Anomaly Detector (PCA + ExtraTrees / IsolationForest)",
            excerpt=excerpt,
            relevance_score=score if is_anomaly else (1.0 - score),
            timestamp=datetime.now(timezone.utc).isoformat(),
            provenance={
                "model_name": "ProcessAnomalyDetector",
                "model_version": model_version,
                "dataset": "TEP Canonical (Curated)",
                "status": "VALIDATED_WITH_LIMITATIONS",
                "evaluation_status": "VALIDATED_WITH_LIMITATIONS",
            },
            model_version=model_version,
            metadata=prediction,
            citation=None,
        )

    @staticmethod
    def from_fault_prediction(
        prediction: Dict[str, Any],
        model_version: str = "v1.1.0",
    ) -> CanonicalEvidence:
        """Convert ProcessFaultClassifier output into MODEL_EVIDENCE."""
        predicted_fault = prediction.get("predicted_fault")
        fault_name = prediction.get("fault_name", f"Fault {predicted_fault}")
        confidence = float(prediction.get("confidence", 0.0))
        status = str(prediction.get("status", "OK"))

        excerpt = (
            f"ProcessFaultClassifier {model_version}: "
            f"Predicted fault={predicted_fault} ({fault_name}) with confidence {confidence:.2%}. Status={status}."
        )

        return CanonicalEvidence(
            evidence_id=f"ev_mod_fault_{uuid.uuid4().hex[:8]}",
            evidence_type=EvidenceType.MODEL_EVIDENCE,
            source_type="ml_fault_classifier",
            source_id="ProcessFaultClassifier",
            source_title="Process Fault Classifier (LightGBM 21-Class Classifier)",
            excerpt=excerpt,
            relevance_score=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            provenance={
                "model_name": "ProcessFaultClassifier",
                "model_version": model_version,
                "dataset": "TEP Canonical (Curated)",
                "status": "VALIDATED_WITH_LIMITATIONS",
                "evaluation_status": "VALIDATED_WITH_LIMITATIONS",
            },
            model_version=model_version,
            metadata=prediction,
            citation=None,
        )

    @staticmethod
    def from_cot_prediction(
        prediction: Dict[str, Any],
        model_version: str = "v1.1.0",
    ) -> CanonicalEvidence:
        """Convert FurnaceCOTPredictor output into MODEL_EVIDENCE."""
        predicted_cot = prediction.get("predicted_cot") or prediction.get("prediction")
        confidence = float(prediction.get("confidence", 0.95))
        status = str(prediction.get("status", "OK"))

        excerpt = (
            f"FurnaceCOTPredictor {model_version}: "
            f"Predicted Coil Outlet Temperature (COT)={predicted_cot} °C. Status={status}."
        )

        return CanonicalEvidence(
            evidence_id=f"ev_mod_cot_{uuid.uuid4().hex[:8]}",
            evidence_type=EvidenceType.MODEL_EVIDENCE,
            source_type="ml_regression_soft_sensor",
            source_id="FurnaceCOTPredictor",
            source_title="Furnace COT Predictor (Gradient Boosting Regression)",
            excerpt=excerpt,
            relevance_score=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            provenance={
                "model_name": "FurnaceCOTPredictor",
                "model_version": model_version,
                "dataset": "Furnace COT Canonical (Curated)",
                "status": "VALIDATED_WITH_LIMITATIONS",
                "evaluation_status": "VALIDATED_WITH_LIMITATIONS",
            },
            model_version=model_version,
            metadata=prediction,
            citation=None,
        )

    @staticmethod
    def from_tube_temp_prediction(
        prediction: Dict[str, Any],
        model_version: str = "v1.1.0",
    ) -> CanonicalEvidence:
        """
        Convert TubeTemperaturePredictor output into MODEL_EVIDENCE.

        IMPORTANT: Explicitly marks and preserves synthetic surrogate provenance:
        - target_type = 'physics_informed_synthetic_surrogate'
        - industrial_validation = False
        - Transparent limitation notice
        """
        predicted_tmt = prediction.get("predicted_tmt") or prediction.get("prediction")
        confidence = float(prediction.get("confidence", 0.85))
        status = str(prediction.get("status", "OK"))

        excerpt = (
            f"TubeTemperaturePredictor {model_version} [SYNTHETIC SURROGATE]: "
            f"Estimated Tube Metal Temperature (TMT)={predicted_tmt} °C. "
            f"Notice: Physics-informed statistical surrogate; NOT measured industrial telemetry. "
            f"Status={status}."
        )

        return CanonicalEvidence(
            evidence_id=f"ev_mod_tmt_{uuid.uuid4().hex[:8]}",
            evidence_type=EvidenceType.MODEL_EVIDENCE,
            source_type="ml_synthetic_surrogate",
            source_id="TubeTemperaturePredictor",
            source_title="Tube Metal Temperature Predictor (Physics-Informed Synthetic Surrogate)",
            excerpt=excerpt,
            relevance_score=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            provenance={
                "model_name": "TubeTemperaturePredictor",
                "model_version": model_version,
                "dataset": "Tube Temperature Canonical (Curated)",
                "target_type": "physics_informed_synthetic_surrogate",
                "industrial_validation": False,
                "evaluation_status": "DEMO_VALIDATED_WITH_LIMITATIONS",
                "limitation_notice": "Target is generated via physics-informed formula; not equivalent to direct thermal thermocouple measurements.",
            },
            model_version=model_version,
            metadata={
                **prediction,
                "target_type": "physics_informed_synthetic_surrogate",
                "industrial_validation": False,
            },
            citation=None,
        )
