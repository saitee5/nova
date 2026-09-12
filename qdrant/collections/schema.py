"""Qdrant collection definitions for VIGIL.

Eight logical collections matching §6 / §11.3 of the master document.
All use BAAI/bge-small-en-v1.5 embeddings: size=384, distance=Cosine.

Each collection has a TypedDict describing its payload schema and a
``COLLECTION_CONFIGS`` dict consumed by QdrantMemoryClient.ensure_collections().
"""

from __future__ import annotations

from typing import Literal, TypedDict

# ------------------------------------------------------------------
# Vector constants (bge-small-en-v1.5)
# ------------------------------------------------------------------

VECTOR_SIZE: int = 384
DISTANCE: str = "Cosine"


# ------------------------------------------------------------------
# Payload schemas (one TypedDict per collection)
# ------------------------------------------------------------------

class IncidentPayload(TypedDict):
    """Payload for ``incidents_historical`` and ``near_misses``."""

    equipment_id: str
    equipment_class: str
    zone_id: str
    date: str  # ISO-8601
    severity: Literal["near_miss", "minor", "major", "fatal"]
    contributing_factors: list[str]
    verified: bool
    superseded_by: str | None
    text_summary: str  # embedded field


class MaintenanceHistoryPayload(TypedDict):
    """Payload for ``maintenance_history``."""

    equipment_id: str
    date: str  # ISO-8601
    fault_type: str
    text_summary: str  # embedded field


class SafetyProcedurePayload(TypedDict):
    """Payload for ``safety_procedures``."""

    regulation_id: str
    topic: str
    text_summary: str  # embedded field


class EquipmentContextPayload(TypedDict):
    """Payload for ``equipment_context``."""

    equipment_id: str
    equipment_class: str
    criticality: str
    zone_id: str
    text_summary: str  # embedded field


class RiskPatternPayload(TypedDict):
    """Payload for ``risk_patterns``."""

    pattern_type: str
    zone_id: str
    equipment_class: str
    text_summary: str  # embedded field


class LessonLearnedPayload(TypedDict):
    """Payload for ``lessons_learned``."""

    incident_id: str
    equipment_id: str
    zone_id: str
    verified: bool
    contributing_factors: list[str]
    debrief_text: str  # embedded field
    created_at: str  # ISO-8601


class ActiveCaseMemoryPayload(TypedDict):
    """Payload for ``active_case_memory``."""

    session_id: str
    case_id: str
    status: str
    ttl_expires_at: str  # ISO-8601


# ------------------------------------------------------------------
# Collection configs — consumed by QdrantMemoryClient.ensure_collections()
# ------------------------------------------------------------------

# Maps collection name -> (vector_size, distance_metric, payload_schema_class,
#                           name of the payload field that gets embedded)
COLLECTION_CONFIGS: dict[str, dict] = {
    "incidents_historical": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": IncidentPayload,
        "embed_field": "text_summary",
    },
    "near_misses": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": IncidentPayload,  # same shape
        "embed_field": "text_summary",
    },
    "maintenance_history": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": MaintenanceHistoryPayload,
        "embed_field": "text_summary",
    },
    "safety_procedures": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": SafetyProcedurePayload,
        "embed_field": "text_summary",
    },
    "equipment_context": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": EquipmentContextPayload,
        "embed_field": "text_summary",
    },
    "risk_patterns": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": RiskPatternPayload,
        "embed_field": "text_summary",
    },
    "lessons_learned": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": LessonLearnedPayload,
        "embed_field": "debrief_text",
    },
    "active_case_memory": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": ActiveCaseMemoryPayload,
        "embed_field": "status",  # minimal; primarily payload-filtered
    },
    # NOVA Canonical Semantic Memory Collections
    "nova_operational_memory": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": dict,
        "embed_field": "text_summary",
    },
    "nova_engineering_knowledge": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": dict,
        "embed_field": "text_summary",
    },
    "nova_industry_cases": {
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "payload_schema": dict,
        "embed_field": "text_summary",
    },
}

ALL_COLLECTION_NAMES: list[str] = list(COLLECTION_CONFIGS.keys())

