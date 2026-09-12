"""
backend/services/context_engine.py — Operational Context Engine.

The Context Engine is the intelligence layer's primary data assembly hub.
It aggregates:
  1. Live telemetry (from TelemetryProvider)
  2. ML Evidence (from MLRuntime)
  3. Alarm state (from AlarmProvider)
  4. Equipment and asset metadata (from AssetProvider)
  5. Maintenance / Permit state (from Maintenance/PermitProvider)
  6. Operating mode (from OperationsProvider)
  7. Historical similar episodes (from HistoricalEpisodeProvider)
  8. Engineering knowledge (from KnowledgeProvider)

And assembles them into an OperationalContextSnapshot — a rich, typed,
provenance-tracked context object consumed by:
  - IndustrialRiskEngine
  - OperationalEpisodeEngine
  - NovaAgents

Provenance contract:
  Every field in the snapshot carries a DataProvenance tag:
    OBSERVED   = live sensor reading
    PREDICTED  = ML model output
    DERIVED    = computed from other fields
    MISSING    = data not available (not fabricated)
    STALE      = data older than staleness threshold
    UNKNOWN    = provenance cannot be determined

Zero-Actuation Rule:
  The Context Engine is read-only. It never issues commands.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.ml.runtime.contracts import MLEvidence, MLEvidenceStatus, MLPredictionType
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

logger = logging.getLogger("nova.context_engine")

# Staleness threshold for live telemetry (seconds)
TELEMETRY_STALE_THRESHOLD_S: float = 120.0


# ---------------------------------------------------------------------------
# Provenance Enumeration
# ---------------------------------------------------------------------------

class DataProvenance(str, Enum):
    """
    Data provenance tags for all context fields.
    Tracks how each data point was obtained.
    """
    OBSERVED = "OBSERVED"       # Live sensor / DCS reading
    PREDICTED = "PREDICTED"     # ML model output
    DERIVED = "DERIVED"         # Calculated from other fields
    MISSING = "MISSING"         # Data not available — NOT fabricated
    STALE = "STALE"             # Reading older than staleness threshold
    UNKNOWN = "UNKNOWN"         # Provenance cannot be determined


# ---------------------------------------------------------------------------
# Typed context field
# ---------------------------------------------------------------------------

class ContextField(BaseModel):
    """A typed context value with its provenance label."""
    value: Optional[Any]
    provenance: DataProvenance
    unit: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# ML Summary embedded in context
# ---------------------------------------------------------------------------

class MLContextSummary(BaseModel):
    """Compressed ML evidence summary for the context snapshot."""
    anomaly_detected: ContextField
    anomaly_score: ContextField
    predicted_fault: ContextField
    fault_confidence: ContextField
    predicted_cot: ContextField
    predicted_tube_temperature: ContextField
    model_versions: Dict[str, str] = Field(default_factory=dict)
    evidence_records: List[MLEvidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Operational Context Snapshot
# ---------------------------------------------------------------------------

class OperationalContextSnapshot(BaseModel):
    """
    The canonical, fully-assembled operational context for one asset.
    This is the complete intelligence picture consumed by Risk, Episode, and Agents.

    All fields carry DataProvenance tags. Unavailable fields are MISSING (never fabricated).
    """
    model_config = {"arbitrary_types_allowed": True}

    # Identity
    asset_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context_id: str = Field(default="")

    # Telemetry
    telemetry: Dict[str, ContextField] = Field(default_factory=dict)
    sensor_health: Dict[str, str] = Field(default_factory=dict)

    # ML Evidence
    ml_summary: Optional[MLContextSummary] = None
    ml_evidence: List[MLEvidence] = Field(default_factory=list)

    # Alarm State
    active_alarms: List[Dict[str, Any]] = Field(default_factory=list)
    highest_alarm_severity: ContextField = Field(
        default_factory=lambda: ContextField(value=None, provenance=DataProvenance.MISSING)
    )

    # Asset / Equipment
    asset_metadata: Optional[Dict[str, Any]] = None
    equipment_status: ContextField = Field(
        default_factory=lambda: ContextField(value="UNKNOWN", provenance=DataProvenance.MISSING)
    )
    asset_criticality: ContextField = Field(
        default_factory=lambda: ContextField(value="MEDIUM", provenance=DataProvenance.MISSING)
    )

    # Maintenance / Permit
    active_maintenance: List[Dict[str, Any]] = Field(default_factory=list)
    active_permits: List[Dict[str, Any]] = Field(default_factory=list)
    is_simops: ContextField = Field(
        default_factory=lambda: ContextField(value=False, provenance=DataProvenance.DERIVED)
    )

    # Operating Context
    operating_mode: ContextField = Field(
        default_factory=lambda: ContextField(value="UNKNOWN", provenance=DataProvenance.MISSING)
    )
    personnel_count: ContextField = Field(
        default_factory=lambda: ContextField(value=0, provenance=DataProvenance.MISSING)
    )

    # Historical / Knowledge
    similar_episodes: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_references: List[Dict[str, Any]] = Field(default_factory=list)

    # Assembly metadata
    assembly_duration_ms: float = 0.0
    providers_used: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.context_id:
            import uuid
            self.context_id = f"ctx_{uuid.uuid4().hex[:12]}"

    @property
    def anomaly_score(self) -> Optional[float]:
        """Convenience accessor for ML anomaly score."""
        if self.ml_summary:
            return self.ml_summary.anomaly_score.value
        return None

    @property
    def is_anomaly(self) -> bool:
        """True when ML detects anomaly and confidence is GOOD."""
        if self.ml_summary:
            v = self.ml_summary.anomaly_detected.value
            return bool(v) and self.ml_summary.anomaly_detected.provenance != DataProvenance.MISSING
        return False

    @property
    def equipment_condition_score(self) -> float:
        """
        Numeric equipment condition score [0.0, 1.0] derived from status and ML evidence.
        Used by the Risk Engine.
        """
        status = (self.equipment_status.value or "UNKNOWN").upper()
        base = {
            "HEALTHY": 0.1,
            "OPERATIONAL": 0.2,
            "WARNING": 0.4,
            "DEGRADED": 0.6,
            "FAULT": 0.8,
            "UNKNOWN": 0.3,
        }.get(status, 0.3)

        # Boost if anomaly detected
        if self.is_anomaly and self.anomaly_score is not None:
            base = max(base, float(self.anomaly_score))

        return min(base, 1.0)


# ---------------------------------------------------------------------------
# Context Engine
# ---------------------------------------------------------------------------

class ContextEngine:
    """
    Operational Context Engine.

    Assembles a complete OperationalContextSnapshot for a given asset
    by orchestrating all registered providers and the ML runtime.

    Usage:
        engine = ContextEngine(
            telemetry_provider=...,
            alarm_provider=...,
            asset_provider=...,
            ...
            ml_runtime=...,
        )
        ctx = engine.assemble(asset_id="F-201A")
        # ctx is now ready for Risk Engine / Episode Engine / Agents

    All providers are optional. Missing providers produce MISSING-provenance fields.
    The engine never fabricates data — MISSING is explicit.
    """

    def __init__(
        self,
        telemetry_provider: Optional[TelemetryProvider] = None,
        alarm_provider: Optional[AlarmProvider] = None,
        asset_provider: Optional[AssetProvider] = None,
        maintenance_provider: Optional[MaintenanceProvider] = None,
        permit_provider: Optional[PermitProvider] = None,
        operations_provider: Optional[OperationsProvider] = None,
        historical_provider: Optional[HistoricalEpisodeProvider] = None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        ml_runtime=None,
        staleness_threshold_s: float = TELEMETRY_STALE_THRESHOLD_S,
    ) -> None:
        self._tel = telemetry_provider
        self._alm = alarm_provider
        self._ast = asset_provider
        self._mnt = maintenance_provider
        self._prm = permit_provider
        self._ops = operations_provider
        self._hist = historical_provider
        self._know = knowledge_provider
        self._ml = ml_runtime
        self._staleness_s = staleness_threshold_s

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def assemble(
        self,
        asset_id: str,
        telemetry_override: Optional[Dict[str, Any]] = None,
        query_hint: Optional[str] = None,
        include_knowledge: bool = True,
        include_history: bool = True,
    ) -> OperationalContextSnapshot:
        """
        Assemble the complete operational context for the given asset.

        Args:
            asset_id:            Target asset (e.g. "F-201A")
            telemetry_override:  Use this telemetry instead of provider (for testing / replay)
            query_hint:          Query string for knowledge / episode search
            include_knowledge:   Include engineering knowledge retrieval
            include_history:     Include historical episode retrieval

        Returns:
            OperationalContextSnapshot with all available data and provenance tags.
        """
        t0 = datetime.now(timezone.utc)
        providers_used: List[str] = []
        warnings: List[str] = []

        # ── 1. Telemetry ──────────────────────────────────────────────────
        telemetry_fields: Dict[str, ContextField] = {}
        sensor_health: Dict[str, str] = {}
        raw_telemetry: Dict[str, Any] = {}

        if telemetry_override is not None:
            raw_telemetry = dict(telemetry_override)
            for param, val in raw_telemetry.items():
                telemetry_fields[param] = ContextField(
                    value=val,
                    provenance=DataProvenance.OBSERVED,
                    source="override",
                )
            providers_used.append("telemetry:override")
        elif self._tel is not None:
            try:
                latest = self._tel.get_latest(asset_id)
                for param, meta in latest.items():
                    v = meta.get("value")
                    raw_telemetry[param] = v
                    ts_str = meta.get("timestamp")
                    ts: Optional[datetime] = None
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str)
                        except ValueError:
                            pass

                    prov = DataProvenance.OBSERVED
                    if ts is not None:
                        age = (t0 - ts).total_seconds()
                        if age > self._staleness_s:
                            prov = DataProvenance.STALE
                            warnings.append(f"Stale telemetry: {param} age={age:.0f}s")

                    qual = meta.get("quality", "GOOD").upper()
                    if qual in ("BAD", "SUBSTITUTED"):
                        prov = DataProvenance.STALE

                    telemetry_fields[param] = ContextField(
                        value=v,
                        provenance=prov,
                        unit=meta.get("unit"),
                        source=meta.get("source"),
                        timestamp=ts,
                    )
                sensor_health = self._tel.get_sensor_health(asset_id)
                providers_used.append("telemetry:live")
            except Exception as exc:
                logger.warning("TelemetryProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Telemetry provider error: {exc}")

        # ── 2. ML Evidence ────────────────────────────────────────────────
        ml_evidence: List[MLEvidence] = []
        ml_summary: Optional[MLContextSummary] = None

        if self._ml is not None and raw_telemetry:
            try:
                ml_evidence = self._ml.run(asset_id, raw_telemetry)
                ml_summary = self._build_ml_summary(ml_evidence)
                providers_used.append("ml_runtime")
            except Exception as exc:
                logger.warning("MLRuntime failed for %s: %s", asset_id, exc)
                warnings.append(f"ML runtime error: {exc}")
        else:
            if not raw_telemetry:
                warnings.append("No telemetry available — ML inference skipped")

        # ── 3. Alarms ─────────────────────────────────────────────────────
        active_alarms: List[Dict[str, Any]] = []
        highest_alarm_sev = ContextField(value=None, provenance=DataProvenance.MISSING)

        if self._alm is not None:
            try:
                active_alarms = self._alm.get_active_alarms(asset_id)
                sev = self._compute_highest_alarm(active_alarms)
                highest_alarm_sev = ContextField(
                    value=sev,
                    provenance=DataProvenance.OBSERVED if active_alarms else DataProvenance.DERIVED,
                    source="alarm_provider",
                )
                providers_used.append("alarms")
            except Exception as exc:
                logger.warning("AlarmProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Alarm provider error: {exc}")

        # ── 4. Asset metadata ─────────────────────────────────────────────
        asset_metadata: Optional[Dict[str, Any]] = None
        equipment_status = ContextField(value="UNKNOWN", provenance=DataProvenance.MISSING)
        asset_criticality = ContextField(value="MEDIUM", provenance=DataProvenance.MISSING)

        if self._ast is not None:
            try:
                asset_metadata = self._ast.get_asset(asset_id)
                eq_status = self._ast.get_equipment_status(asset_id)
                criticality = self._ast.get_asset_criticality(asset_id)
                equipment_status = ContextField(
                    value=eq_status,
                    provenance=DataProvenance.OBSERVED,
                    source="asset_provider",
                )
                asset_criticality = ContextField(
                    value=criticality,
                    provenance=DataProvenance.OBSERVED,
                    source="asset_provider",
                )
                providers_used.append("assets")
            except Exception as exc:
                logger.warning("AssetProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Asset provider error: {exc}")

        # ── 5. Maintenance ────────────────────────────────────────────────
        active_maintenance: List[Dict[str, Any]] = []
        if self._mnt is not None:
            try:
                active_maintenance = self._mnt.get_active_maintenance(asset_id)
                providers_used.append("maintenance")
            except Exception as exc:
                logger.warning("MaintenanceProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Maintenance provider error: {exc}")

        # ── 6. Permits ────────────────────────────────────────────────────
        active_permits: List[Dict[str, Any]] = []
        is_simops = ContextField(value=False, provenance=DataProvenance.DERIVED)
        if self._prm is not None:
            try:
                active_permits = self._prm.get_active_permits(asset_id)
                simops_flag = self._prm.is_simops_active(asset_id)
                is_simops = ContextField(
                    value=simops_flag or (bool(active_permits) and bool(active_maintenance)),
                    provenance=DataProvenance.DERIVED,
                    source="permit_provider",
                )
                providers_used.append("permits")
            except Exception as exc:
                logger.warning("PermitProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Permit provider error: {exc}")

        # ── 7. Operating context ──────────────────────────────────────────
        operating_mode = ContextField(value="UNKNOWN", provenance=DataProvenance.MISSING)
        personnel_count = ContextField(value=0, provenance=DataProvenance.MISSING)
        if self._ops is not None:
            try:
                mode = self._ops.get_operating_mode()
                occ = self._ops.get_occupancy()
                total_personnel = sum(occ.values()) if occ else 0
                operating_mode = ContextField(
                    value=mode,
                    provenance=DataProvenance.OBSERVED,
                    source="operations_provider",
                )
                personnel_count = ContextField(
                    value=total_personnel,
                    provenance=DataProvenance.OBSERVED,
                    source="operations_provider",
                )
                providers_used.append("operations")
            except Exception as exc:
                logger.warning("OperationsProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Operations provider error: {exc}")

        # ── 8. Historical episodes ────────────────────────────────────────
        similar_episodes: List[Dict[str, Any]] = []
        if include_history and self._hist is not None:
            try:
                q = query_hint or self._build_episode_query(ml_summary, active_alarms)
                if q:
                    similar_episodes = self._hist.search_similar_episodes(
                        query=q, asset_id=asset_id, top_k=5
                    )
                    providers_used.append("historical_episodes")
            except Exception as exc:
                logger.warning("HistoricalEpisodeProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Historical episode provider error: {exc}")

        # ── 9. Knowledge ──────────────────────────────────────────────────
        knowledge_refs: List[Dict[str, Any]] = []
        if include_knowledge and self._know is not None:
            try:
                q = query_hint or self._build_episode_query(ml_summary, active_alarms)
                if q:
                    knowledge_refs = self._know.search_knowledge(
                        query=q, asset_id=asset_id, top_k=5
                    )
                    providers_used.append("knowledge")
            except Exception as exc:
                logger.warning("KnowledgeProvider failed for %s: %s", asset_id, exc)
                warnings.append(f"Knowledge provider error: {exc}")

        # ── Assemble ──────────────────────────────────────────────────────
        t1 = datetime.now(timezone.utc)
        duration_ms = (t1 - t0).total_seconds() * 1000.0

        snapshot = OperationalContextSnapshot(
            asset_id=asset_id,
            timestamp=t0,
            telemetry=telemetry_fields,
            sensor_health=sensor_health,
            ml_summary=ml_summary,
            ml_evidence=ml_evidence,
            active_alarms=active_alarms,
            highest_alarm_severity=highest_alarm_sev,
            asset_metadata=asset_metadata,
            equipment_status=equipment_status,
            asset_criticality=asset_criticality,
            active_maintenance=active_maintenance,
            active_permits=active_permits,
            is_simops=is_simops,
            operating_mode=operating_mode,
            personnel_count=personnel_count,
            similar_episodes=similar_episodes,
            knowledge_references=knowledge_refs,
            assembly_duration_ms=round(duration_ms, 2),
            providers_used=providers_used,
            warnings=warnings,
        )

        logger.debug(
            "ContextEngine.assemble: asset=%s, providers=%s, duration=%.1fms, warnings=%d",
            asset_id, providers_used, duration_ms, len(warnings),
        )
        return snapshot

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_ml_summary(self, evidence: List[MLEvidence]) -> MLContextSummary:
        """Condense ML evidence list into a typed ML summary."""
        model_versions: Dict[str, str] = {}
        anomaly_ev: Optional[MLEvidence] = None
        fault_ev: Optional[MLEvidence] = None
        cot_ev: Optional[MLEvidence] = None
        tube_ev: Optional[MLEvidence] = None

        for ev in evidence:
            model_versions[ev.prediction_type.value] = ev.model_version
            if ev.prediction_type == MLPredictionType.ANOMALY:
                anomaly_ev = ev
            elif ev.prediction_type == MLPredictionType.FAULT_CLASSIFICATION:
                fault_ev = ev
            elif ev.prediction_type == MLPredictionType.COT_PREDICTION:
                cot_ev = ev
            elif ev.prediction_type == MLPredictionType.TUBE_TEMPERATURE:
                tube_ev = ev

        def _field(ev: Optional[MLEvidence], key: str, *, default=None) -> ContextField:
            if ev is None or ev.status != MLEvidenceStatus.OK or ev.prediction is None:
                return ContextField(value=default, provenance=DataProvenance.MISSING)
            return ContextField(
                value=ev.prediction.get(key, default),
                provenance=DataProvenance.PREDICTED,
                source=ev.model_name,
                timestamp=ev.timestamp,
            )

        return MLContextSummary(
            anomaly_detected=_field(anomaly_ev, "is_anomaly", default=False),
            anomaly_score=_field(anomaly_ev, "anomaly_score"),
            predicted_fault=_field(fault_ev, "predicted_fault"),
            fault_confidence=ContextField(
                value=fault_ev.confidence if fault_ev and fault_ev.is_successful else None,
                provenance=DataProvenance.PREDICTED if (fault_ev and fault_ev.is_successful) else DataProvenance.MISSING,
            ),
            predicted_cot=_field(cot_ev, "predicted_cot"),
            predicted_tube_temperature=_field(tube_ev, "predicted_tube_temperature"),
            model_versions=model_versions,
            evidence_records=evidence,
        )

    def _compute_highest_alarm(self, alarms: List[Dict[str, Any]]) -> Optional[str]:
        """Return highest severity string from active alarms."""
        if not alarms:
            return None
        priority = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        found = None
        for alarm in alarms:
            sev = str(alarm.get("severity", "")).upper()
            if sev in priority:
                if found is None or priority.index(sev) < priority.index(found):
                    found = sev
            if found == "CRITICAL":
                break
        return found

    def _build_episode_query(
        self,
        ml_summary: Optional[MLContextSummary],
        active_alarms: List[Dict[str, Any]],
    ) -> str:
        """Build a natural-language query for episode / knowledge search."""
        parts: List[str] = []
        if ml_summary:
            if ml_summary.anomaly_detected.value:
                score = ml_summary.anomaly_score.value
                parts.append(f"process anomaly detected score={score:.2f}" if score else "process anomaly detected")
            fault = ml_summary.predicted_fault.value
            if fault and fault not in ("NORMAL", "None", None):
                parts.append(f"fault: {fault}")
        for alarm in active_alarms[:3]:
            tag = alarm.get("tag") or alarm.get("alarm_tag", "")
            sev = alarm.get("severity", "")
            if tag:
                parts.append(f"alarm {tag} {sev}".strip())
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Default singleton (all default providers wired up)
# ---------------------------------------------------------------------------

def _build_default_context_engine() -> ContextEngine:
    """Build the default ContextEngine with default providers and ML runtime."""
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
    from backend.ml.runtime.mocks import build_mock_ml_runtime

    return ContextEngine(
        telemetry_provider=PlantStateTelemetryProvider(),
        alarm_provider=PlantStateAlarmProvider(),
        asset_provider=PlantStateAssetProvider(),
        maintenance_provider=PlantStateMaintenanceProvider(),
        permit_provider=PlantStatePermitProvider(),
        operations_provider=PlantStateOperationsProvider(),
        historical_provider=InMemoryHistoricalEpisodeProvider(),
        knowledge_provider=StubKnowledgeProvider(),
        ml_runtime=build_mock_ml_runtime(),
    )


context_engine: ContextEngine = _build_default_context_engine()
