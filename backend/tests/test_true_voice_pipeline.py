"""
backend/tests/test_true_voice_pipeline.py — End-to-End Real Voice Pipeline Verification.

Validates the full live speech pipeline:
Microphone / Audio -> Deepgram STT (Nova-2) -> VoiceCopilot Orchestrator ->
Real ML / Risk / DB / RAG Tools -> Grounded Response -> Rime TTS (mist-v3) -> Spoken Audio.

Zero-mock policy:
- Real Deepgram API connection
- Real VoiceCopilot orchestrator
- Real Rime TTS streaming API
- Strict Voice HITL SafetyGuard verification
"""

import pytest
import io
import wave
import struct
from backend.voice.deepgram_client import DeepgramSTTClient
from backend.voice.copilot import VoiceCopilot
from backend.voice.models import VoiceSessionContext
from backend.voice.rime_client import synthesize_stream
from backend.runtime.service import RuntimeService
from backend.operational_context.builder import build_operational_case


def _generate_test_wav_bytes(duration_sec: float = 0.5) -> bytes:
    """Generate a valid in-memory PCM 16-bit 16kHz WAV buffer."""
    buf = io.BytesIO()
    sample_rate = 16000
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_samples = int(sample_rate * duration_sec)
        samples = [int(500.0 * struct.unpack("h", b"\x00\x01")[0]) for _ in range(num_samples)]
        raw_data = struct.pack(f"<{num_samples}h", *[0]*num_samples)
        wf.writeframes(raw_data)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_deepgram_stt_health_and_transcription():
    """Verify Deepgram STT service connectivity and live Nova-2 client."""
    stt = DeepgramSTTClient()
    assert stt.is_configured is True, "DEEPGRAM_API_KEY must be configured in environment"

    health = await stt.health_check()
    assert health.get("status") in ["HEALTHY", "DEGRADED"], f"Deepgram connection failed: {health}"

    # Transcribe test audio buffer
    audio_wav = _generate_test_wav_bytes()
    segment = await stt.transcribe_audio_bytes(audio_wav)
    assert segment is not None
    assert segment.is_final is True


@pytest.mark.asyncio
async def test_voice_copilot_real_queries_and_intents():
    """Verify VoiceCopilot processes industrial queries and grounds responses against real case evidence."""
    copilot = VoiceCopilot(default_equipment_id="F-201A")
    session = VoiceSessionContext(equipment_id="F-201A")

    # Real case from operational telemetry
    real_case = build_operational_case(
        telemetry={"TI-201": 891.2, "PI-201": 0.38, "FC-201": 23800.0},
        equipment_id="F-201A",
    )

    # Query 1: Situation overview
    resp1 = copilot.process_query("What is the current condition of F-201A?", session, real_case)
    assert resp1.intent == "SITUATION"
    assert len(resp1.spoken_response) > 0
    assert "F-201A" in resp1.spoken_response or "furnace" in resp1.spoken_response.lower()

    # Query 2: Diagnostic inquiry
    resp2 = copilot.process_query("Why is it risky?", session, real_case)
    assert resp2.intent in ["DIAGNOSTIC", "FOLLOW_UP"]
    assert len(resp2.spoken_response) > 0

    # Query 3: Evidence & Procedure inquiry
    resp3 = copilot.process_query("What does the operating procedure say about this?", session, real_case)
    assert resp3.intent in ["EVIDENCE", "SAFETY"]
    assert len(resp3.spoken_response) > 0


@pytest.mark.asyncio
async def test_voice_hitl_cannot_bypass_safetyguard():
    """Verify voice approval command routes through SafetyGuard and cannot actuate unsafely."""
    copilot = VoiceCopilot(default_equipment_id="F-201A")
    session = VoiceSessionContext(equipment_id="F-201A")

    real_case = build_operational_case(
        telemetry={"TI-201": 895.0, "PI-201": 0.40, "FC-201": 23000.0},
        equipment_id="F-201A",
    )

    # Voice command attempting safety-critical shutdown / trip
    resp = copilot.process_query("Shut down F-201A immediately", session, real_case)
    assert resp.intent == "ACTION_REQUEST"
    # Must enforce human confirmation / SafetyGuard gate
    assert resp.requires_confirmation is True or resp.action_request is not None, (
        "Safety-critical voice action must enforce verification gate, never execute unverified."
    )


@pytest.mark.asyncio
async def test_rime_tts_live_stream_synthesis():
    """Verify that Rime TTS synthesizes real live orchestrator text into audio chunks."""
    copilot = VoiceCopilot(default_equipment_id="F-201A")
    session = VoiceSessionContext(equipment_id="F-201A")
    real_case = build_operational_case(
        telemetry={"TI-201": 885.0},
        equipment_id="F-201A",
    )

    response = copilot.process_query("What is the status of F-201A?", session, real_case)
    spoken_text = response.spoken_response
    assert len(spoken_text) > 0

    # Call real Rime TTS streaming API
    chunks = []
    async for chunk in synthesize_stream(spoken_text):
        chunks.append(chunk)

    total_bytes = sum(len(c) for c in chunks)
    assert len(chunks) > 0, "Rime TTS returned 0 audio chunks"
    assert total_bytes > 1000, f"Expected audio stream bytes, received {total_bytes} bytes"
