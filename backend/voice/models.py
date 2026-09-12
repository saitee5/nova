"""
backend/voice/models.py — Data Contracts and Event Schemas for NOVA Voice Copilot Layer.

Defines:
- VoiceSessionContext (bounded operational conversational state)
- VoiceResponse (canonical structured response model with citations & provenance)
- VoiceEventType & VoiceStreamEvent (streaming lifecycle event contracts)
- TranscriptSegment (partial and final transcript representations)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.knowledge.models import CanonicalEvidence


class VoiceEventType(str, Enum):
    """Lifecycle events emitted during streaming voice copilot interactions."""
    TRANSCRIPT_PARTIAL = "TRANSCRIPT_PARTIAL"
    TRANSCRIPT_FINAL = "TRANSCRIPT_FINAL"
    THINKING_STARTED = "THINKING_STARTED"
    RESPONSE_STARTED = "RESPONSE_STARTED"
    RESPONSE_TEXT_DELTA = "RESPONSE_TEXT_DELTA"
    AUDIO_STARTED = "AUDIO_STARTED"
    AUDIO_CHUNK = "AUDIO_CHUNK"
    BARGE_IN = "BARGE_IN"
    RESPONSE_CANCELLED = "RESPONSE_CANCELLED"
    RESPONSE_COMPLETED = "RESPONSE_COMPLETED"
    ERROR = "ERROR"


class VoiceStreamEvent(BaseModel):
    """Streaming event payload transmitted across WebSockets or SSE channels."""
    event_id: str = Field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}",
        description="Unique event ID",
    )
    event_type: VoiceEventType = Field(..., description="Type of voice event")
    session_id: str = Field(..., description="Active voice session identifier")
    case_id: Optional[str] = Field(default=None, description="Associated operational case ID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event UTC timestamp",
    )
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event data payload")


class TranscriptSegment(BaseModel):
    """Speech-to-text transcript output segment from Deepgram or local ASR."""
    text: str = Field(..., description="Transcribed speech text")
    is_final: bool = Field(default=False, description="True if transcript is finalized/endpointed")
    confidence: float = Field(default=1.0, description="Transcription confidence [0.0, 1.0]")
    speech_final: bool = Field(default=False, description="Deepgram speech_final flag indicating utterance completion")
    start_time: float = Field(default=0.0, description="Start timestamp in seconds")
    end_time: float = Field(default=0.0, description="End timestamp in seconds")
    speaker: Optional[int] = Field(default=None, description="Diarized speaker index if available")


class VoiceSessionContext(BaseModel):
    """
    Lightweight, bounded conversational session context.
    Maintains operational continuity across multi-turn operator inquiries without unbound history.
    """
    session_id: str = Field(
        default_factory=lambda: f"VOICE-SESS-{uuid.uuid4().hex[:8].upper()}",
        description="Unique voice session identifier",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last interaction timestamp",
    )
    case_id: Optional[str] = Field(default=None, description="Active OperationalCase ID")
    equipment_id: str = Field(default="F-201A", description="Current target equipment tag")
    unit_area: str = Field(default="UNIT-CRACK-01", description="Current operating unit area")
    active_topic: str = Field(default="general_operations", description="Active subject (e.g. cot_excursion, decoking)")
    latest_transcript: str = Field(default="", description="Most recent transcribed operator utterance")
    recent_operator_questions: List[str] = Field(default_factory=list, description="Bounded list of recent questions")
    recent_nova_responses: List[str] = Field(default_factory=list, description="Bounded list of recent responses")
    unresolved_question: Optional[str] = Field(default=None, description="Operator question interrupted by barge-in")
    is_speaking: bool = Field(default=False, description="True if TTS audio is actively streaming")
    is_interrupted: bool = Field(default=False, description="True if latest response was barged-in")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session-level metadata")

    def add_turn(self, question: str, response: str, max_turns: int = 5) -> None:
        """Append a conversational turn and maintain bounded history."""
        self.recent_operator_questions.append(question)
        self.recent_nova_responses.append(response)
        if len(self.recent_operator_questions) > max_turns:
            self.recent_operator_questions = self.recent_operator_questions[-max_turns:]
        if len(self.recent_nova_responses) > max_turns:
            self.recent_nova_responses = self.recent_nova_responses[-max_turns:]
        self.updated_at = datetime.now(timezone.utc)
        self.is_interrupted = False


class VoiceResponse(BaseModel):
    """
    Canonical structured voice copilot response model.
    Contains grounded spoken text, structured citations, ML predictions, and safety confirmation gates.
    """
    response_id: str = Field(
        default_factory=lambda: f"vresp_{uuid.uuid4().hex[:10]}",
        description="Unique response identifier",
    )
    session_id: str = Field(..., description="Associated voice session ID")
    case_id: Optional[str] = Field(default=None, description="Associated operational case ID")
    transcript: str = Field(..., description="Transcribed operator query")
    intent: str = Field(..., description="Classified intent (e.g. SITUATION, DIAGNOSTIC, SAFETY, MAINTENANCE)")
    spoken_response: str = Field(..., description="Cleaned, conversational text to be spoken aloud via TTS")
    detailed_text: Optional[str] = Field(default=None, description="Expanded markdown text for screen displays")
    evidence: List[CanonicalEvidence] = Field(
        default_factory=list,
        description="Retrieved authoritative engineering and incident evidence items",
    )
    ml_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current ML model assessments and predictions",
    )
    confidence: Optional[float] = Field(default=None, description="Confidence score if supported by model")
    requires_confirmation: bool = Field(
        default=False,
        description="True if query requests an industrial control action requiring human confirmation",
    )
    action_request: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured action proposal for human-in-the-loop authorization (e.g. FURNACE_SHUTDOWN)",
    )
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete audit provenance tracing all upstream models and documents",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Explicit operational caveats, synthetic surrogate notices, and safety constraints",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="End-to-end processing latency in milliseconds",
    )
