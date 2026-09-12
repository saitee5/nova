"""
backend/services/providers — Provider interface contracts for the intelligence layer.

These abstract base classes define the data access boundary between the
intelligence services (Context, Risk, Episode, Agents) and any underlying
infrastructure (in-memory, PostgreSQL, MQTT, OPC-UA, RAG, Knowledge Graph).

Arushi's implementations (PostgreSQL, RAG, Knowledge Graph) will satisfy
these interfaces without requiring changes to the intelligence layer.
"""
from __future__ import annotations

from backend.services.providers.interfaces import (
    AlarmProvider,
    AssetProvider,
    HistoricalEpisodeProvider,
    KnowledgeProvider,
    MaintenanceProvider,
    OperationsProvider,
    PermitProvider,
    TelemetryProvider,
)
from backend.services.providers.default_providers import (
    PlantStateTelemetryProvider,
    PlantStateAlarmProvider,
    PlantStateAssetProvider,
    PlantStateMaintenanceProvider,
    PlantStatePermitProvider,
    PlantStateOperationsProvider,
    InMemoryHistoricalEpisodeProvider,
    StubKnowledgeProvider,
)

__all__ = [
    # Interfaces
    "TelemetryProvider",
    "AlarmProvider",
    "AssetProvider",
    "MaintenanceProvider",
    "PermitProvider",
    "OperationsProvider",
    "HistoricalEpisodeProvider",
    "KnowledgeProvider",
    # Default/test implementations
    "PlantStateTelemetryProvider",
    "PlantStateAlarmProvider",
    "PlantStateAssetProvider",
    "PlantStateMaintenanceProvider",
    "PlantStatePermitProvider",
    "PlantStateOperationsProvider",
    "InMemoryHistoricalEpisodeProvider",
    "StubKnowledgeProvider",
    "RAGKnowledgeProvider",
]


def __getattr__(name: str):
    if name == "RAGKnowledgeProvider":
        from backend.knowledge.provider import RAGKnowledgeProvider
        return RAGKnowledgeProvider
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
