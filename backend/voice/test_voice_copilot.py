"""
backend/voice/test_voice_copilot.py — Comprehensive Test Suite for the NOVA Voice Copilot Layer.

Covers:
- VoiceCopilot grounded reasoning across all intent categories
- VoiceSessionContext bounded turn management
- VoicePipelineManager session lifecycle, barge-in, and latency tracking
- DeepgramSTTClient API + fallback pathways
- StreamingTranscriptDebouncer stabilization
- Streaming event contracts and pipeline flow
- Demo conversation scenarios (matching OperationalCase SCENARIO-1 to SCENARIO-4)
- Safety / provenance / surrogate compliance
- Failure handling (missing model, unavailable RAG, etc.)
- VoiceResponse / VoiceStreamEvent contract validation

Run with:
    python -m pytest backend/voice/test_voice_copilot.py -v
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.knowledge.models import CanonicalEvidence, Citation, EvidenceType
from backend.operational_context.models import (
    CasePriority,
    CaseStatus,
    MLAssessmentSummary,
    Observation,
    OperationalCase,
)
from backend.operational_context.scenarios import ScenarioBuilder
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


# ======================================================================
# Fixtures
# ======================================================================


def _make_demo_evidence(doc_id: str = "DOC-DEMO-SOP-F201-001", section: str = "3.1") -> CanonicalEvidence:
    """Create a minimal CanonicalEvidence for testing."""
    return CanonicalEvidence(
        evidence_type=EvidenceType.OPERATIONAL_PROCEDURE,
        source_title=f"Demo SOP {doc_id}",
        content="If COT exceeds 885°C, reduce fuel gas firing by 5-10%.",
        citation=Citation(
            document_id=doc_id,
            section=section,
            version="v1.0-demo",
        ),
    )


def _make_operational_case() -> OperationalCase:
    """Build a realistic OperationalCase for voice testing."""
    try:
        return ScenarioBuilder.build_case_from_scenario("SCENARIO-1-HIGH-COT")
    except Exception:
        return OperationalCase(
            equipment_id="F-201A",
            equipment_type="furnace",
            unit_area="UNIT-CRACK-01",
            title="High COT Thermal Excursion",
            summary="F-201A COT exceeds operating envelope at 888.5°C",
            overall_state="ABNORMAL",
            status=CaseStatus.EVIDENCE_GATHERED,
            priority=CasePriority.HIGH,
            observations=[
                Observation(tag="TI-201", value=888.5, unit="°C", description="Coil Outlet Temperature"),
                Observation(tag="PI-201", value=0.34, unit="MPa", description="Fuel Gas Header Pressure"),
                Observation(tag="FC-201", value=24000.0, unit="kg/h", description="Naphtha Feed Rate"),
            ],
            alarms=[{"tag": "TI-201-HAH", "type": "HIGH_HIGH", "description": "COT high alarm"}],
            ml_assessments={
                "ProcessAnomalyDetector": MLAssessmentSummary(
                    model_name="ProcessAnomalyDetector",
                    model_version="v1.1.0",
                    is_available=True,
                    predicted_value=True,
                    score=0.87,
                    summary="Abnormal process covariance detected",
                ),
                "ProcessFaultClassifier": MLAssessmentSummary(
                    model_name="ProcessFaultClassifier",
                    model_version="v1.1.0",
                    is_available=True,
                    predicted_value="Cooling Water Disturbance / High Firing",
                    confidence=0.82,
                    summary="Fault 4: CW disturbance",
                ),
                "FurnaceCOTPredictor": MLAssessmentSummary(
                    model_name="FurnaceCOTPredictor",
                    model_version="v1.1.0",
                    is_available=True,
                    predicted_value=887.3,
                    summary="COT prediction consistent with telemetry",
                ),
                "TubeTemperaturePredictor": MLAssessmentSummary(
                    model_name="TubeTemperaturePredictor",
                    model_version="v1.0.0-demo",
                    is_available=True,
                    predicted_value=995.0,
                    target_type="physics_informed_synthetic_surrogate",
                    industrial_validation=False,
                    summary="Synthetic surrogate estimate — NOT measured TMT",
                ),
            },
            knowledge_evidence=[_make_demo_evidence()],
            safety_context=[_make_demo_evidence("DOC-DEMO-SAF-GEN-013", "2.4")],
            maintenance_context=[_make_demo_evidence("DOC-DEMO-MNT-HIS-022", "4.1")],
            permit_context=[_make_demo_evidence("DOC-DEMO-PMT-SOP-025", "1.2")],
            incident_context=[_make_demo_evidence("DOC-DEMO-INC-F201-023", "5.3")],
            limitations=[
                "All telemetry is synthetic demo data.",
                "TubeTemperaturePredictor uses physics_informed_synthetic_surrogate target.",
            ],
        )


@pytest.fixture
def copilot() -> VoiceCopilot:
    return VoiceCopilot(default_equipment_id="F-201A")


@pytest.fixture
def session() -> VoiceSessionContext:
    return VoiceSessionContext(equipment_id="F-201A")


@pytest.fixture
def case() -> OperationalCase:
    return _make_operational_case()


@pytest.fixture
def pipeline() -> VoicePipelineManager:
    stt = DeepgramSTTClient(api_key="mock-test-key")
    copilot = VoiceCopilot()
    return VoicePipelineManager(stt_client=stt, copilot=copilot)


# ======================================================================
# 1. VoiceSessionContext Tests
# ======================================================================


class TestVoiceSessionContext:
    """Bounded conversational session state management."""

    def test_session_has_auto_generated_id(self, session: VoiceSessionContext) -> None:
        assert session.session_id.startswith("VOICE-SESS-")
        assert len(session.session_id) > 12

    def test_add_turn_appends_bounded_history(self, session: VoiceSessionContext) -> None:
        for i in range(7):
            session.add_turn(f"Q{i}", f"A{i}", max_turns=5)
        assert len(session.recent_operator_questions) == 5
        assert len(session.recent_nova_responses) == 5
        assert session.recent_operator_questions[0] == "Q2"
        assert session.recent_nova_responses[-1] == "A6"

    def test_add_turn_resets_interrupted_flag(self, session: VoiceSessionContext) -> None:
        session.is_interrupted = True
        session.add_turn("test", "response")
        assert session.is_interrupted is False

    def test_session_default_equipment(self, session: VoiceSessionContext) -> None:
        assert session.equipment_id == "F-201A"
        assert session.unit_area == "UNIT-CRACK-01"

    def test_session_created_at_is_utc(self, session: VoiceSessionContext) -> None:
        assert session.created_at.tzinfo is not None


# ======================================================================
# 2. TranscriptSegment Tests
# ======================================================================


class TestTranscriptSegment:
    """Speech-to-text transcript data contract validation."""

    def test_partial_transcript(self) -> None:
        seg = TranscriptSegment(text="What's hap", is_final=False, confidence=0.6)
        assert seg.text == "What's hap"
        assert seg.is_final is False

    def test_final_transcript(self) -> None:
        seg = TranscriptSegment(text="What's happening?", is_final=True, confidence=0.95)
        assert seg.is_final is True
        assert seg.speech_final is False  # default

    def test_deepgram_speech_final_flag(self) -> None:
        seg = TranscriptSegment(text="Done", is_final=True, speech_final=True, confidence=0.99)
        assert seg.speech_final is True


# ======================================================================
# 3. VoiceStreamEvent Tests
# ======================================================================


class TestVoiceStreamEvent:
    """Streaming lifecycle event contract tests."""

    def test_all_event_types_are_valid(self) -> None:
        expected = {
            "TRANSCRIPT_PARTIAL", "TRANSCRIPT_FINAL", "THINKING_STARTED",
            "RESPONSE_STARTED", "RESPONSE_TEXT_DELTA", "AUDIO_STARTED",
            "AUDIO_CHUNK", "BARGE_IN", "RESPONSE_CANCELLED",
            "RESPONSE_COMPLETED", "ERROR",
        }
        actual = {e.value for e in VoiceEventType}
        assert actual == expected

    def test_event_creation(self) -> None:
        evt = VoiceStreamEvent(
            event_type=VoiceEventType.TRANSCRIPT_FINAL,
            session_id="VOICE-SESS-TEST1234",
            payload={"text": "Hello"},
        )
        assert evt.event_id.startswith("evt_")
        assert evt.session_id == "VOICE-SESS-TEST1234"
        assert evt.timestamp is not None

    def test_barge_in_event(self) -> None:
        evt = VoiceStreamEvent(
            event_type=VoiceEventType.BARGE_IN,
            session_id="sess-1",
            payload={"reason": "operator_speech_detected"},
        )
        assert evt.event_type == VoiceEventType.BARGE_IN


# ======================================================================
# 4. VoiceResponse Contract Tests
# ======================================================================


class TestVoiceResponse:
    """Canonical voice response model contract validation."""

    def test_response_requires_session_id_and_transcript(self) -> None:
        resp = VoiceResponse(
            session_id="sess-1",
            transcript="What's happening?",
            intent="SITUATION",
            spoken_response="F-201A is above normal.",
        )
        assert resp.session_id == "sess-1"
        assert resp.response_id.startswith("vresp_")

    def test_response_default_confidence_is_none(self) -> None:
        resp = VoiceResponse(
            session_id="s", transcript="t", intent="SITUATION", spoken_response="r"
        )
        assert resp.confidence is None

    def test_response_default_no_action_required(self) -> None:
        resp = VoiceResponse(
            session_id="s", transcript="t", intent="SITUATION", spoken_response="r"
        )
        assert resp.requires_confirmation is False
        assert resp.action_request is None

    def test_response_serialization(self) -> None:
        resp = VoiceResponse(
            session_id="s",
            transcript="t",
            intent="SITUATION",
            spoken_response="r",
            limitations=["demo only"],
            ml_context={"ProcessAnomalyDetector": {"is_available": True}},
        )
        d = resp.model_dump()
        assert "limitations" in d
        assert d["limitations"] == ["demo only"]


# ======================================================================
# 5. VoiceCopilot Intent Classification Tests
# ======================================================================


class TestCopilotIntentClassification:
    """Intent classification across all supported operator query categories."""

    def test_situation_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("What's happening with F-201A?", session) == "SITUATION"
        assert copilot._classify_intent("What's wrong?", session) == "SITUATION"
        assert copilot._classify_intent("How is the furnace doing?", session) == "SITUATION"

    def test_diagnostic_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("Why is COT high?", session) == "DIAGNOSTIC"
        assert copilot._classify_intent("What fault was detected?", session) == "DIAGNOSTIC"
        assert copilot._classify_intent("What does the anomaly model say?", session) == "DIAGNOSTIC"

    def test_safety_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("Is this dangerous?", session) == "SAFETY"
        assert copilot._classify_intent("Do we need LOTO?", session) == "SAFETY"
        assert copilot._classify_intent("Is hot work allowed?", session) == "SAFETY"
        assert copilot._classify_intent("What about PPE?", session) == "SAFETY"

    def test_maintenance_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("When was this last maintained?", session) == "MAINTENANCE"
        assert copilot._classify_intent("Any open work orders?", session) == "MAINTENANCE"
        assert copilot._classify_intent("When was the last decoke?", session) == "MAINTENANCE"

    def test_evidence_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("What does the SOP say?", session) == "EVIDENCE"
        assert copilot._classify_intent("What evidence do we have?", session) == "EVIDENCE"

    def test_historical_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("Have we seen this before?", session) == "HISTORICAL"
        assert copilot._classify_intent("Any similar incidents?", session) == "HISTORICAL"

    def test_action_request(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("Shut the furnace down", session) == "ACTION_REQUEST"
        assert copilot._classify_intent("Emergency stop now", session) == "ACTION_REQUEST"
        assert copilot._classify_intent("Close valve FV-201", session) == "ACTION_REQUEST"

    def test_follow_up_query(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        assert copilot._classify_intent("why?", session) == "FOLLOW_UP"
        assert copilot._classify_intent("how high?", session) == "FOLLOW_UP"


# ======================================================================
# 6. VoiceCopilot Grounded Response Tests
# ======================================================================


class TestCopilotGroundedResponses:
    """Grounded response synthesis across all intent domains."""

    def test_situation_response_contains_cot_value(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What's happening with F-201A?", session, case)
        assert isinstance(resp, VoiceResponse)
        assert resp.intent == "SITUATION"
        assert "F-201A" in resp.spoken_response
        assert "°C" in resp.spoken_response

    def test_diagnostic_response_references_model(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Why is COT high?", session, case)
        assert resp.intent == "DIAGNOSTIC"
        assert "ProcessFaultClassifier" in resp.spoken_response or "fault" in resp.spoken_response.lower()

    def test_safety_response_includes_ppe_or_loto(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Is this dangerous?", session, case)
        assert resp.intent == "SAFETY"
        assert any(w in resp.spoken_response.lower() for w in ["safety", "ppe", "loto", "isolation", "priority"])

    def test_maintenance_response(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("When was this last maintained?", session, case)
        assert resp.intent == "MAINTENANCE"
        assert "decok" in resp.spoken_response.lower() or "work order" in resp.spoken_response.lower()

    def test_evidence_response_cites_documents(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What does the SOP say?", session, case)
        assert resp.intent == "EVIDENCE"
        assert len(resp.evidence) > 0

    def test_historical_response(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Have we seen this before?", session, case)
        assert resp.intent == "HISTORICAL"
        assert "incident" in resp.spoken_response.lower() or "thermal" in resp.spoken_response.lower()

    def test_hot_work_permit_response(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Can we do hot work here?", session, case)
        assert resp.intent == "SAFETY"
        assert "permit" in resp.spoken_response.lower()

    def test_follow_up_preserves_topic(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        # First set topic via situation query
        copilot.process_query("What's happening?", session, case)
        assert session.active_topic == "situation_overview"
        # Follow-up should resolve against active topic
        resp = copilot.process_query("why?", session, case)
        assert resp.intent == "FOLLOW_UP"
        assert len(resp.spoken_response) > 10

    def test_response_latency_is_recorded(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What's wrong?", session, case)
        assert resp.latency_ms is not None
        assert resp.latency_ms >= 0


# ======================================================================
# 7. Tube Temperature Surrogate Safety Compliance
# ======================================================================


class TestTubeTemperatureSurrogateCompliance:
    """Ensures TubeTemperaturePredictor voice output always contains synthetic surrogate disclaimers."""

    def test_tmt_query_explicitly_disclaims_measured_data(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What's the tube temperature?", session, case)
        assert "surrogate" in resp.spoken_response.lower() or "not industrially validated" in resp.spoken_response.lower()

    def test_tmt_query_does_not_claim_measured(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What is the TMT?", session, case)
        spoken_lower = resp.spoken_response.lower()
        assert "measured tube" not in spoken_lower
        assert "actual tmt" not in spoken_lower
        assert "coking detector" not in spoken_lower

    def test_tmt_limitations_include_surrogate_notice(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What about tube temperature?", session, case)
        assert any("surrogate" in lim.lower() or "synthetic" in lim.lower() for lim in resp.limitations)

    def test_tmt_does_not_imply_safety_instrumentation(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What is the skin temp?", session, case)
        spoken_lower = resp.spoken_response.lower()
        assert "safety instrumentation" in spoken_lower or "not industrially validated" in spoken_lower


# ======================================================================
# 8. Action Request / Safety Gate Tests
# ======================================================================


class TestActionRequestSafetyGate:
    """Ensures NOVA never executes industrial actions autonomously through voice."""

    def test_shutdown_request_requires_confirmation(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Shut the furnace down", session, case)
        assert resp.requires_confirmation is True
        assert resp.action_request is not None
        assert resp.action_request["requires_human_confirmation"] is True

    def test_shutdown_does_not_execute_directly(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Emergency stop now", session, case)
        assert resp.intent == "ACTION_REQUEST"
        assert "cannot execute" in resp.spoken_response.lower() or "confirmation" in resp.spoken_response.lower()

    def test_valve_control_requires_confirmation(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Close valve FV-201", session, case)
        assert resp.requires_confirmation is True
        assert resp.action_request is not None


# ======================================================================
# 9. Provenance & ML Context Tests
# ======================================================================


class TestProvenanceAndMLContext:
    """Ensures ML model provenance and audit trail are preserved in voice responses."""

    def test_provenance_contains_case_id(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What's happening?", session, case)
        assert "case_id" in resp.provenance
        assert "equipment_id" in resp.provenance
        assert resp.provenance["equipment_id"] == "F-201A"

    def test_provenance_records_intent(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("Why is COT high?", session, case)
        assert resp.provenance["intent"] == "DIAGNOSTIC"

    def test_ml_context_contains_all_four_models(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What's happening?", session, case)
        assert "ProcessAnomalyDetector" in resp.ml_context
        assert "ProcessFaultClassifier" in resp.ml_context
        assert "FurnaceCOTPredictor" in resp.ml_context
        assert "TubeTemperaturePredictor" in resp.ml_context

    def test_evidence_items_are_canonical(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        resp = copilot.process_query("What does the SOP say?", session, case)
        for ev in resp.evidence:
            assert isinstance(ev, CanonicalEvidence)


# ======================================================================
# 10. StreamingTranscriptDebouncer Tests
# ======================================================================


class TestStreamingTranscriptDebouncer:
    """Partial/interim transcript stabilization to prevent LLM jitter."""

    def test_interim_returns_none_on_first_input(self) -> None:
        d = StreamingTranscriptDebouncer()
        result = d.process_interim("What's")
        assert result is None

    def test_interim_returns_text_on_stabilized_repeat(self) -> None:
        d = StreamingTranscriptDebouncer()
        d.process_interim("What's happening")
        result = d.process_interim("What's happening")
        assert result == "What's happening"

    def test_interim_resets_on_new_text(self) -> None:
        d = StreamingTranscriptDebouncer()
        d.process_interim("What's happening")
        d.process_interim("What's happening")
        result = d.process_interim("What's happening with the furnace")
        assert result is None

    def test_final_returns_confirmed_text(self) -> None:
        d = StreamingTranscriptDebouncer()
        result = d.process_final("What's happening with F-201A?")
        assert result == "What's happening with F-201A?"

    def test_reset_clears_state(self) -> None:
        d = StreamingTranscriptDebouncer()
        d.process_interim("hello")
        d.process_final("hello world")
        d.reset()
        assert d.last_partial_text == ""
        assert d.confirmed_text == ""

    def test_empty_interim_returns_none(self) -> None:
        d = StreamingTranscriptDebouncer()
        assert d.process_interim("") is None
        assert d.process_interim("   ") is None


# ======================================================================
# 11. DeepgramSTTClient Tests
# ======================================================================


class TestDeepgramSTTClient:
    """Deepgram STT client configuration and fallback behavior."""

    def test_client_not_configured_without_api_key(self) -> None:
        client = DeepgramSTTClient(api_key="")
        assert client.is_configured is False

    def test_client_not_configured_with_mock_key(self) -> None:
        client = DeepgramSTTClient(api_key="mock-key")
        assert client.is_configured is False

    def test_client_configured_with_real_key(self) -> None:
        client = DeepgramSTTClient(api_key="dg_real_api_key_12345")
        assert client.is_configured is True

    def test_default_model_is_nova2(self) -> None:
        client = DeepgramSTTClient(api_key="test")
        assert client.model == "nova-2"

    @pytest.mark.asyncio
    async def test_empty_audio_returns_empty_transcript(self) -> None:
        client = DeepgramSTTClient(api_key="")
        seg = await client.transcribe_audio_bytes(b"")
        assert seg.text == ""
        assert seg.is_final is True

    @pytest.mark.asyncio
    async def test_fallback_transcribe_returns_segment(self) -> None:
        """Fallback should not crash even without faster-whisper installed."""
        client = DeepgramSTTClient(api_key="")
        seg = await client._fallback_transcribe(b"\x00" * 3200)
        assert isinstance(seg, TranscriptSegment)
        assert seg.is_final is True

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self) -> None:
        client = DeepgramSTTClient(api_key="")
        result = await client.health_check()
        assert result["status"] == "UNCONFIGURED"
        assert result["fallback_available"] is True


# ======================================================================
# 12. VoicePipelineManager Tests
# ======================================================================


class TestVoicePipelineManager:
    """Pipeline session lifecycle, latency tracking, and barge-in."""

    def test_session_creation(self, pipeline: VoicePipelineManager) -> None:
        session = pipeline.get_or_create_session(session_id="TEST-SESSION-01")
        assert session.session_id == "TEST-SESSION-01"

    def test_session_persistence(self, pipeline: VoicePipelineManager) -> None:
        s1 = pipeline.get_or_create_session(session_id="PERSIST-01")
        s2 = pipeline.get_or_create_session(session_id="PERSIST-01")
        assert s1.session_id == s2.session_id

    def test_latency_marker_recording(self, pipeline: VoicePipelineManager) -> None:
        pipeline.mark_latency("sess-lat", "start")
        time.sleep(0.01)
        pipeline.mark_latency("sess-lat", "end")
        elapsed = pipeline.get_latency_metric("sess-lat", "start", "end")
        assert elapsed is not None
        assert elapsed > 0

    def test_latency_returns_none_for_missing_markers(self, pipeline: VoicePipelineManager) -> None:
        result = pipeline.get_latency_metric("nonexistent", "a", "b")
        assert result is None

    @pytest.mark.asyncio
    async def test_barge_in_cancels_tts(self, pipeline: VoicePipelineManager) -> None:
        session = pipeline.get_or_create_session(session_id="BARGE-TEST")
        session.is_speaking = True
        with patch("backend.voice.pipeline.cancel_synthesis", new_callable=AsyncMock):
            event = await pipeline.handle_barge_in("BARGE-TEST", reason="operator_speech")
        assert event.event_type == VoiceEventType.BARGE_IN
        assert session.is_speaking is False
        assert session.is_interrupted is True

    @pytest.mark.asyncio
    async def test_barge_in_preserves_session_context(self, pipeline: VoicePipelineManager) -> None:
        session = pipeline.get_or_create_session(session_id="BARGE-CTX")
        session.case_id = "CASE-20260912-AABBCC"
        session.equipment_id = "F-201A"
        session.is_speaking = True
        with patch("backend.voice.pipeline.cancel_synthesis", new_callable=AsyncMock):
            await pipeline.handle_barge_in("BARGE-CTX")
        assert session.case_id == "CASE-20260912-AABBCC"
        assert session.equipment_id == "F-201A"

    @pytest.mark.asyncio
    async def test_barge_in_cancels_active_task(self, pipeline: VoicePipelineManager) -> None:
        session = pipeline.get_or_create_session(session_id="BARGE-TASK")
        session.is_speaking = True
        mock_task = MagicMock()
        mock_task.done.return_value = False
        pipeline._active_tasks["BARGE-TASK"] = mock_task
        with patch("backend.voice.pipeline.cancel_synthesis", new_callable=AsyncMock):
            await pipeline.handle_barge_in("BARGE-TASK")
        mock_task.cancel.assert_called_once()

    def test_vad_speech_detection(self, pipeline: VoicePipelineManager) -> None:
        import numpy as np
        session = pipeline.get_or_create_session(session_id="VAD-TEST")
        session.is_speaking = False
        # Should not trigger barge-in when not speaking
        silent = b"\x00" * 3200
        result = pipeline.detect_speech_interruption(silent, "VAD-TEST")
        assert result is False


# ======================================================================
# 13. Streaming Pipeline Event Flow Tests
# ======================================================================


class TestStreamingPipelineFlow:
    """End-to-end streaming event emission and ordering."""

    @pytest.mark.asyncio
    async def test_process_text_query_emits_correct_event_sequence(
        self, pipeline: VoicePipelineManager
    ) -> None:
        case = _make_operational_case()

        # Mock synthesize_stream to yield deterministic fake audio
        async def _fake_tts(text: str) -> Any:
            yield b"\x00" * 1024
            yield b"\x01" * 1024

        with patch("backend.voice.pipeline.synthesize_stream", _fake_tts):
            events: List[VoiceStreamEvent] = []
            async for evt in pipeline.process_text_query_stream(
                "What's happening?", operational_case=case
            ):
                events.append(evt)

        event_types = [e.event_type for e in events]

        # Verify ordering: TRANSCRIPT_FINAL → THINKING → RESPONSE_STARTED → deltas → AUDIO_STARTED → chunks → COMPLETED
        assert VoiceEventType.TRANSCRIPT_FINAL in event_types
        assert VoiceEventType.THINKING_STARTED in event_types
        assert VoiceEventType.RESPONSE_STARTED in event_types
        assert VoiceEventType.RESPONSE_TEXT_DELTA in event_types
        assert VoiceEventType.AUDIO_STARTED in event_types
        assert VoiceEventType.AUDIO_CHUNK in event_types
        assert VoiceEventType.RESPONSE_COMPLETED in event_types

        # TRANSCRIPT_FINAL should come first
        assert event_types.index(VoiceEventType.TRANSCRIPT_FINAL) < event_types.index(VoiceEventType.THINKING_STARTED)
        # AUDIO_STARTED should come after RESPONSE_STARTED
        assert event_types.index(VoiceEventType.RESPONSE_STARTED) < event_types.index(VoiceEventType.AUDIO_STARTED)

    @pytest.mark.asyncio
    async def test_completed_event_contains_latency_metrics(
        self, pipeline: VoicePipelineManager
    ) -> None:
        case = _make_operational_case()

        async def _fake_tts(text: str) -> Any:
            yield b"\x00" * 512

        with patch("backend.voice.pipeline.synthesize_stream", _fake_tts):
            events: List[VoiceStreamEvent] = []
            async for evt in pipeline.process_text_query_stream(
                "What's wrong?", operational_case=case
            ):
                events.append(evt)

        completed = [e for e in events if e.event_type == VoiceEventType.RESPONSE_COMPLETED]
        assert len(completed) == 1
        latency = completed[0].payload.get("latency", {})
        assert "reasoning_ms" in latency
        assert "time_to_first_audio_ms" in latency

    @pytest.mark.asyncio
    async def test_completed_event_contains_voice_response(
        self, pipeline: VoicePipelineManager
    ) -> None:
        case = _make_operational_case()

        async def _fake_tts(text: str) -> Any:
            yield b"\x00" * 512

        with patch("backend.voice.pipeline.synthesize_stream", _fake_tts):
            events: List[VoiceStreamEvent] = []
            async for evt in pipeline.process_text_query_stream(
                "What does the SOP say?", operational_case=case
            ):
                events.append(evt)

        completed = [e for e in events if e.event_type == VoiceEventType.RESPONSE_COMPLETED]
        response_data = completed[0].payload.get("response", {})
        assert "spoken_response" in response_data
        assert "intent" in response_data


# ======================================================================
# 14. Demo Conversation Scenario Tests
# ======================================================================


class TestDemoConversationScenarios:
    """Deterministic multi-turn voice conversation scenarios matching OperationalCase demos."""

    def test_conversation_1_high_cot_situation_then_followup(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        """Conversation 1: Operator asks about current condition, then asks why."""
        r1 = copilot.process_query("What's happening with F-201A?", session, case)
        assert r1.intent == "SITUATION"
        assert "F-201A" in r1.spoken_response
        assert "°C" in r1.spoken_response

        r2 = copilot.process_query("Why?", session, case)
        # Should provide diagnostic context as follow-up to situation
        assert len(r2.spoken_response) > 20

    def test_conversation_1_barge_in_safety_question(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        """Conversation 1 continued: Operator interrupts with safety question."""
        copilot.process_query("What's happening with F-201A?", session, case)
        session.is_interrupted = True
        r3 = copilot.process_query("Is this dangerous?", session, case)
        assert r3.intent == "SAFETY"
        assert any(w in r3.spoken_response.lower() for w in ["safety", "ppe", "priority", "isolation"])

    def test_conversation_2_anomaly_then_fault_classifier(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        """Conversation 2: What changed → What does fault classifier say."""
        r1 = copilot.process_query("What's wrong?", session, case)
        assert r1.intent == "SITUATION"

        r2 = copilot.process_query("What does the fault classifier say?", session, case)
        assert r2.intent == "DIAGNOSTIC"
        assert "fault" in r2.spoken_response.lower() or "classifier" in r2.spoken_response.lower()

    def test_conversation_3_maintenance_then_historical(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        """Conversation 3: Maintenance history → Similar past incidents."""
        r1 = copilot.process_query("When was this burner last serviced?", session, case)
        assert r1.intent == "MAINTENANCE"

        r2 = copilot.process_query("And was there a similar issue before?", session, case)
        assert r2.intent == "HISTORICAL"
        assert "incident" in r2.spoken_response.lower() or "thermal" in r2.spoken_response.lower()

    def test_conversation_4_hot_work_permit(
        self, copilot: VoiceCopilot, session: VoiceSessionContext, case: OperationalCase
    ) -> None:
        """Conversation 4: Hot work permit inquiry."""
        r1 = copilot.process_query("Can we do hot work here?", session, case)
        assert r1.intent == "SAFETY"
        assert "permit" in r1.spoken_response.lower()
        # Should not claim an active permit is authorized
        assert "authorized" not in r1.spoken_response.lower() or "not" in r1.spoken_response.lower()


# ======================================================================
# 15. Failure Handling Tests
# ======================================================================


class TestFailureHandling:
    """Graceful degradation when upstream services or models are unavailable."""

    def test_missing_model_in_ml_assessments(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        """Case with empty ML assessments should still produce a response."""
        case = OperationalCase(
            equipment_id="F-201A",
            equipment_type="furnace",
            unit_area="UNIT-CRACK-01",
            status=CaseStatus.NEW,
            priority=CasePriority.INFO,
            overall_state="NORMAL",
            ml_assessments={},
            limitations=["No ML models available"],
        )
        resp = copilot.process_query("What's happening?", session, case)
        assert isinstance(resp, VoiceResponse)
        assert resp.intent == "SITUATION"

    def test_model_not_available_flag(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        """ML assessment with is_available=False should not crash copilot."""
        case = OperationalCase(
            equipment_id="F-201A",
            equipment_type="furnace",
            unit_area="UNIT-CRACK-01",
            status=CaseStatus.NEW,
            priority=CasePriority.INFO,
            overall_state="NORMAL",
            ml_assessments={
                "ProcessAnomalyDetector": MLAssessmentSummary(
                    model_name="ProcessAnomalyDetector",
                    is_available=False,
                    status="MODEL_NOT_AVAILABLE",
                ),
            },
            limitations=["ProcessAnomalyDetector model artifact unavailable"],
        )
        resp = copilot.process_query("What does the anomaly detector say?", session, case)
        assert isinstance(resp, VoiceResponse)

    def test_empty_knowledge_evidence(self, copilot: VoiceCopilot, session: VoiceSessionContext) -> None:
        """Case with no knowledge evidence should not crash."""
        case = OperationalCase(
            equipment_id="F-201A",
            equipment_type="furnace",
            unit_area="UNIT-CRACK-01",
            status=CaseStatus.NEW,
            priority=CasePriority.INFO,
            overall_state="NORMAL",
            knowledge_evidence=[],
            safety_context=[],
            maintenance_context=[],
            incident_context=[],
            permit_context=[],
        )
        resp = copilot.process_query("What does the SOP say?", session, case)
        assert isinstance(resp, VoiceResponse)

    def test_tmt_query_with_unavailable_predictor(
        self, copilot: VoiceCopilot, session: VoiceSessionContext
    ) -> None:
        """TMT query when TubeTemperaturePredictor is unavailable."""
        case = OperationalCase(
            equipment_id="F-201A",
            equipment_type="furnace",
            unit_area="UNIT-CRACK-01",
            status=CaseStatus.NEW,
            priority=CasePriority.INFO,
            overall_state="NORMAL",
            ml_assessments={
                "TubeTemperaturePredictor": MLAssessmentSummary(
                    model_name="TubeTemperaturePredictor",
                    is_available=False,
                    status="MODEL_NOT_AVAILABLE",
                    target_type="physics_informed_synthetic_surrogate",
                    industrial_validation=False,
                ),
            },
        )
        resp = copilot.process_query("What's the tube temperature?", session, case)
        assert isinstance(resp, VoiceResponse)
        # Should still warn about surrogate nature
        assert any("surrogate" in lim.lower() or "synthetic" in lim.lower() for lim in resp.limitations)


# ======================================================================
# 16. Clean Spoken Output Tests
# ======================================================================


class TestCleanSpokenOutput:
    """Spoken text cleaning removes markdown, reasoning tags, and JSON artifacts."""

    def test_strip_markdown(self, copilot: VoiceCopilot) -> None:
        raw = "**Bold** and *italic* and `code` and ## heading"
        result = copilot._clean_spoken_output(raw)
        assert "*" not in result
        assert "`" not in result
        assert "#" not in result

    def test_strip_think_tags(self, copilot: VoiceCopilot) -> None:
        raw = "<think>Internal reasoning</think>The answer is 42."
        result = copilot._clean_spoken_output(raw)
        assert "Internal reasoning" not in result
        assert "42" in result

    def test_strip_response_prefix(self, copilot: VoiceCopilot) -> None:
        raw = "Thought: Let me analyze.\nAction: query_db\nResponse: The COT is 888°C."
        result = copilot._clean_spoken_output(raw)
        assert "Thought:" not in result
        assert "Action:" not in result
        assert "888°C" in result

    def test_multiline_collapse(self, copilot: VoiceCopilot) -> None:
        raw = "Line one.\n\nLine two.\n\n\nLine three."
        result = copilot._clean_spoken_output(raw)
        assert "\n" not in result
        assert "Line one." in result
        assert "Line three." in result


# ======================================================================
# 17. Audio Processing Integration Test
# ======================================================================


class TestAudioProcessingIntegration:
    """Audio utterance → VoiceResponse pipeline (mock STT)."""

    @pytest.mark.asyncio
    async def test_process_audio_utterance(self, pipeline: VoicePipelineManager) -> None:
        case = _make_operational_case()
        audio = b"\x00" * 3200
        resp = await pipeline.process_audio_utterance(audio, operational_case=case)
        assert isinstance(resp, VoiceResponse)
        # Default fallback should provide some response even with empty transcript
        assert resp.spoken_response is not None


# ======================================================================
# Entry Point
# ======================================================================


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
