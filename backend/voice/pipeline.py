"""
backend/voice/pipeline.py — Real-Time Voice Pipeline, Barge-In & Latency Orchestrator.

Orchestrates the end-to-end streaming audio loop:
Microphone / Audio -> Deepgram STT -> Transcript Debouncer -> VoiceCopilot -> Streaming Text -> Rime TTS -> Audio Playback

Features:
- Sub-second low-latency streaming pipeline
- First-class Barge-In interruption & cancellation
- Session state preservation across conversational interruptions
- Latency profiling (STT, LLM reasoning, TTFA, and end-to-end)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from backend.operational_context.models import OperationalCase
from backend.voice.asr_client import has_speech_energy
from backend.voice.copilot import VoiceCopilot
from backend.voice.deepgram_client import DeepgramSTTClient, StreamingTranscriptDebouncer
from backend.voice.models import (
    TranscriptSegment,
    VoiceEventType,
    VoiceResponse,
    VoiceSessionContext,
    VoiceStreamEvent,
)
from backend.voice.rime_client import cancel_synthesis, synthesize_stream

logger = logging.getLogger("nova.voice.pipeline")


class VoicePipelineManager:
    """
    Orchestrates real-time audio streams, STT transcription, grounded copilot reasoning,
    TTS audio generation, and low-latency barge-in handling.
    """

    def __init__(
        self,
        stt_client: Optional[DeepgramSTTClient] = None,
        copilot: Optional[VoiceCopilot] = None,
    ) -> None:
        self.stt_client = stt_client or DeepgramSTTClient()
        self.copilot = copilot or VoiceCopilot()
        self.debouncer = StreamingTranscriptDebouncer()
        self.sessions: Dict[str, VoiceSessionContext] = {}

        # Active generation tasks per session for immediate cancellation
        self._active_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._active_tts_cancellation_events: Dict[str, asyncio.Event] = {}

        # Latency records: session_id -> {metric: value_ms}
        self.latency_records: Dict[str, Dict[str, float]] = {}

    def get_or_create_session(self, session_id: Optional[str] = None, equipment_id: str = "F-201A") -> VoiceSessionContext:
        """Retrieve existing session context or initialize a new one."""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        new_session = VoiceSessionContext(equipment_id=equipment_id)
        if session_id:
            new_session.session_id = session_id
        self.sessions[new_session.session_id] = new_session
        self.latency_records[new_session.session_id] = {}
        return new_session

    def mark_latency(self, session_id: str, marker_name: str) -> None:
        """Record high-precision timestamp for latency benchmarking."""
        if session_id not in self.latency_records:
            self.latency_records[session_id] = {}
        self.latency_records[session_id][marker_name] = time.perf_counter()

    def get_latency_metric(self, session_id: str, start_marker: str, end_marker: str) -> Optional[float]:
        """Compute elapsed milliseconds between two latency markers."""
        records = self.latency_records.get(session_id, {})
        t0 = records.get(start_marker)
        t1 = records.get(end_marker)
        if t0 is not None and t1 is not None:
            return round((t1 - t0) * 1000, 2)
        return None

    # -----------------------------------------------------------------------
    # Barge-In & Interruption Handling
    # -----------------------------------------------------------------------

    async def handle_barge_in(self, session_id: str, reason: str = "operator_speech_detected") -> VoiceStreamEvent:
        """
        Immediately interrupt and cancel ongoing TTS playback and reasoning tasks.
        Preserves session context, equipment focus, and active OperationalCase.
        """
        logger.info("Barge-in triggered for session %s (reason: %s)", session_id, reason)
        session = self.get_or_create_session(session_id)
        session.is_speaking = False
        session.is_interrupted = True

        # 1. Signal Rime TTS client-side stream cancellation
        await cancel_synthesis()

        # 2. Cancel in-flight asyncio generation tasks
        task = self._active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

        # 3. Set cancellation event
        cancel_ev = self._active_tts_cancellation_events.get(session_id)
        if cancel_ev:
            cancel_ev.set()

        event = VoiceStreamEvent(
            event_type=VoiceEventType.BARGE_IN,
            session_id=session_id,
            case_id=session.case_id,
            payload={"reason": reason, "interrupted_at": datetime.now(timezone.utc).isoformat()},
        )
        return event

    def detect_speech_interruption(self, audio_chunk: bytes, session_id: str, threshold: float = 500.0) -> bool:
        """
        Fast VAD energy check on incoming audio chunk.
        If operator speaks while NOVA is speaking, triggers barge-in.
        """
        session = self.get_or_create_session(session_id)
        if session.is_speaking and has_speech_energy(audio_chunk, threshold=threshold):
            asyncio.create_task(self.handle_barge_in(session_id, reason="vad_energy_detected"))
            return True
        return False

    # -----------------------------------------------------------------------
    # Core Stream Pipeline
    # -----------------------------------------------------------------------

    async def process_text_query_stream(
        self,
        transcript: str,
        session_id: Optional[str] = None,
        operational_case: Optional[OperationalCase] = None,
    ) -> AsyncIterator[VoiceStreamEvent]:
        """
        Process a finalized text transcript into streaming events (tokens, audio chunks).
        """
        session = self.get_or_create_session(session_id)
        sess_id = session.session_id

        self.mark_latency(sess_id, "query_received")
        yield VoiceStreamEvent(
            event_type=VoiceEventType.TRANSCRIPT_FINAL,
            session_id=sess_id,
            case_id=session.case_id,
            payload={"text": transcript},
        )

        # 1. Start Reasoning
        self.mark_latency(sess_id, "reasoning_started")
        yield VoiceStreamEvent(
            event_type=VoiceEventType.THINKING_STARTED,
            session_id=sess_id,
            case_id=session.case_id,
            payload={"query": transcript},
        )

        response: VoiceResponse = self.copilot.process_query(
            transcript=transcript,
            session_context=session,
            operational_case=operational_case,
        )
        self.mark_latency(sess_id, "reasoning_completed")

        yield VoiceStreamEvent(
            event_type=VoiceEventType.RESPONSE_STARTED,
            session_id=sess_id,
            case_id=response.case_id,
            payload={"response_id": response.response_id, "intent": response.intent},
        )

        # 2. Stream Response Text Deltas
        spoken_text = response.spoken_response
        words = spoken_text.split()
        for i in range(0, len(words), 3):
            delta = " ".join(words[i : i + 3]) + " "
            yield VoiceStreamEvent(
                event_type=VoiceEventType.RESPONSE_TEXT_DELTA,
                session_id=sess_id,
                case_id=response.case_id,
                payload={"delta": delta},
            )
            await asyncio.sleep(0.01)

        # 3. Stream TTS Audio Chunks
        self.mark_latency(sess_id, "tts_started")
        first_audio = False
        cancel_event = asyncio.Event()
        self._active_tts_cancellation_events[sess_id] = cancel_event

        try:
            yield VoiceStreamEvent(
                event_type=VoiceEventType.AUDIO_STARTED,
                session_id=sess_id,
                case_id=response.case_id,
                payload={"text": spoken_text},
            )

            async for audio_chunk in synthesize_stream(spoken_text):
                if cancel_event.is_set() or session.is_interrupted:
                    logger.info("TTS stream aborted due to barge-in on session %s", sess_id)
                    yield VoiceStreamEvent(
                        event_type=VoiceEventType.RESPONSE_CANCELLED,
                        session_id=sess_id,
                        case_id=response.case_id,
                        payload={"reason": "barge_in"},
                    )
                    return

                if not first_audio:
                    self.mark_latency(sess_id, "first_audio_byte")
                    first_audio = True

                yield VoiceStreamEvent(
                    event_type=VoiceEventType.AUDIO_CHUNK,
                    session_id=sess_id,
                    case_id=response.case_id,
                    payload={"audio_bytes_length": len(audio_chunk), "audio_chunk": audio_chunk},
                )

            self.mark_latency(sess_id, "tts_completed")
            session.is_speaking = False

            # Latency Metrics Summary
            ttfa = self.get_latency_metric(sess_id, "query_received", "first_audio_byte") or 0.0
            stt_lat = self.get_latency_metric(sess_id, "query_received", "reasoning_started") or 0.0
            reason_lat = self.get_latency_metric(sess_id, "reasoning_started", "reasoning_completed") or 0.0
            tts_lat = self.get_latency_metric(sess_id, "tts_started", "first_audio_byte") or 0.0

            yield VoiceStreamEvent(
                event_type=VoiceEventType.RESPONSE_COMPLETED,
                session_id=sess_id,
                case_id=response.case_id,
                payload={
                    "response": response.dict(),
                    "latency": {
                        "time_to_first_audio_ms": ttfa,
                        "stt_ms": stt_lat,
                        "reasoning_ms": reason_lat,
                        "tts_first_byte_ms": tts_lat,
                    },
                },
            )
        finally:
            self._active_tts_cancellation_events.pop(sess_id, None)

    async def process_audio_utterance(
        self,
        audio_bytes: bytes,
        session_id: Optional[str] = None,
        operational_case: Optional[OperationalCase] = None,
    ) -> VoiceResponse:
        """
        Process a single audio buffer: STT -> VoiceCopilot -> VoiceResponse.
        """
        session = self.get_or_create_session(session_id)
        sess_id = session.session_id

        self.mark_latency(sess_id, "audio_received")
        stt_result: TranscriptSegment = await self.stt_client.transcribe_audio_bytes(audio_bytes)
        self.mark_latency(sess_id, "stt_completed")

        transcript = stt_result.text
        if not transcript:
            transcript = "What is the current plant status?"

        response = self.copilot.process_query(
            transcript=transcript,
            session_context=session,
            operational_case=operational_case,
        )
        return response
