"""
backend/operational_context/models.py — Canonical Operational Case & Context Models for NOVA.

Defines the core data contracts for the NOVA Operational Intelligence Context Layer:
- Observation model (separating measured telemetry from ML predictions)
- Transparent Risk Indicators
- Standardized ML Assessment Summaries with explicit synthetic provenance
- Granular Industrial Evidence categorization
- Canonical OperationalCase combining telemetry, ML, alarms, and multi-domain RAG evidence
- Deterministic Case Status & Priority classifications
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
from pydantic import BaseModel, Field

from backend.knowledge.models import CanonicalEvidence, Citation, EvidenceType


class CaseStatus(str, Enum):
    """Lifecycle states for an OperationalCase."""
    NEW = "NEW"
    ASSESSING = "ASSESSING"
    EVIDENCE_GATHERED = "EVIDENCE_GATHERED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    CLOSED = "CLOSED"


class CasePriority(str, Enum):
    """Deterministic priority classifications based on explicit risk indicators."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ObservationQuality(str, Enum):
    """Quality status of a measured process observation."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    SUBSTITUTED = "SUBSTITUTED"


class Observation(BaseModel):
    """
    Standardized process observation.
    Explicitly represents measured sensor readings separately from ML model assessments.
    """
    tag: str = Field(..., description="Instrument tag or parameter identifier (e.g. TI-201, PI-201)")
    value: float = Field(..., description="Numerical observed value")
    unit: str = Field(..., description="Engineering units (e.g. °C, MPa, kg/h)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of observation",
    )
    quality: ObservationQuality = Field(
        default=ObservationQuality.GOOD,
        description="Data quality indicator",
    )
    description: Optional[str] = Field(default=None, description="Human-readable description of the tag")
    source: str = Field(default="telemetry", description="Source of observation (e.g., telemetry, dcs, synthetic_stream)")
    is_synthetic: bool = Field(default=True, description="True if generated from synthetic/demo stream")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Source provenance metadata")


class RiskIndicator(BaseModel):
    """
    Transparent, interpretable operational risk indicator.
    Contains no opaque or ungrounded failure probabilities.
    """
    name: str = Field(..., description="Name of indicator (e.g. COT_above_threshold, anomaly_detected)")
    value: Any = Field(..., description="Evaluated indicator value (e.g., True, 888.5, 'Fault 4')")
    source: str = Field(..., description="Originating component (e.g. ProcessAnomalyDetector v1.1.0, Telemetry TI-201)")
    severity: CasePriority = Field(default=CasePriority.INFO, description="Severity contribution of this indicator")
    description: str = Field(..., description="Clear explanation of the indicator condition")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Audit trail for this risk indicator")


class MLAssessmentSummary(BaseModel):
    """
    Standardized aggregation summary for an ML model component.
    Preserves model version, evaluation status, and synthetic surrogate notices.
    """
    model_name: str = Field(..., description="Component name (e.g. ProcessAnomalyDetector, TubeTemperaturePredictor)")
    model_version: str = Field(default="v1.1.0", description="Model version string")
    status: str = Field(default="OK", description="Inference status (e.g. OK, MODEL_NOT_AVAILABLE, INFERENCE_ERROR)")
    is_available: bool = Field(default=True, description="True if model artifact was loaded and executed")
    predicted_value: Optional[Any] = Field(default=None, description="Primary predicted output or label")
    confidence: Optional[float] = Field(default=None, description="Model confidence score if supported [0.0, 1.0]")
    score: Optional[float] = Field(default=None, description="Anomaly score or continuous metric")
    target_type: Optional[str] = Field(default=None, description="Target type (e.g. physics_informed_synthetic_surrogate)")
    industrial_validation: bool = Field(default=False, description="Whether target is validated against measured industrial plant data")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Detailed model artifact & training provenance")
    summary: str = Field(default="", description="Human-readable assessment summary")


class EquipmentDetailContext(BaseModel):
    """
    Structured equipment metadata assembled from knowledge base engineering records.
    """
    equipment_id: str = Field(..., description="Target equipment identifier (e.g. F-201A)")
    equipment_type: str = Field(..., description="Equipment classification (e.g. furnace, compressor, pump)")
    unit_area: str = Field(default="UNIT-CRACK-01", description="Plant operating area")
    name: Optional[str] = Field(default=None, description="Formal asset name")
    design_limits: Dict[str, Any] = Field(default_factory=dict, description="Physical and operational design envelopes")
    connected_upstream: List[str] = Field(default_factory=list, description="Direct upstream assets in plant topology")
    connected_downstream: List[str] = Field(default_factory=list, description="Direct downstream assets in plant topology")
    associated_tags: List[str] = Field(default_factory=list, description="Key DCS instrumentation tags")
    relevant_datasheets: List[str] = Field(default_factory=list, description="Referenced engineering datasheet document IDs")


class OperationalCase(BaseModel):
    """
    The canonical Operational Intelligence Case object for NOVA.
    Unifies observations, ML assessments, alarms, multi-domain RAG evidence, equipment context,
    maintenance context, safety context, permit requirements, and incident history into a single
    structured, traceable container for downstream runtime reasoning.
    """
    case_id: str = Field(
        default_factory=lambda: f"CASE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        description="Unique operational case identifier",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC last updated timestamp",
    )
    status: CaseStatus = Field(
        default=CaseStatus.NEW,
        description="Current case lifecycle state",
    )
    priority: CasePriority = Field(
        default=CasePriority.INFO,
        description="Evaluated case priority",
    )
    equipment_id: str = Field(..., description="Primary asset ID (e.g. F-201A)")
    equipment_type: str = Field(default="furnace", description="Primary asset type")
    unit_area: str = Field(default="UNIT-CRACK-01", description="Plant area")
    title: str = Field(default="", description="Summary title of the operational case")
    summary: str = Field(default="", description="High-level operational situation summary")
    overall_state: str = Field(default="NORMAL", description="Overall operating regime / state descriptor")

    # 1. Process Observations (Measured Telemetry)
    observations: List[Observation] = Field(
        default_factory=list,
        description="List of measured process parameter observations",
    )

    # 2. Alarms & Events
    alarms: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Active or associated alarm records",
    )

    # 3. Machine Learning Assessments (4 Standardized Models)
    ml_assessments: Dict[str, MLAssessmentSummary] = Field(
        default_factory=dict,
        description="Standardized ML model assessments keyed by model component",
    )

    # 4. Multi-Domain RAG Evidence Categorization
    knowledge_evidence: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Authoritative SOP and engineering document evidence",
    )
    maintenance_context: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Maintenance history, inspection records, and work order evidence",
    )
    safety_context: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Process safety standards, PPE matrices, and hazard controls",
    )
    permit_context: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Applicable permit-to-work requirements and isolation rules",
    )
    incident_context: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Historical incident retrospectives and near-miss logs",
    )

    # 5. Plant Topology & Equipment Detail
    equipment_context: Optional[EquipmentDetailContext] = Field(
        default=None,
        description="Static equipment metadata, topology, and design limits",
    )

    # 6. Interpretable Risk Indicators
    risk_indicators: List[RiskIndicator] = Field(
        default_factory=list,
        description="Explicit, traceable risk indicator evaluations",
    )

    # 7. Audit Provenance & Operational Limitations
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="End-to-end case audit trail and source lineages",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Explicit operational caveats, synthetic surrogate notices, and boundaries",
    )
    scenario_type: Optional[str] = Field(
        default="synthetic_demo",
        description="Scenario provenance classification (e.g. synthetic_demo)",
    )
