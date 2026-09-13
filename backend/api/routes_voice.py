"""backend/api/routes_voice.py — Full Rime voice integration.

Endpoints:
  GET  /api/voice/{case_id}/status    → VoiceStatus (latency marks, transcript)
  POST /api/voice/speak               → Trigger TTS for a case (streams via WS)
  POST /api/voice/cancel              → Barge-in: cancel current synthesis
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Query, HTTPException
from pydantic import BaseModel

from backend.voice.rime_client import cancel_synthesis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

# In-memory transcript store (case_id → list of transcript lines)
_transcripts: dict[str, list[dict[str, Any]]] = {}
_latency_store: dict[str, dict[str, float]] = {}


class VoiceStatus(BaseModel):
    case_id: str
    transcript: list[dict]
    latency_marks: dict[str, float]
    is_speaking: bool = False


class SpeakRequest(BaseModel):
    case_id: str
    text: str
    model: str | None = None


class SpeakResult(BaseModel):
    case_id: str
    queued: bool
    text: str


class CancelResult(BaseModel):
    case_id: str
    cancelled: bool


def record_utterance(case_id: str, text: str, speaker: str = "NOVA", latency_ms: float | None = None) -> None:
    """Append a transcript entry for a case."""
    if case_id not in _transcripts:
        _transcripts[case_id] = []
    _transcripts[case_id].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "speaker": speaker,
        "text": text,
        "latency_ms": latency_ms,
    })


@router.get("/{case_id}/status", response_model=VoiceStatus)
async def get_voice_status(case_id: str) -> VoiceStatus:
    """Return voice transcript and latency marks for a case."""
    from backend.api.ws_audio import get_latency_ms, _latency_marks
    latency = {}
    for key in ["speak_triggered", "first_audio_byte", "barge_in", "stream_complete"]:
        val = get_latency_ms(case_id, "speak_triggered", key) if key != "speak_triggered" else None
        if val is not None:
            latency[f"rime_{key}_ms"] = val

    return VoiceStatus(
        case_id=case_id,
        transcript=_transcripts.get(case_id, []),
        latency_marks=latency,
    )


@router.post("/speak", response_model=SpeakResult)
async def trigger_speak(body: SpeakRequest, bg: BackgroundTasks) -> SpeakResult:
    """Trigger TTS synthesis for a case. Audio streams to WS /ws/audio/{case_id}."""
    from backend.api.ws_audio import speak_to_case

    record_utterance(body.case_id, body.text)
    bg.add_task(speak_to_case, body.case_id, body.text, body.model)
    return SpeakResult(case_id=body.case_id, queued=True, text=body.text)


@router.post("/cancel", response_model=CancelResult)
async def cancel_voice(body: dict | None = None) -> CancelResult:
    """Barge-in: cancel in-flight Rime synthesis."""
    case_id = body.get("case_id", "") if body else ""
    await cancel_synthesis()
    return CancelResult(case_id=case_id, cancelled=True)


@router.get("/stream")
@router.post("/stream")
async def stream_tts_audio(
    text: str | None = None,
    model: str | None = None,
    case_id: str | None = "live-copilot",
    body: SpeakRequest | None = None,
):
    """Direct HTTP audio stream for HTML5 Audio playback via Rime TTS."""
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    from backend.voice.rime_client import synthesize_stream
    from backend.api.ws_audio import mark_latency

    spoken_text = (body.text if body else None) or text or ""
    if not spoken_text.strip():
        raise HTTPException(status_code=400, detail="Text parameter is required")

    model_id = (body.model if body else None) or model or None
    active_case = (body.case_id if body else None) or case_id or "live-copilot"

    record_utterance(active_case, spoken_text)
    mark_latency(active_case, "speak_triggered")
    first_chunk = True

    async def _audio_gen():
        nonlocal first_chunk
        try:
            async for chunk in synthesize_stream(spoken_text, model=model_id):
                if first_chunk:
                    mark_latency(active_case, "first_audio_byte")
                    first_chunk = False
                yield chunk
            mark_latency(active_case, "stream_complete")
        except Exception as exc:
            logger.warning("Direct TTS streaming failed: %s", exc)

    return StreamingResponse(
        _audio_gen(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Type": "audio/mpeg",
            "Accept-Ranges": "bytes",
        },
    )


@router.post("/transcribe")
async def transcribe_audio_file(
    audio: UploadFile = File(...),
):
    """Transcribe an uploaded audio file (WebM, WAV, MP3, OGG) using faster-whisper."""
    import os
    import tempfile
    from backend.voice.asr_client import transcribe_utterance

    suffix = ".webm"
    if audio.filename and "." in audio.filename:
        suffix = "." + audio.filename.rsplit(".", 1)[-1].lower()

    content = await audio.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transcript = await transcribe_utterance(tmp_path)
        logger.info("Transcribed audio upload (%d bytes) -> '%s'", len(content), transcript)
        return {"transcript": transcript or ""}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
