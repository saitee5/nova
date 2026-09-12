# NOVA Voice Copilot Architecture

> **Status:** VOICE_LAYER_READY_WITH_LIMITATIONS  
> **Last Updated:** 2026-09-12  
> **Owner:** Arushi Sachdeva (ML / RAG / Knowledge / Voice Intelligence)

---

## 1. Overview

NOVA's Voice Copilot Layer provides a real-time, hands-free operator interface to the NOVA industrial intelligence stack. The system is designed so that a furnace operator can ask natural-language questions and receive immediate, grounded, operationally-relevant answers — without ever looking away from the control panel.

The voice layer is an **intelligence interface** — it does **not** replace the underlying ML, RAG, or OperationalCase architecture.

### Design Principles

| Principle | Implementation |
|---|---|
| **Grounded, not generative** | Every response is synthesized from the active OperationalCase, ML assessments, and RAG evidence |
| **Industrial copilot, not chatbot** | Responses reference specific equipment, tags, procedures, and provenance |
| **Safety-first** | No autonomous industrial actions; human-in-the-loop confirmation for all control requests |
| **Low-latency streaming** | STT → reasoning → TTS pipeline optimized for sub-second response initiation |
| **Barge-in first-class** | Operator can interrupt NOVA at any time without losing conversational context |

---

## 2. Previous Architecture Recovered

### Components Preserved

| Component | File | Status |
|---|---|---|
| Local ASR (faster-whisper) | `backend/voice/asr_client.py` | ✅ Preserved unchanged |
| Rime TTS streaming client | `backend/voice/rime_client.py` | ✅ Preserved unchanged |
| VAD / speech energy detection | `backend/voice/asr_client.py::has_speech_energy` | ✅ Preserved unchanged |
| WebSocket audio endpoint | `backend/api/ws_audio.py` | ✅ Preserved unchanged |
| Voice REST API routes | `backend/api/routes_voice.py` | ✅ Preserved unchanged |
| ASR unit tests | `backend/voice/test_asr_client.py` | ✅ Preserved unchanged |
| Rime unit tests | `backend/voice/test_rime_client.py` | ✅ Preserved unchanged |

### Components Added

| Component | File | Purpose |
|---|---|---|
| Voice data contracts | `backend/voice/models.py` | VoiceSessionContext, VoiceResponse, VoiceStreamEvent, TranscriptSegment |
| Deepgram STT client | `backend/voice/deepgram_client.py` | Deepgram Nova-2 REST transcription + local ASR fallback + StreamingTranscriptDebouncer |
| Voice Copilot intelligence | `backend/voice/copilot.py` | Grounded reasoning engine with intent classification and OperationalCase integration |
| Voice pipeline manager | `backend/voice/pipeline.py` | Streaming orchestrator with barge-in, latency profiling, and session management |
| Voice copilot test suite | `backend/voice/test_voice_copilot.py` | 65+ tests covering all requirements |

### Components Upgraded

| Component | Change |
|---|---|
| `backend/voice/__init__.py` | Extended exports to include all new voice layer components |
| `backend/config.py` | Added Deepgram and Rime configuration settings |

### Components Removed

None. All previous voice implementation was preserved.

---

## 3. Architecture

### End-to-End Pipeline

```
Microphone / Audio Input
        ↓
┌─────────────────────────────┐
│   Deepgram STT (Nova-2)     │ ← Primary provider
│   OR faster-whisper (local) │ ← Automatic fallback
└─────────────────────────────┘
        ↓
┌─────────────────────────────┐
│ StreamingTranscriptDebouncer│ ← Stabilizes partials, prevents jitter
└─────────────────────────────┘
        ↓
┌─────────────────────────────┐
│    VoiceCopilot Engine      │
│  ┌───────────────────────┐  │
│  │ Intent Classification │  │
│  │ Context Resolution    │  │
│  │ Grounded Reasoning    │  │
│  │ Spoken Output Cleaning│  │
│  └───────────────────────┘  │
│                             │
│  Data Sources:              │
│  • OperationalCase          │
│  • ML Assessments (×4)      │
│  • RAG Knowledge Evidence   │
│  • Safety Context           │
│  • Maintenance Context      │
│  • Permit Context           │
│  • Incident History         │
└─────────────────────────────┘
        ↓
┌─────────────────────────────┐
│     VoiceResponse           │ ← Canonical structured response
│  (spoken text + evidence    │
│   + ML context + provenance │
│   + limitations + action)   │
└─────────────────────────────┘
        ↓
┌─────────────────────────────┐
│     Rime TTS (mist-v3)      │ ← Streaming audio synthesis
└─────────────────────────────┘
        ↓
   Audio Playback (WebSocket)
```

### Streaming Event Lifecycle

```
TRANSCRIPT_PARTIAL → TRANSCRIPT_FINAL → THINKING_STARTED →
RESPONSE_STARTED → RESPONSE_TEXT_DELTA (×N) →
AUDIO_STARTED → AUDIO_CHUNK (×N) → RESPONSE_COMPLETED
```

Barge-in interrupts emit: `BARGE_IN → RESPONSE_CANCELLED`

---

## 4. Deepgram STT Integration

- **Provider:** Deepgram Nova-2 (REST `/v1/listen`)
- **Fallback:** Local faster-whisper (`small.en`, CPU, int8)
- **Partial transcript support:** Via StreamingTranscriptDebouncer
- **Endpointing:** Configurable (default 300ms)
- **API key:** Environment variable `DEEPGRAM_API_KEY`
- **Health check:** `DeepgramSTTClient.health_check()` returns structured status

### Fallback Chain

```
1. Deepgram Nova-2 API (if DEEPGRAM_API_KEY is set)
   ↓ (on failure)
2. Local faster-whisper ASR (if model installed)
   ↓ (on failure)
3. Empty transcript → default status query
```

---

## 5. Rime TTS Integration

- **Provider:** Rime AI
- **Live model:** `mist-v3` (low-latency conversational)
- **Debrief model:** `coda` (longer-form synthesis)
- **Speaker:** `astra` (configurable)
- **Streaming:** HTTP chunked transfer → WebSocket binary frames
- **Cancellation:** Client-side stream abort via `cancel_synthesis()`
- **API key:** Environment variable `RIME_API_KEY`

---

## 6. Barge-In Implementation

Barge-in is a **first-class feature**. The operator can interrupt NOVA at any time.

### Mechanism

1. **VAD Detection:** `has_speech_energy()` checks incoming audio RMS amplitude
2. **TTS Cancellation:** `cancel_synthesis()` sets a cancellation event and closes the HTTP response stream
3. **Task Cancellation:** In-flight asyncio reasoning tasks are cancelled
4. **Context Preservation:** Session equipment, case ID, topic, and history are preserved
5. **New Query Processing:** Interrupted question is stored as `unresolved_question`

### What Happens on Barge-In

```
NOVA speaking: "The furnace COT is above the normal operating—"
Operator:      "Wait, is this dangerous?"

1. VAD detects speech energy during NOVA playback
2. cancel_synthesis() aborts Rime stream immediately
3. Active generation task is cancelled
4. Session context preserved (case_id, equipment_id, topic)
5. New transcript processed through VoiceCopilot
6. New response generated from same OperationalCase
7. BARGE_IN event emitted
8. New audio stream begins
```

---

## 7. Conversational Context

### VoiceSessionContext

Bounded, lightweight session state:

| Field | Purpose |
|---|---|
| `session_id` | Unique session identifier |
| `case_id` | Active OperationalCase ID |
| `equipment_id` | Current target equipment |
| `unit_area` | Plant operating area |
| `active_topic` | Current conversation subject |
| `latest_transcript` | Most recent operator utterance |
| `recent_operator_questions` | Bounded list (max 5) |
| `recent_nova_responses` | Bounded list (max 5) |
| `unresolved_question` | Interrupted question |
| `is_speaking` | TTS active flag |
| `is_interrupted` | Barge-in flag |

History is bounded to 5 turns to maintain operational relevance without unbounded growth.

---

## 8. Intelligence Routing

### Intent Categories

| Intent | Example Queries | Data Sources |
|---|---|---|
| `SITUATION` | "What's happening?", "What's wrong?" | Observations, alarms, anomaly detector |
| `DIAGNOSTIC` | "Why is COT high?", "What fault?" | FaultClassifier, AnomalyDetector, COTPredictor |
| `SAFETY` | "Is this dangerous?", "Need LOTO?" | Safety context, permit context |
| `MAINTENANCE` | "Last decoke?", "Work orders?" | Maintenance context |
| `EVIDENCE` | "What does the SOP say?" | Knowledge evidence (RAG) |
| `HISTORICAL` | "Seen this before?" | Incident context |
| `FOLLOW_UP` | "Why?", "How high?" | Resolves against active_topic |
| `ACTION_REQUEST` | "Shut it down" | Generates confirmation gate |

---

## 9. OperationalCase Integration

The VoiceCopilot resolves every query against the active OperationalCase:

```
OperationalCase
├── observations        → COT, pressure, flow values
├── alarms              → Active alarm states
├── ml_assessments      → 4 model predictions
│   ├── ProcessAnomalyDetector
│   ├── ProcessFaultClassifier
│   ├── FurnaceCOTPredictor
│   └── TubeTemperaturePredictor
├── knowledge_evidence  → SOP, engineering docs
├── safety_context      → PPE, LOTO, hazard controls
├── maintenance_context → Work orders, inspection history
├── permit_context      → Hot work, confined space permits
├── incident_context    → Historical incident reports
├── risk_indicators     → Explicit risk evaluations
└── limitations         → Synthetic data notices, caveats
```

---

## 10. ML Model Provenance in Voice

All four NOVA models are accessible through voice queries:

| Model | Voice Exposure | Special Handling |
|---|---|---|
| ProcessAnomalyDetector v1.1.0 | Anomaly state, score | Standard |
| ProcessFaultClassifier v1.1.0 | Fault diagnosis, confidence | Standard |
| FurnaceCOTPredictor v1.1.0 | COT prediction | Standard |
| TubeTemperaturePredictor v1.0.0-demo | **Surrogate estimate only** | **Mandatory disclaimer** |

### TubeTemperaturePredictor — Mandatory Voice Behavior

When the operator asks about tube temperature / TMT / skin temp:

- ✅ "The Tube Temperature Predictor estimates 995°C using a physics-informed synthetic surrogate."
- ✅ "This target is not industrially validated and must not be used as safety instrumentation."
- ❌ Never says "measured tube temperature"
- ❌ Never says "actual TMT"
- ❌ Never calls it a "coking detector"

---

## 11. Safety-Critical Voice Behavior

### Industrial Action Safety Gate

Voice **never** executes plant actions autonomously:

```python
# Operator: "Shut the furnace down"
VoiceResponse(
    requires_confirmation=True,
    action_request={
        "action": "FURNACE_EMERGENCY_SHUTDOWN",
        "equipment_id": "F-201A",
        "requires_human_confirmation": True,
    }
)
```

### Safety Distinctions

| Distinction | Voice Behavior |
|---|---|
| Measured vs. inferred state | Explicitly separates telemetry from model output |
| Model prediction vs. observation | States model name and version |
| Applicable procedure vs. active permit | "No active permit is currently authorized" |
| Historical vs. current incident | References incident document IDs |
| Recommendation vs. authorized action | Always requires human confirmation |

---

## 12. RAG-Grounded Voice Answers

Knowledge queries are resolved against the existing RAG infrastructure:

```
Operator: "What does the SOP say?"
→ Retrieve knowledge_evidence from OperationalCase
→ Reference document ID, section, version
→ Spoken: "Operating Manual OPM-FLT-008 specifies that when COT exceeds 885°C..."
```

### Citation Provenance (retained internally)

```
document_id, chunk_id, source, section, version, content_hash, evidence_type
```

Citations are not read aloud but are preserved in VoiceResponse.evidence for frontend display.

---

## 13. Latency Architecture

### Measurement Points

```
audio_received → stt_completed → reasoning_started →
reasoning_completed → tts_started → first_audio_byte → tts_completed
```

### Latency Metrics Reported

| Metric | Measurement |
|---|---|
| STT latency | `query_received → reasoning_started` |
| Reasoning latency | `reasoning_started → reasoning_completed` |
| TTS first byte | `tts_started → first_audio_byte` |
| Time-to-first-audio | `query_received → first_audio_byte` |
| End-to-end | `query_received → tts_completed` |

### Optimization Strategies

- Streaming STT (Deepgram endpointing)
- Partial transcript debouncing (prevents premature LLM calls)
- Synchronous copilot reasoning (no LLM API call — deterministic grounding)
- Streaming TTS (HTTP chunked transfer)
- Connection reuse (httpx AsyncClient)
- Bounded context (max 5 turns)
- Cancellation support (asyncio.Task + cancel_event)

### Latency Benchmark Notes

The previous implementation referenced ~100ms latency. The current voice layer does not make an external LLM API call during reasoning (the VoiceCopilot uses deterministic grounding against the OperationalCase), so reasoning latency is sub-millisecond. End-to-end latency depends on Deepgram STT and Rime TTS network round-trips.

**No fabricated latency benchmarks are claimed.** Actual latency must be measured against live Deepgram/Rime endpoints.

---

## 14. Failure Modes

| Failure | Behavior |
|---|---|
| Deepgram unavailable | Falls back to local faster-whisper ASR |
| faster-whisper unavailable | Returns empty transcript → default status query |
| Rime unavailable | Text response returned; no audio |
| OperationalCase build failure | Fallback case with minimal telemetry |
| ML model unavailable | `MODEL_NOT_AVAILABLE` status preserved |
| Knowledge evidence empty | Response states evidence could not be retrieved |
| Network disconnect | WebSocket disconnect handled cleanly |
| Barge-in during generation | Immediate cancellation of TTS + reasoning tasks |

---

## 15. Security

| Requirement | Implementation |
|---|---|
| Deepgram API key | `DEEPGRAM_API_KEY` environment variable |
| Rime API key | `RIME_API_KEY` environment variable |
| LLM API key | `LLM_API_KEY` environment variable |
| No hardcoded secrets | All credentials via pydantic-settings / `.env` |
| No raw audio logging | Audio bytes not logged by default |
| Credential isolation | Keys never appear in response payloads |

---

## 16. Testing

### Test Suite Structure

| Test File | Coverage |
|---|---|
| `test_asr_client.py` | VAD energy detection, transcription, event loop non-blocking |
| `test_rime_client.py` | Streaming synthesis, error handling, health check, cancellation |
| `test_voice_copilot.py` | 65+ tests across 17 test classes |

### Test Categories (test_voice_copilot.py)

1. VoiceSessionContext bounded history
2. TranscriptSegment contracts
3. VoiceStreamEvent lifecycle
4. VoiceResponse contract validation
5. Intent classification (all 8 categories)
6. Grounded response synthesis
7. Tube Temperature surrogate compliance (4 tests)
8. Action request safety gate (3 tests)
9. Provenance & ML context preservation
10. StreamingTranscriptDebouncer stabilization
11. DeepgramSTTClient configuration & fallback
12. VoicePipelineManager session lifecycle
13. Streaming pipeline event flow
14. Demo conversation scenarios (4 multi-turn conversations)
15. Failure handling (missing models, empty evidence)
16. Clean spoken output formatting
17. Audio processing integration

---

## 17. Configuration

### Environment Variables

```env
# STT
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your_key_here
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=en
DEEPGRAM_API_BASE_URL=https://api.deepgram.com

# Local ASR fallback
ASR_MODEL=small.en

# TTS
TTS_PROVIDER=rime
RIME_API_KEY=your_key_here
RIME_MODEL_LIVE=mist-v3
RIME_MODEL_DEBRIEF=coda
RIME_SPEAKER=astra
RIME_API_BASE_URL=https://users.rime.ai
```

---

## 18. Known Limitations

1. **VoiceCopilot uses deterministic grounding, not LLM generation** — responses are template-synthesized from OperationalCase data, not generated by an LLM. This ensures safety and determinism but limits conversational flexibility.
2. **No real-time Deepgram WebSocket streaming** — current implementation uses REST `/v1/listen` for pre-recorded audio buffers. WebSocket streaming would reduce STT latency further.
3. **Single-session TTS cancellation** — `cancel_synthesis()` uses a global cancellation event, not per-session. Multi-concurrent-session barge-in requires per-session refactoring.
4. **All telemetry is synthetic demo data** — voice responses reference demo OperationalCase scenarios.
5. **TubeTemperaturePredictor is a physics-informed synthetic surrogate** — not industrially validated.
6. **Latency benchmarks not measured** — actual end-to-end latency depends on network round-trips to Deepgram and Rime APIs.

---

## 19. File Inventory

| File | Purpose |
|---|---|
| `backend/voice/__init__.py` | Package exports |
| `backend/voice/asr_client.py` | Local faster-whisper ASR (preserved) |
| `backend/voice/rime_client.py` | Rime TTS streaming client (preserved) |
| `backend/voice/deepgram_client.py` | Deepgram STT + fallback + debouncer |
| `backend/voice/models.py` | Data contracts (VoiceResponse, VoiceSessionContext, VoiceStreamEvent) |
| `backend/voice/copilot.py` | Grounded intelligence engine |
| `backend/voice/pipeline.py` | Streaming pipeline manager |
| `backend/voice/test_asr_client.py` | ASR tests (preserved) |
| `backend/voice/test_rime_client.py` | Rime tests (preserved) |
| `backend/voice/test_voice_copilot.py` | Comprehensive voice layer tests |
| `backend/api/routes_voice.py` | Voice REST API endpoints (preserved) |
| `backend/api/ws_audio.py` | WebSocket audio streaming (preserved) |
| `backend/config.py` | Voice provider configuration |
| `docs/VOICE_ARCHITECTURE.md` | This document |
