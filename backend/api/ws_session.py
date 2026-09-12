"""
backend/api/ws_session.py — WebSocket connection manager and session endpoint.

WS path: /ws/session/{session_id}

Protocol
--------
On connect  → background heartbeat task every 3 s:
    { "type": "connection.status",
      "payload": { "status": "connected", "session_id": "<id>" },
      "ts": "<ISO8601>" }

Client may send any JSON (reserved for future ASR text-fallback); unrecognised
messages are logged and ignored.

Graceful disconnect: WebSocketDisconnect is caught; heartbeat task is cancelled.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.db.db import get_db

if TYPE_CHECKING:
    from backend.bus.event_bus import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# --------------------------------------------------------------------------- #
# Connection manager                                                           #
# --------------------------------------------------------------------------- #


class ConnectionManager:
    """Tracks WebSocket connections keyed by session_id."""

    def __init__(self) -> None:
        # session_id → set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, session_id: str) -> None:
        await ws.accept()
        self._connections.setdefault(session_id, set()).add(ws)
        logger.info("WS connect: session=%s total=%d", session_id, len(self._connections[session_id]))

    def disconnect(self, ws: WebSocket, session_id: str) -> None:
        bucket = self._connections.get(session_id, set())
        bucket.discard(ws)
        if not bucket:
            self._connections.pop(session_id, None)
        logger.info("WS disconnect: session=%s", session_id)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        """Push *message* to every connection in *session_id*."""
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)

    async def broadcast_all(self, message: dict[str, Any]) -> None:
        """Push *message* to every connected client across all sessions."""
        for session_id in list(self._connections.keys()):
            await self.broadcast(session_id, message)


manager = ConnectionManager()


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def _heartbeat(ws: WebSocket, session_id: str) -> None:
    """Send a heartbeat envelope every 3 seconds until cancelled."""
    while True:
        await asyncio.sleep(3)
        envelope = {
            "type": "connection.status",
            "payload": {"status": "connected", "session_id": session_id},
            "ts": _now_iso(),
        }
        try:
            await ws.send_json(envelope)
        except Exception:
            # Client gone — let the main handler notice on next recv
            break


# --------------------------------------------------------------------------- #
# WebSocket endpoint                                                           #
# --------------------------------------------------------------------------- #


@router.websocket("/ws/session/{session_id}")
async def ws_session_endpoint(ws: WebSocket, session_id: str) -> None:
    await manager.connect(ws, session_id)
    await ws.send_json({
        "type": "connection.status",
        "payload": {"status": "connected", "session_id": session_id},
        "ts": _now_iso(),
    })
    heartbeat_task = asyncio.create_task(_heartbeat(ws, session_id))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("WS session=%s: non-JSON message received, ignored", session_id)
                continue
            # Reserved for ASR text-fallback messages — log and ignore for now
            logger.debug("WS session=%s recv: %s", session_id, msg.get("type", "<unknown>"))
    except WebSocketDisconnect:
        logger.info("WS session=%s: client disconnected", session_id)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(ws, session_id)


# --------------------------------------------------------------------------- #
# Event-bus → WebSocket bridge                                                 #
# --------------------------------------------------------------------------- #


async def start_ws_bridge(bus: "EventBus") -> None:
    """
    Subscribe to the event bus topics that the frontend cares about and
    forward them as typed WsEnvelope messages to ALL connected WS clients.

    Call this from FastAPI lifespan after bus.start():
        await start_ws_bridge(bus)

    Uses bus subscriptions (push), never polls.
    """

    def _ts() -> str:
        return datetime.now(tz=timezone.utc).isoformat() + "Z"

    async def on_risk_updated(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "risk.updated", "payload": event, "ts": _ts()}
        )

    async def on_case_state_changed(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "case.state_changed", "payload": event, "ts": _ts()}
        )

    async def on_audit_entry(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "audit.entry", "payload": event, "ts": _ts()}
        )

    async def on_ui_directive(event: dict[str, Any]) -> None:
        await manager.broadcast_all(event)

    async def on_raw_telemetry(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "raw.telemetry", "payload": event, "ts": _ts()}
        )
        # Trigger risk assessment for telemetry events to update live risk state and zoom
        hint = event.get("severity_hint", "normal")
        val = event.get("value")
        zone_id = event.get("zone_id", "unknown_zone")
        
        is_high_signal = (hint in ("elevated", "critical")) or (isinstance(val, (int, float)) and val >= 210)

        # Check existing case tier in DB to detect if we need to transition/normalize
        need_assessment = is_high_signal
        if not is_high_signal and zone_id:
            case_id = f"case-{zone_id.lower()}"
            from backend.api.routes_cases import _db_path
            try:
                async with get_db(_db_path()) as db:
                    cur = await db.execute("SELECT tier FROM cases WHERE case_id=?", (case_id,))
                    row = await cur.fetchone()
                    if row and row["tier"] != "low":
                        need_assessment = True
            except Exception:
                pass

        if need_assessment and zone_id:
            now_iso = _ts()
            case_id = f"case-{zone_id.lower()}"
            
            from backend.models.case import OperationalContext, ShiftState
            from backend.models.event import NormalizedEvent
            from backend.agents.risk_reasoner.agent import RiskReasonerAgent
            import uuid
            from datetime import datetime, timezone
            
            event_copy = dict(event)
            if "event_id" not in event_copy:
                event_copy["event_id"] = str(uuid.uuid4())
            if "severity_hint" not in event_copy:
                event_copy["severity_hint"] = hint
            if "metadata" not in event_copy:
                event_copy["metadata"] = {}
                
            ctx = OperationalContext(
                zone_id=zone_id,
                ts=datetime.now(timezone.utc),
                active_permits=[],
                recent_maintenance=[],
                shift_state=ShiftState(current_shift="Day", changeover_at=None),
                equipment=[],
                recent_events=[NormalizedEvent(**event_copy)]
            )
            
            reasoner = RiskReasonerAgent()
            assessment = await reasoner.assess(ctx, case_id)
            
            tier = assessment.tier
            score = assessment.compound_score
            
            # Upsert into DB so the frontend can pull it
            from backend.api.routes_cases import _db_path
            async with get_db(_db_path()) as db:
                await db.execute(
                    """
                    INSERT INTO cases (case_id, zone_id, state, tier, compound_score, created_at, resolved_at)
                    VALUES (?, ?, 'DETECTED', ?, ?, ?, NULL)
                    ON CONFLICT(case_id) DO UPDATE SET
                        tier = excluded.tier,
                        compound_score = excluded.compound_score,
                        state = CASE WHEN cases.state = 'RESOLVED' THEN 'DETECTED' ELSE cases.state END
                    """,
                    (case_id, zone_id, tier, score, now_iso),
                )
            
            risk_payload = assessment.model_dump(mode="json")
            risk_payload["case_id"] = case_id
            await bus.publish("risk.assessed", risk_payload)

    async def on_action_proposed(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "action.proposed", "payload": event, "ts": _ts()}
        )
        
    async def on_action_resolved(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "action.resolved", "payload": event, "ts": _ts()}
        )

    async def on_report_generated(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "report.generated", "payload": event, "ts": _ts()}
        )

    async def on_telemetry_updated(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "telemetry.updated", "payload": event, "ts": _ts(), "asset_id": event.get("asset_id")}
        )

    async def on_alarm_event(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "alarm.updated", "payload": event, "ts": _ts(), "asset_id": event.get("asset_id")}
        )

    async def on_episode_event(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "episode.updated", "payload": event, "ts": _ts(), "asset_id": event.get("asset_id")}
        )

    async def on_runtime_case_event(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "runtime.case.updated", "payload": event, "ts": _ts(), "case_id": event.get("case_id")}
        )

    async def on_plant_state_event(event: dict[str, Any]) -> None:
        await manager.broadcast_all(
            {"type": "plant_state.updated", "payload": event, "ts": _ts()}
        )

    await bus.subscribe("raw.telemetry", on_raw_telemetry)
    await bus.subscribe("risk.assessed", on_risk_updated)
    await bus.subscribe("case.state_changed", on_case_state_changed)
    await bus.subscribe("tool.executed", on_audit_entry)
    await bus.subscribe("ui.directive", on_ui_directive)
    await bus.subscribe("action.proposed", on_action_proposed)
    await bus.subscribe("action.resolved", on_action_resolved)
    await bus.subscribe("report.generated", on_report_generated)
    await bus.subscribe("telemetry.updated", on_telemetry_updated)
    await bus.subscribe("alarm.created", on_alarm_event)
    await bus.subscribe("alarm.updated", on_alarm_event)
    await bus.subscribe("episode.created", on_episode_event)
    await bus.subscribe("episode.updated", on_episode_event)
    await bus.subscribe("runtime.case.updated", on_runtime_case_event)
    await bus.subscribe("plant_state.updated", on_plant_state_event)

    logger.info("WS bridge: subscribed to raw.telemetry, risk.assessed, case.state_changed, tool.executed, ui.directive, action.*, report.*, telemetry.updated, alarm.*, episode.*, runtime.case.updated, plant_state.updated")
