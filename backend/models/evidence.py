"""Evidence and historical-match models used by the Risk Reasoner and
the retrieval pipeline (§11.2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel



class EvidenceItem(BaseModel):
    """A single piece of grounded evidence supporting a risk assessment."""

    source: str
    fact: str
    raw_value: Any
    ts: datetime
    weight: float


class HistoricalMatch(BaseModel):
    """A past incident / near-miss retrieved from Qdrant and (optionally)
    re-ranked by the cross-encoder."""

    record_id: str
    collection: str
    similarity_score: float
    rerank_score: float | None
    title: str
    date: datetime
    matched_on: list[str]


class EvidencePackage(BaseModel):
    """
    Structured evidence container sitting between telemetry/retrieval and LLM reasoning.
    Supplies comprehensive, grounded multi-source operational context without redundant DB roundtrips.
    """

    package_id: str
    timestamp: datetime
    plant_id: str = "PLANT-ETH-01"
    unit_id: str = "UNIT-CRACK-01"
    asset_id: str = ""
    plant_state: dict[str, Any] | None = None
    ml_assessments: dict[str, Any] = {}
    risk_assessment: dict[str, Any] | None = None
    active_alarms: list[dict[str, Any]] = []
    maintenance_records: list[dict[str, Any]] = []
    permits: list[dict[str, Any]] = []
    occupancy: dict[str, Any] | None = None
    historical_matches: list[HistoricalMatch] = []
    engineering_knowledge: list[dict[str, Any]] = []
    evidence_items: list[EvidenceItem] = []
    provenance: dict[str, Any] = {}


def __getattr__(name: str):
    if name in ("CanonicalEvidence", "Citation", "EvidenceType"):
        from backend.knowledge.models import (
            CanonicalEvidence,
            Citation,
            EvidenceType,
        )
        globals()["CanonicalEvidence"] = CanonicalEvidence
        globals()["Citation"] = Citation
        globals()["EvidenceType"] = EvidenceType
        return globals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

