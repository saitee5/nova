"""Assembles a full OperationalContext for a zone.

Joins live sensor events with permits, maintenance records, shift data,
and equipment metadata.  Pure structured data-assembly — no LLM calls.

All SQL uses parameterized queries via sqlite3.  If a sub-query returns
nothing the result is an empty list (never an exception) — a zone
legitimately having no active permits is a valid, common state.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from backend.agents.sensor_event_intelligence.agent import (
    SensorEventIntelligenceAgent,
)
from backend.models.event import NormalizedEvent

from .context_schema import (
    EquipmentContext,
    MaintenanceRecord,
    OperationalContext,
    PermitRecord,
    ShiftState,
)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def build_context(
    zone_id: str,
    sensor_agent: SensorEventIntelligenceAgent,
    db_conn: sqlite3.Connection,
) -> OperationalContext:
    """Build the full situational picture for *zone_id*.

    Args:
        zone_id: The zone to assemble context for.
        sensor_agent: An initialised SensorEventIntelligenceAgent whose
            rolling buffer contains recent normalized events.
        db_conn: An open ``sqlite3.Connection`` (with
            ``row_factory = sqlite3.Row`` recommended).

    Returns:
        A fully populated ``OperationalContext``.  Sub-fields that have no
        matching data are empty lists / a default ``ShiftState``.
    """
    now = datetime.now(timezone.utc)

    active_permits = _query_active_permits(db_conn, zone_id, now)
    recent_maintenance = _query_recent_maintenance(db_conn, zone_id, now)
    shift_state = _query_shift_state(db_conn, zone_id, now)
    equipment = _query_equipment(db_conn, zone_id)
    recent_events = _get_recent_events(sensor_agent, zone_id, minutes=30, now=now)

    return OperationalContext(
        zone_id=zone_id,
        ts=now,
        active_permits=active_permits,
        recent_maintenance=recent_maintenance,
        shift_state=shift_state,
        equipment=equipment,
        recent_events=recent_events,
    )


# ------------------------------------------------------------------
# Internal query helpers
# ------------------------------------------------------------------


def _query_active_permits(
    conn: sqlite3.Connection,
    zone_id: str,
    now: datetime,
) -> list[PermitRecord]:
    """Return permits that are active and whose window covers *now*."""
    now_iso = now.isoformat()
    cursor = conn.execute(
        """
        SELECT permit_id, permit_type, zone_id, holder, status,
               COALESCE(window_start, '2026-01-01T00:00:00Z') as window_start,
               COALESCE(window_end, '2030-01-01T00:00:00Z') as window_end
          FROM permits
         WHERE status = ?
           AND (zone_id = ? OR zone_id IS NULL)
           AND COALESCE(window_start, '2026-01-01T00:00:00Z') <= ?
           AND COALESCE(window_end, '2030-01-01T00:00:00Z') >= ?
        """,
        ("active", zone_id, now_iso, now_iso),
    )
    rows = cursor.fetchall()
    results = []
    for r in rows:
        try:
            ws = datetime.fromisoformat(r["window_start"].replace("Z", "+00:00"))
            we = datetime.fromisoformat(r["window_end"].replace("Z", "+00:00"))
        except Exception:
            ws = now
            we = now
        results.append(
            PermitRecord(
                permit_id=r["permit_id"],
                permit_type=r["permit_type"] or "hot_work",
                zone_id=r["zone_id"] or zone_id,
                holder=r["holder"] or "Operator",
                status=r["status"] or "active",
                window_start=ws,
                window_end=we,
            )
        )
    return results


def _query_recent_maintenance(
    conn: sqlite3.Connection,
    zone_id: str,
    now: datetime,
) -> list[MaintenanceRecord]:
    """Return maintenance records for equipment in *zone_id* logged within 24 h."""
    cutoff_iso = (now - timedelta(hours=24)).isoformat()
    cursor = conn.execute(
        """
        SELECT m.record_id, m.equipment_id, m.fault_code,
               m.logged_at, m.summary
          FROM maintenance_records m
          JOIN equipment e ON m.equipment_id = e.equipment_id
         WHERE e.zone_id = ?
           AND m.logged_at >= ?
        """,
        (zone_id, cutoff_iso),
    )
    rows = cursor.fetchall()
    return [
        MaintenanceRecord(
            record_id=r["record_id"],
            equipment_id=r["equipment_id"],
            fault_code=r["fault_code"],
            logged_at=datetime.fromisoformat(r["logged_at"].replace("Z", "+00:00")),
            summary=r["summary"],
        )
        for r in rows
    ]


def _query_shift_state(
    conn: sqlite3.Connection,
    zone_id: str,
    now: datetime,
) -> ShiftState:
    """Find the shift covering *now* for *zone_id* and compute changeover.

    If no matching shift is found, returns a default ``ShiftState`` with
    ``current_shift="unknown"`` and ``changeover_at=None``.
    """
    now_iso = now.isoformat()
    cursor = conn.execute(
        """
        SELECT shift_id, starts_at, ends_at
          FROM shifts
         WHERE zone_id = ?
           AND starts_at <= ?
           AND ends_at   >= ?
        """,
        (zone_id, now_iso, now_iso),
    )
    row = cursor.fetchone()
    if row is None:
        return ShiftState(current_shift="unknown", changeover_at=None)

    ends_at = datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00"))
    return ShiftState(current_shift=row["shift_id"], changeover_at=ends_at)


def _query_equipment(
    conn: sqlite3.Connection,
    zone_id: str,
) -> list[EquipmentContext]:
    """Return all equipment items assigned to *zone_id*."""
    cursor = conn.execute(
        """
        SELECT equipment_id, equipment_class, criticality, zone_id
          FROM equipment
         WHERE zone_id = ?
        """,
        (zone_id,),
    )
    rows = cursor.fetchall()
    return [
        EquipmentContext(
            equipment_id=r["equipment_id"],
            equipment_class=r["equipment_class"],
            criticality=r["criticality"],
            zone_id=r["zone_id"],
        )
        for r in rows
    ]


def _get_recent_events(
    sensor_agent: SensorEventIntelligenceAgent,
    zone_id: str,
    minutes: int,
    now: datetime,
) -> list[NormalizedEvent]:
    """Filter the sensor agent's rolling buffer by zone and time window.

    ``SensorEventIntelligenceAgent.get_recent_events(n)`` returns the
    last *n* events across *all* zones.  We pull a generous slice and
    filter client-side by zone_id and timestamp.
    """
    cutoff = now - timedelta(minutes=minutes)
    all_recent = sensor_agent.get_recent_events(n=200)
    return [
        evt
        for evt in all_recent
        if evt.zone_id == zone_id and _ensure_aware(evt.ts) >= cutoff
    ]


def _ensure_aware(dt: datetime) -> datetime:
    """Promote naïve datetimes to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
