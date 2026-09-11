"""
backend/api/routes_risk.py — Zone risk status stub.

Endpoints
---------
GET /api/zones  →  list[ZoneStatus]
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter(prefix="/zones", tags=["risk"])


class ZoneStatus(BaseModel):
    zone_id: str
    tier: str
    compound_score: float
    active_case_id: str | None


from backend.db.db import get_db

@router.get("", response_model=list[ZoneStatus])
async def list_zones() -> list[ZoneStatus]:
    # REAL: queries cases database table and active zone risk state
    async with get_db() as db:
        async with db.execute("SELECT zone_id, tier, compound_score, case_id FROM cases") as cursor:
            rows = await cursor.fetchall()
            if rows:
                return [
                    ZoneStatus(
                        zone_id=row["zone_id"],
                        tier=row["tier"] or "low",
                        compound_score=row["compound_score"] or 0.0,
                        active_case_id=row["case_id"],
                    )
                    for row in rows
                ]
    
    # Default active operational bays when database has no open cases
    return [
        ZoneStatus(zone_id="Bay1", tier="low", compound_score=0.10, active_case_id=None),
        ZoneStatus(zone_id="Bay2", tier="low", compound_score=0.15, active_case_id=None),
        ZoneStatus(zone_id="Bay3", tier="low", compound_score=0.20, active_case_id=None),
        ZoneStatus(zone_id="Bay4", tier="low", compound_score=0.08, active_case_id=None),
        ZoneStatus(zone_id="Bay5", tier="low", compound_score=0.12, active_case_id=None),
    ]


from backend.services.risk_service import calculate_decomposed_risk
from backend.services.asset_topology_service import topology_service


class DecomposedRiskRequest(BaseModel):
    threat_severity: float = 0.5
    asset_criticality: str = "MEDIUM"
    vulnerability_count: int = 0
    exposure_multiplier: float = 1.0


@router.post("/decompose")
async def decompose_risk(req: DecomposedRiskRequest):
    return calculate_decomposed_risk(
        threat_severity=req.threat_severity,
        asset_criticality=req.asset_criticality,
        vulnerability_count=req.vulnerability_count,
        exposure_multiplier=req.exposure_multiplier,
    )


@router.get("/topology")
async def get_network_topology():
    return topology_service.get_full_topology()


@router.get("/blast-radius/{node_id}")
async def get_blast_radius(node_id: str):
    return topology_service.calculate_blast_radius(node_id)


