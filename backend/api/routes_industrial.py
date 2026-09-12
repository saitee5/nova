"""
backend/api/routes_industrial.py — Canonical Industrial REST API Endpoints.

Provides strongly-typed REST routes for:
- Plant, Unit, Asset, Sensor topology
- Real-time telemetry ingestion and querying
- Alarms, Maintenance, Permits, and Occupancy tracking
- Aggregated Plant State inspection
- Pluggable ML Model status and inference
- Deterministic Industrial Risk evaluation
- Operational Episode lifecycle inspection
- Semantic memory search and grounded Copilot querying
- Audit trail log inspection
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.config_reference_plant import (
    REFERENCE_ASSETS,
    REFERENCE_PLANT,
    REFERENCE_UNITS,
    get_reference_plant_summary,
)
from backend.db.db import get_connection
from backend.ml.features.extractor import FeatureExtractor
from backend.ml.inference.pipeline import ml_pipeline
from backend.ml.registry.registry import model_registry
from backend.models.evidence import EvidencePackage, HistoricalMatch
from backend.models.industrial_domain import (
    Alarm,
    IndustrialRiskAssessment,
    MaintenanceRecord,
    MLAssessment,
    OccupancyRecord,
    OperatingMode,
    OperationalEpisode,
    Permit,
    PlantState,
    ProcessTelemetry,
    RiskTier,
)
from backend.services.episode_engine import episode_engine
from backend.services.industrial_risk_service import industrial_risk_engine
from backend.services.plant_state_service import plant_state_service

logger = logging.getLogger("nova.api.industrial")

router = APIRouter(tags=["industrial"])


# ──────────────────────────────────────────────────────────────────────────────
# Topology: Plants, Units, Assets, Sensors
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/plants")
@router.get("/api/plants")
async def get_plants() -> List[Dict[str, Any]]:
    return [REFERENCE_PLANT.model_dump()]


@router.get("/units")
@router.get("/api/units")
async def get_units() -> List[Dict[str, Any]]:
    return [u.model_dump() for u in REFERENCE_UNITS]


@router.get("/assets")
@router.get("/api/assets")
async def get_assets() -> List[Dict[str, Any]]:
    return REFERENCE_ASSETS


@router.get("/sensors")
@router.get("/api/sensors")
async def get_sensors() -> List[Dict[str, Any]]:
    summary = get_reference_plant_summary()
    return summary.get("sensors", [])


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/telemetry")
@router.post("/api/telemetry")
async def ingest_telemetry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest canonical telemetry reading into PlantState and Episode correlation."""
    try:
        telem = ProcessTelemetry(**payload)
        plant_state_service.update_telemetry(telem)
        episode_engine.correlate_observation(asset_id=telem.asset_id, telemetry=telem)
        return {"status": "ingested", "event_id": telem.event_id, "asset_id": telem.asset_id}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid telemetry payload: {exc}")


@router.get("/telemetry")
@router.get("/api/telemetry")
async def get_telemetry(asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve recent telemetry observations."""
    state = plant_state_service.get_current_state()
    readings = list(state.telemetry.values())
    if asset_id:
        readings = [r for r in readings if r.asset_id == asset_id]
    return [r.model_dump() for r in readings]


@router.get("/telemetry/timeseries")
@router.get("/api/telemetry/timeseries")
async def get_telemetry_timeseries(
    asset_id: str = Query(default="F-201A"),
    limit: int = Query(default=30, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """Retrieve historical time-series observations for an asset."""
    import os
    import sqlite3
    from backend.db.db import DEFAULT_DB_PATH
    db_path = os.environ.get("SQLITE_DB_PATH", os.environ.get("SQLITE_PATH", str(DEFAULT_DB_PATH)))
    entries = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, ts, zone_id, sensor_type, value, unit, is_anomaly
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        for r in rows:
            entries.append(dict(r))
        conn.close()
    except Exception as exc:
        logger.warning("Telemetry timeseries query fallback: %s", exc)
    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Alarms, Maintenance, Permits, Occupancy
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/alarms")
@router.get("/api/alarms")
async def get_alarms() -> List[Dict[str, Any]]:
    state = plant_state_service.get_current_state()
    return [a.model_dump() for a in state.active_alarms]


@router.post("/alarms")
@router.post("/api/alarms")
async def create_alarm(payload: Dict[str, Any]) -> Dict[str, Any]:
    alarm = plant_state_service.update_alarm(payload)
    episode_engine.correlate_observation(asset_id=alarm.asset_id, alarms=[alarm])
    return {"status": "created", "alarm_id": alarm.alarm_id}


@router.post("/alarms/{alarm_id}/acknowledge")
@router.post("/api/alarms/{alarm_id}/acknowledge")
async def acknowledge_alarm(alarm_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = plant_state_service.get_current_state()
    target_alarm = None
    for a in state.active_alarms:
        if a.alarm_id == alarm_id:
            target_alarm = a
            break
    if not target_alarm:
        raise HTTPException(status_code=404, detail=f"Alarm '{alarm_id}' not found among active alarms.")

    data = target_alarm.model_dump()
    data["state"] = "ACKNOWLEDGED"
    data["acknowledged"] = True
    updated = plant_state_service.update_alarm(data)

    actor = (payload or {}).get("actor", "OPERATOR")
    notes = (payload or {}).get("notes")
    try:
        from backend.services.audit_service import write_audit_entry
        write_audit_entry(
            case_id="ALARM",
            action="ALARM_ACKNOWLEDGE",
            actor=actor,
            payload={"alarm_id": alarm_id, "tag": updated.tag, "notes": notes},
            step="OPERATIONAL",
        )
    except Exception as exc:
        logger.warning("Failed to record alarm acknowledgement audit: %s", exc)

    return updated.model_dump()



@router.get("/maintenance")
@router.get("/api/maintenance")
async def get_maintenance() -> List[Dict[str, Any]]:
    state = plant_state_service.get_current_state()
    return [m.model_dump() for m in state.active_maintenance]


@router.post("/maintenance")
@router.post("/api/maintenance")
async def create_maintenance(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = plant_state_service.update_maintenance(payload)
    episode_engine.correlate_observation(asset_id=record.asset_id, maintenance=[record])
    return {"status": "registered", "record_id": record.record_id}


@router.get("/permits")
@router.get("/api/permits")
async def get_permits() -> List[Dict[str, Any]]:
    state = plant_state_service.get_current_state()
    return [p.model_dump() if hasattr(p, "model_dump") else p for p in state.active_permits]


@router.post("/permits")
@router.post("/api/permits")
async def create_permit(payload: Dict[str, Any]) -> Dict[str, Any]:
    permit = plant_state_service.update_permit(payload)
    asset_id = getattr(permit, "asset_id", None) or payload.get("asset_id", "F-201A")
    permit_obj = Permit(**payload) if isinstance(payload, dict) else permit
    episode_engine.correlate_observation(asset_id=asset_id, permits=[permit_obj])
    return {"status": "registered", "permit_id": payload.get("permit_id")}


@router.get("/occupancy")
@router.get("/api/occupancy")
async def get_occupancy() -> Dict[str, int]:
    state = plant_state_service.get_current_state()
    return state.occupancy


# ──────────────────────────────────────────────────────────────────────────────
# Plant State
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/plant-state")
@router.get("/api/plant-state")
async def get_plant_state() -> Dict[str, Any]:
    """Retrieve full authoritative snapshot of current industrial plant state."""
    state = plant_state_service.get_current_state()
    return state.model_dump()


# ──────────────────────────────────────────────────────────────────────────────
# ML Subsystem & Pipeline
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/ml/status")
@router.get("/api/ml/status")
async def get_ml_status() -> Dict[str, Any]:
    """Inspect registered ML models, versions, and weight availability."""
    models = model_registry.list_models()
    return {
        "total_registered_models": len(models),
        "catalog": [
            {
                "name": m.name,
                "version": m.version,
                "model_type": m.model_type,
                "algorithm": m.algorithm,
                "status": m.status,
                "is_artifact_available": model_registry.is_artifact_available(
                    m.name.lower() if m.name.lower() in model_registry._models else m.model_type
                ),
            }
            for m in models
        ],
    }


@router.post("/ml/inference")
@router.post("/api/ml/inference")
async def run_ml_inference(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute the pluggable MLPipeline across all 4 industrial model contracts."""
    data = payload or {}
    asset_id = data.get("asset_id", "F-201A")
    telemetry = data.get("telemetry", {})

    # If telemetry is not supplied, pull from live PlantState
    if not telemetry:
        state = plant_state_service.get_current_state()
        results = ml_pipeline.run_pipeline(input_data=state, asset_id=asset_id)
    else:
        results = ml_pipeline.run_pipeline(input_data=telemetry, asset_id=asset_id)

    # Correlate ML results into active episode
    episode_engine.correlate_observation(asset_id=asset_id, ml_assessments=results)

    return {
        "asset_id": asset_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "assessments": {k: v.model_dump() for k, v in results.items()},
    }


# ──────────────────────────────────────────────────────────────────────────────
# Risk Engine
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/risk")
@router.get("/api/risk")
async def get_risk(asset_id: str = Query(default="F-201A")) -> Dict[str, Any]:
    """Evaluate deterministic multi-factor industrial risk for specified asset."""
    state = plant_state_service.get_current_state()
    ml_results = ml_pipeline.run_pipeline(input_data=state, asset_id=asset_id)
    assessment = industrial_risk_engine.evaluate_plant_state(
        plant_state=state,
        ml_assessments=ml_results,
        target_asset_id=asset_id,
    )
    episode_engine.correlate_observation(asset_id=asset_id, risk=assessment)
    return assessment.model_dump()


class RiskEvaluationRequest(BaseModel):
    asset_id: str = "F-201A"
    process_anomaly_score: float = 0.0
    equipment_condition_score: float = 0.0
    alarm_severity: str = "LOW"
    has_active_permit: bool = False
    is_simops: bool = False
    personnel_count_in_zone: int = 0
    asset_criticality: str = "MEDIUM"


@router.post("/risk/evaluate")
@router.post("/api/risk/evaluate")
async def evaluate_risk(req: RiskEvaluationRequest) -> Dict[str, Any]:
    assessment = industrial_risk_engine.evaluate_asset_risk(
        asset_id=req.asset_id,
        process_anomaly_score=req.process_anomaly_score,
        equipment_condition_score=req.equipment_condition_score,
        alarm_severity=req.alarm_severity,
        has_active_permit=req.has_active_permit,
        is_simops=req.is_simops,
        personnel_count_in_zone=req.personnel_count_in_zone,
        asset_criticality=req.asset_criticality,
    )
    episode_engine.correlate_observation(asset_id=req.asset_id, risk=assessment)
    return assessment.model_dump()


# ──────────────────────────────────────────────────────────────────────────────
# Operational Episodes
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/episodes")
@router.get("/api/episodes")
async def get_episodes() -> List[Dict[str, Any]]:
    episodes = episode_engine.list_active_episodes()
    if not episodes:
        state = plant_state_service.get_current_state()
        risk = industrial_risk_engine.evaluate_plant_state(state, target_asset_id="F-201A")
        ep = episode_engine.correlate_observation(
            asset_id="F-201A",
            alarms=state.active_alarms,
            permits=state.active_permits,
            maintenance=state.active_maintenance,
            risk=risk,
        )
        episodes = [ep]
    return [ep.model_dump() for ep in episodes]


@router.get("/episodes/{episode_id}")
@router.get("/api/episodes/{episode_id}")
async def get_episode_by_id(episode_id: str) -> Dict[str, Any]:
    ep = episode_engine.get_episode(episode_id)
    if not ep:
        raise HTTPException(status_code=404, detail=f"Episode {episode_id} not found.")
    return ep.model_dump()


# ──────────────────────────────────────────────────────────────────────────────
# Semantic Memory & Copilot
# ──────────────────────────────────────────────────────────────────────────────

class MemorySearchRequest(BaseModel):
    query: str
    collection: str = "nova_operational_memory"
    top_k: int = 5


@router.post("/memory/search")
@router.post("/api/memory/search")
async def search_memory(req: MemorySearchRequest) -> Dict[str, Any]:
    try:
        from backend.memory.collections import MemoryStore
        store = MemoryStore()
        coll = req.collection if req.collection and req.collection != "nova_operational_memory" else "incidents_historical"
        results = store.search(collection_name=coll, query_text=req.query, top_k=req.top_k)
        if results:
            return {"query": req.query, "collection": coll, "matches": results}
    except Exception as exc:
        logger.warning("Memory search store query failed, falling back to seed incidents: %s", exc)

    try:
        from backend.memory.seed_qdrant import INCIDENTS_HISTORICAL
        query_words = [w.lower() for w in req.query.split() if len(w) > 2]
        scored_matches = []
        for inc in INCIDENTS_HISTORICAL:
            payload = inc.get("payload", {})
            title = str(inc.get("title", ""))
            desc = str(inc.get("description", ""))
            zone = str(payload.get("zone_id", ""))
            equip = str(payload.get("equipment_id", ""))
            factors = " ".join(str(f) for f in payload.get("contributing_factors", []))
            full_text = f"{title} {desc} {zone} {equip} {factors}".lower()

            match_count = sum(1 for w in query_words if w in full_text)
            score = round(min(0.98, 0.72 + 0.08 * match_count), 2) if match_count > 0 else 0.65
            scored_matches.append({
                "id": str(inc.get("id", "")),
                "score": score,
                "title": title,
                "description": desc,
                "payload": payload,
            })
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        return {"query": req.query, "collection": "incidents_historical", "matches": scored_matches[:req.top_k]}
    except Exception as exc:
        return {"query": req.query, "collection": req.collection, "matches": [], "error": str(exc)}


class CopilotQueryRequest(BaseModel):
    prompt: str
    asset_id: str = "F-201A"


@router.post("/copilot/query")
@router.post("/api/copilot/query")
async def query_copilot(req: CopilotQueryRequest) -> Dict[str, Any]:
    """Execute grounded industrial copilot inquiry backed by EvidencePackage."""
    state = plant_state_service.get_current_state()
    ml_results = ml_pipeline.run_pipeline(input_data=state, asset_id=req.asset_id)
    risk_assessment = industrial_risk_engine.evaluate_plant_state(state, ml_results, target_asset_id=req.asset_id)

    # Assemble comprehensive EvidencePackage
    evidence_package = EvidencePackage(
        package_id=f"EPKG-{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc),
        plant_id=state.plant_id,
        unit_id=state.unit_id,
        asset_id=req.asset_id,
        plant_state=state.model_dump(),
        ml_assessments={k: v.model_dump() for k, v in ml_results.items()},
        risk_assessment=risk_assessment.model_dump(),
        active_alarms=[a.model_dump() for a in state.active_alarms],
        maintenance_records=[m.model_dump() for m in state.active_maintenance],
        permits=[p.model_dump() if hasattr(p, "model_dump") else p for p in state.active_permits],
        occupancy=state.occupancy,
        provenance={"system": "NOVA", "role": "READ_ONLY_ADVISORY", "policy_version": "1.0"},
    )

    explanation = (
        f"NOVA Industrial Copilot Advisory for {req.asset_id}: "
        f"Operating Mode: {state.operating_mode.value}. "
        f"Evaluated Risk: {risk_assessment.risk_score:.2f} ({risk_assessment.risk_tier.value}). "
        f"Active Alarms: {len(state.active_alarms)}. Active SIMOPS: {state.metadata.get('simops_active', False)}. "
        f"ML inference status: {[m.status for m in ml_results.values()]}."
    )

    return {
        "response": explanation,
        "evidence_package": evidence_package.model_dump(),
        "recommended_actions": risk_assessment.recommended_actions,
        "advisory_only": True,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Audit Trail
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/audit")
@router.get("/api/audit")
async def get_audit_trail(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve immutable audit log entries."""
    entries = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            for r in rows:
                entries.append(dict(r))
    except Exception as exc:
        logger.warning("Failed to query audit_log: %s", exc)
    return entries
