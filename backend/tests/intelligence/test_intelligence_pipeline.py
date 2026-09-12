"""
backend/tests/intelligence/test_intelligence_pipeline.py — End-to-End Pipeline Test Suite.

Tests the complete IntelligenceService pipeline:
  Telemetry → ContextEngine → ContextRiskBridge → AgentOrchestrator → IntelligenceResult

Tests:
  - Happy path end-to-end
  - Risk score integration
  - Advisory output completeness
  - Partial pipeline failure handling
  - API dict serialization
"""
from __future__ import annotations

import pytest

from backend.agents.industrial.orchestrator import AgentOrchestrator
from backend.ml.runtime.mocks import build_mock_ml_runtime
from backend.services.context_engine import ContextEngine
from backend.services.context_risk_bridge import ContextRiskBridge
from backend.services.intelligence_service import IntelligenceResult, IntelligenceService


SAMPLE_TELEMETRY = {
    "TI-20101": 847.0,
    "TI-20102": 849.0,
    "tube_skin_temperature": 985.0,
    "compressor_vibration": 1.5,
    "compressor_suction_pressure": 2.2,
}


def _build_pipeline(
    anomaly_score: float = 0.1,
    force_anomaly: bool = False,
    predicted_fault: str = "NORMAL",
    predicted_cot: float = 845.0,
    predicted_tube_temp: float = 980.0,
) -> IntelligenceService:
    ml_runtime = build_mock_ml_runtime(
        anomaly_score=anomaly_score,
        force_anomaly=force_anomaly,
        predicted_fault=predicted_fault,
        predicted_cot=predicted_cot,
        predicted_tube_temp=predicted_tube_temp,
    )
    return IntelligenceService(
        context_engine=ContextEngine(ml_runtime=ml_runtime),
        risk_bridge=ContextRiskBridge(),
        orchestrator=AgentOrchestrator(),
    )


class TestIntelligencePipelineHappyPath:

    def test_pipeline_returns_success(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.success is True
        assert result.error is None

    def test_context_populated(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.context is not None
        assert result.context.asset_id == "F-201A"

    def test_risk_assessment_populated(self):
        svc = _build_pipeline(anomaly_score=0.3)
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.risk_assessment is not None
        assert 0.0 <= result.risk_assessment.risk_score <= 1.0

    def test_advisory_populated(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.advisory is not None
        assert len(result.advisory.advisories) == 4

    def test_all_timing_fields_positive(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.context_duration_ms >= 0.0
        assert result.risk_duration_ms >= 0.0
        assert result.agent_duration_ms >= 0.0
        assert result.total_duration_ms >= 0.0

    def test_run_id_is_unique(self):
        svc = _build_pipeline()
        r1 = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        r2 = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert r1.run_id != r2.run_id


class TestRiskIntegration:

    def test_high_anomaly_score_produces_high_risk(self):
        svc = _build_pipeline(anomaly_score=0.9, force_anomaly=True)
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.risk_assessment is not None
        assert result.risk_assessment.risk_score > 0.3

    def test_normal_conditions_produce_low_risk(self):
        svc = _build_pipeline(anomaly_score=0.0)
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.risk_assessment is not None
        assert result.risk_assessment.risk_score < 0.5

    def test_risk_score_in_advisory(self):
        svc = _build_pipeline(anomaly_score=0.5, force_anomaly=True)
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.advisory is not None
        assert result.advisory.risk_score is not None

    def test_context_id_in_risk_factors(self):
        svc = _build_pipeline(anomaly_score=0.4)
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert result.risk_assessment is not None
        assert "context_id" in result.risk_assessment.factors


class TestApiDictSerialization:

    def test_to_api_dict_returns_dict(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        d = result.to_api_dict()
        assert isinstance(d, dict)

    def test_api_dict_has_required_keys(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        d = result.to_api_dict()
        assert "run_id" in d
        assert "asset_id" in d
        assert "success" in d
        assert "timing_ms" in d
        assert "risk" in d
        assert "advisory" in d
        assert "context_summary" in d

    def test_api_dict_advisory_has_agents(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        d = result.to_api_dict()
        assert "agents" in d["advisory"]
        assert len(d["advisory"]["agents"]) == 4

    def test_api_dict_context_summary(self):
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        d = result.to_api_dict()
        cs = d["context_summary"]
        assert "providers_used" in cs
        assert "ml_available" in cs
        assert cs["ml_available"] is True


class TestPipelineGracefulDegradation:

    def test_pipeline_succeeds_without_telemetry(self):
        """Pipeline must not crash when no telemetry is available."""
        svc = _build_pipeline()
        result = svc.run("F-201A")  # No telemetry_override, no live provider
        # Should succeed (partial data) rather than crash
        assert result is not None

    def test_partial_telemetry_still_produces_result(self):
        partial_tel = {"TI-20101": 848.0}
        svc = _build_pipeline()
        result = svc.run("F-201A", telemetry_override=partial_tel)
        assert result.success is True

    def test_unknown_asset_still_produces_result(self):
        svc = _build_pipeline()
        result = svc.run("UNKNOWN-ASSET-XYZ", telemetry_override=SAMPLE_TELEMETRY)
        assert result.success is True
