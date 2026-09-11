"""Persistence service for cases and audit entries.

This module is the ONLY place in the codebase that writes to audit_log or cases.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from backend.db.db import get_connection
from backend.models.audit import AuditEntry
from backend.models.case import Case


def _iso(dt: datetime | None) -> str | None:
    """Format datetime to ISO string or return None."""
    if dt is None:
        return None
    return dt.isoformat()


def _parse_dt(dt_str: str | None) -> datetime | None:
    """Parse ISO string to datetime or return None."""
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def write_audit_entry(
    entry: AuditEntry,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Insert a single AuditEntry into the audit_log table.

    Args:
        entry: The ``AuditEntry`` instance to record.
        conn: Optional SQLite connection. If None, default connection is used.
    """
    payload_str = json.dumps(entry.payload) if entry.payload is not None else None
    ts_str = entry.ts.isoformat()

    sql = """
    INSERT INTO audit_log (entry_id, case_id, step, action, actor, decision, payload, ts)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        entry.entry_id, 
        entry.case_id, 
        entry.step, 
        entry.action,
        entry.actor,
        entry.decision,
        payload_str, 
        ts_str
    )

    if conn is not None:
        conn.execute(sql, params)
        conn.commit()
    else:
        with get_connection() as local_conn:
            local_conn.execute(sql, params)
            local_conn.commit()


def get_case_audit_trail(
    case_id: str,
    conn: sqlite3.Connection | None = None,
) -> list[AuditEntry]:
    """Retrieve all audit log entries for a given case in chronological order.

    Args:
        case_id: Case identifier.
        conn: Optional SQLite connection. If None, default connection is used.

    Returns:
        List of ``AuditEntry`` objects ordered by timestamp ascending.
    """
    sql = """
    SELECT id, entry_id, case_id, step, action, actor, decision, payload, ts
    FROM audit_log
    WHERE case_id = ?
    ORDER BY ts ASC
    """

    def _rows_from_conn(c: sqlite3.Connection) -> list[sqlite3.Row]:
        cursor = c.execute(sql, (case_id,))
        return cursor.fetchall()

    if conn is not None:
        rows = _rows_from_conn(conn)
    else:
        with get_connection() as local_conn:
            rows = _rows_from_conn(local_conn)

    entries: list[AuditEntry] = []
    for row in rows:
        payload_val = None
        if row["payload"]:
            try:
                payload_val = json.loads(row["payload"])
            except json.JSONDecodeError:
                pass
                
        ts_val = _parse_dt(row["ts"])
        assert ts_val is not None

        entries.append(
            AuditEntry(
                entry_id=row["entry_id"] or str(row["id"]),
                case_id=row["case_id"],
                step=row["step"] or "operator_action",
                action=row["action"],
                actor=row["actor"],
                decision=row["decision"],
                payload=payload_val,
                ts=ts_val,
            )
        )
    return entries


def persist_case(
    case: Case,
    conn: sqlite3.Connection | None = None,
) -> None:
    """Upsert a Case into the cases table.

    Args:
        case: The ``Case`` object to persist.
        conn: Optional SQLite connection. If None, default connection is used.
    """
    sql = """
    INSERT INTO cases (case_id, zone_id, state, tier, compound_score, created_at, resolved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(case_id) DO UPDATE SET
        zone_id = excluded.zone_id,
        state = excluded.state,
        tier = excluded.tier,
        compound_score = excluded.compound_score,
        resolved_at = excluded.resolved_at
    """
    params = (
        case.case_id,
        case.zone_id,
        case.state,
        case.tier,
        case.compound_score,
        _iso(case.created_at),
        _iso(case.resolved_at),
    )

    if conn is not None:
        conn.execute(sql, params)
        conn.commit()
    else:
        with get_connection() as local_conn:
            local_conn.execute(sql, params)
            local_conn.commit()


def get_case(
    case_id: str,
    conn: sqlite3.Connection | None = None,
) -> Case | None:
    """Retrieve a Case by case_id.

    Args:
        case_id: Case identifier.
        conn: Optional SQLite connection. If None, default connection is used.

    Returns:
        The ``Case`` object if found, or None if not found.
    """
    sql = """
    SELECT case_id, zone_id, state, tier, compound_score, created_at, resolved_at
    FROM cases
    WHERE case_id = ?
    """

    def _fetch_row(c: sqlite3.Connection) -> sqlite3.Row | None:
        cursor = c.execute(sql, (case_id,))
        return cursor.fetchone()

    if conn is not None:
        row = _fetch_row(conn)
    else:
        with get_connection() as local_conn:
            row = _fetch_row(local_conn)

    if row is None:
        return None

    created_at_dt = _parse_dt(row["created_at"])
    assert created_at_dt is not None

    return Case(
        case_id=row["case_id"],
        zone_id=row["zone_id"],
        state=row["state"],
        tier=row["tier"],
        compound_score=row["compound_score"],
        created_at=created_at_dt,
        resolved_at=_parse_dt(row["resolved_at"]),
    )
