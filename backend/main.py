"""
backend/main.py — VIGIL FastAPI application entry-point.

Startup sequence
----------------
1. Read environment variables (python-dotenv loads .env if present)
2. Lifespan: init SQLite schema, log "VIGIL backend ready"
3. CORS: allow localhost:5173/5174 and VITE_ORIGIN env var
4. Mount all /api route modules
5. Mount WebSocket at /ws/session/{session_id} and /ws/audio/{case_id}
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path

# Ensure repository root is on sys.path regardless of execution directory
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

load_dotenv()  # noqa: E402 — must run before any os.environ reads

from backend.api import routes_cases, routes_debug, routes_demo, routes_memory, routes_retrieval, routes_risk, routes_voice, routes_voice_command, routes_explainability, routes_readings
from backend.services.sensor_generator import SensorGenerator
from backend.api.ws_session import manager
from backend.api.routes_factory import router as factory_router, get_factory_state
from backend.api.ws_session import router as ws_router, start_ws_bridge
from backend.api.ws_audio import router as audio_router
from backend.bus.event_bus import bus
from backend.db.db import init_db, seed_demo_cases, get_db
from backend.debug_transport import debug_transport
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("vigil")

# --------------------------------------------------------------------------- #
# Lifespan                                                                     #
# --------------------------------------------------------------------------- #


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ──────────────────────────────────────────────────────────── #
    db_path = os.environ.get("SQLITE_PATH", "./vigil.db")
    await init_db(db_path)
    await seed_demo_cases(db_path)

    await bus.start()
    await start_ws_bridge(bus)

    # Debug transport is intentionally off unless explicitly enabled.
    # Production runs must set ENABLE_DEBUG_TRANSPORT=true only when a one-off debug session is needed.
    debug_enabled = os.environ.get("ENABLE_DEBUG_TRANSPORT", "false").lower() in ("true", "1", "yes")
    if debug_enabled:
        await debug_transport.enable()
        logger.info("✅ Debug transport enabled explicitly via ENABLE_DEBUG_TRANSPORT=true")
    else:
        logger.info("ℹ️ Debug transport disabled; APP_ENV is not used to activate it")


    # Pre-warm embedding model in background if enabled (disabled by default to prevent OOM on 512MB cloud free tier)
    if os.environ.get("ENABLE_PREWARM_EMBEDDINGS", "false").lower() in ("true", "1"):
        try:
            from backend.memory.embeddings import embed_text
            asyncio.create_task(asyncio.to_thread(embed_text, "init"))
        except Exception as exc:
            logger.warning("Failed to pre-warm embeddings: %s", exc)

    # Start 5-second SensorGenerator background loop
    try:
        sensor_generator = SensorGenerator(
            db_path=db_path,
            ws_manager=manager,
        )
        asyncio.create_task(sensor_generator.run())
        logger.info("Sensor generator online — 5s push loop active")
    except Exception as exc:
        logger.warning("Failed to start SensorGenerator: %s", exc)

    # Wire factory state updates from raw telemetry events
    async def _update_factory_state(event: dict) -> None:
        get_factory_state().apply_event(event)
        if event.get("source") == "permit":
            meta = event.get("metadata", {})
            permit_id = meta.get("permit_id")
            action = meta.get("action")
            permit_type = meta.get("permit_type", "hot_work")
            holder = meta.get("holder", "Operator")
            zone_id = event.get("zone_id", "Bay3")
            if permit_id and action:
                status = "active" if action == "activated" else ("suspended" if action == "suspended" else "closed")
                now_iso = datetime.now(timezone.utc).isoformat()
                try:
                    async with get_db(db_path) as db:
                        await db.execute(
                            """
                            INSERT INTO permits (permit_id, permit_type, zone_id, holder, status, window_start, window_end)
                            VALUES (?, ?, ?, ?, ?, ?, '2030-01-01T00:00:00Z')
                            ON CONFLICT(permit_id) DO UPDATE SET status = excluded.status
                            """,
                            (permit_id, permit_type, zone_id, holder, status, now_iso),
                        )
                    await bus.publish("ui.directive", {
                        "type": "permit.updated",
                        "payload": {"permit_id": permit_id, "status": status, "zone_id": zone_id}
                    })
                except Exception as exc:
                    logger.warning("Failed to persist live permit telemetry event: %s", exc)

    await bus.subscribe("raw.telemetry", _update_factory_state)

    # Wire Rime TTS to scenario voice events
    async def _speak_from_event(event: dict) -> None:
        text = event.get("text") or event.get("payload", {}).get("text", "")
        case_id = event.get("case_id", "demo")
        if text:
            try:
                from backend.api.ws_audio import speak_to_case
                await speak_to_case(case_id, text)
            except Exception as exc:
                logger.warning("Voice event TTS failed: %s", exc)

    await bus.subscribe("voice.speak", _speak_from_event)

    # Wire Risk Reasoner to Response Orchestrator
    async def _handle_risk_assessed(event: dict) -> None:
        try:
            from backend.models.risk import RiskAssessment
            from backend.services.audit_service import get_case
            from backend.agents.response_orchestrator.agent import ResponseOrchestratorAgent
            from backend.services.notification_service import VoiceNotifier
            
            # Extract or fallback case_id
            case_id = event.get("case_id")
            if not case_id:
                case_id = "case-" + event.get("zone_id", "unknown").lower()
                event["case_id"] = case_id
                
            assessment = RiskAssessment(**event)
            case = get_case(case_id)
            if not case:
                logger.warning("No case found for %s, skipping orchestration", case_id)
                return
            
            class DummyNotifier:
                def notify(self, target: str, message: str, case_id: str) -> None:
                    logger.info("Notify %s for %s: %s", target, case_id, message)
                    
            notifier = DummyNotifier()
            orchestrator = ResponseOrchestratorAgent(notifier)
            await orchestrator.handle_assessment(assessment, case)
        except Exception as exc:
            logger.error("Response Orchestrator failed: %s", exc)

    await bus.subscribe("risk.assessed", _handle_risk_assessed)

    logger.info("Event bus started, WS bridge active, audio WS ready")
    logger.info("VIGIL backend ready  |  db=%s", db_path)

    # Start internal BackgroundSimulatorService (controlled by SIMULATOR_ENABLED)
    from backend.simulator import BackgroundSimulatorService
    sim_service = BackgroundSimulatorService(bus)
    await sim_service.start()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────── #
    await sim_service.stop()
    await bus.shutdown()
    logger.info("VIGIL backend shutting down")


# --------------------------------------------------------------------------- #
# App                                                                          #
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="VIGIL — Compound-Risk Voice Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS -----------------------------------------------------------------------
_allowed_origins: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "*",
]
_vite_origin = os.environ.get("VITE_ORIGIN", "")
if _vite_origin and _vite_origin not in _allowed_origins:
    _allowed_origins.append(_vite_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes (/api prefix) --------------------------------------------------
_API_PREFIX = "/api"

app.include_router(routes_cases.router,      prefix=_API_PREFIX)
app.include_router(routes_risk.router,       prefix=_API_PREFIX)
app.include_router(routes_retrieval.router,  prefix=_API_PREFIX)
app.include_router(routes_voice.router,      prefix=_API_PREFIX)
app.include_router(routes_voice_command.router, prefix=_API_PREFIX)
app.include_router(routes_memory.router,     prefix=_API_PREFIX)
app.include_router(routes_demo.router,       prefix=_API_PREFIX)
app.include_router(routes_debug.router)      # Debug endpoints (no prefix, has own)
app.include_router(routes_explainability.router)
app.include_router(routes_readings.router)

# Factory state routes (already has /api/factory prefix) --------------------
app.include_router(factory_router)

# WebSocket routes -----------------------------------------------------------
app.include_router(ws_router)     # /ws/session/{session_id}
app.include_router(audio_router)  # /ws/audio/{case_id}


# Health check ---------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


# --------------------------------------------------------------------------- #
# Dev runner                                                                   #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.environ.get("PORT", os.environ.get("API_PORT", 8000)))
    uvicorn.run(
        "backend.main:app",
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=port,
        reload=False,
    )
