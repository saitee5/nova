"""backend.voice package — NOVA Voice Copilot Layer.

Exports:
- Legacy ASR (faster-whisper) and Rime TTS clients
- VoiceCopilot intelligence engine
- VoicePipelineManager streaming orchestrator
- DeepgramSTTClient with local fallback
- Voice data contracts (models, events, sessions)
"""

from backend.voice.asr_client import (
    get_model,
    has_speech_energy,
    transcribe_stream,
    transcribe_utterance,
)
from backend.voice.copilot import VoiceCopilot
from backend.voice.deepgram_client import DeepgramSTTClient, StreamingTranscriptDebouncer
from backend.voice.models import (
    TranscriptSegment,
    VoiceEventType,
    VoiceResponse,
    VoiceSessionContext,
    VoiceStreamEvent,
)
from backend.voice.pipeline import VoicePipelineManager
from backend.voice.rime_client import (
    AUDIO_FORMAT,
    RimeClientError,
    cancel_synthesis,
    health_check,
    synthesize_debrief,
    synthesize_stream,
)

__all__ = [
    # Legacy ASR
    "get_model",
    "has_speech_energy",
    "transcribe_stream",
    "transcribe_utterance",
    # Rime TTS
    "AUDIO_FORMAT",
    "RimeClientError",
    "cancel_synthesis",
    "health_check",
    "synthesize_debrief",
    "synthesize_stream",
    # Deepgram STT
    "DeepgramSTTClient",
    "StreamingTranscriptDebouncer",
    # Data Contracts
    "TranscriptSegment",
    "VoiceEventType",
    "VoiceResponse",
    "VoiceSessionContext",
    "VoiceStreamEvent",
    # Intelligence & Pipeline
    "VoiceCopilot",
    "VoicePipelineManager",
]
