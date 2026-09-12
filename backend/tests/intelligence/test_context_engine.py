"""
backend/tests/intelligence/test_context_engine.py — Context Engine Test Suite.

Tests:
  - Context assembly with telemetry override
  - Provenance tagging (OBSERVED, PREDICTED, MISSING, STALE)
  - ML evidence injection into context
  - Provider failure graceful degradation
  - OperationalContextSnapshot properties
  - equipment_condition_score derivation
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from backend.services.context_engine import (
    ContextEngine,
    DataProvenance,
    OperationalContextSnapshot,
)
from backend.ml.runtime.mocks import build_mock_ml_runtime


SAMPLE_TELEMETRY = {
    "TI-20101": 848.0,
    "TI-20102": 850.0,
    "tube_skin_temperature": 986.0,
    "compressor_vibration": 1.5,
    "compressor_suction_pressure": 2.2,
}


class TestContextEngineBasic:

    def test_assemble_with_telemetry_override(self):
        engine = ContextEngine(
            ml_runtime=build_mock_ml_runtime(anomaly_score=0.1),
        )
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.asset_id == "F-201A"
        assert isinstance(ctx.timestamp, datetime)
        assert ctx.context_id.startswith("ctx_")

    def test_telemetry_fields_have_observed_provenance(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime())
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        for param, field in ctx.telemetry.items():
            assert field.provenance == DataProvenance.OBSERVED

    def test_ml_evidence_populated_from_runtime(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.3))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert len(ctx.ml_evidence) == 4
        assert ctx.ml_summary is not None

    def test_ml_summary_anomaly_field_has_predicted_provenance(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.4))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.ml_summary is not None
        assert ctx.ml_summary.anomaly_score.provenance == DataProvenance.PREDICTED

    def test_ml_skipped_when_no_telemetry(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime())
        ctx = engine.assemble("F-201A")
        # No telemetry provider, no override → ML skipped
        assert len(ctx.ml_evidence) == 0
        assert "No telemetry available" in " ".join(ctx.warnings)

    def test_anomaly_score_property(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.55))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.anomaly_score == pytest.approx(0.55)

    def test_is_anomaly_false_when_score_below_threshold(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.1))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.is_anomaly is False

    def test_is_anomaly_true_when_forced(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(force_anomaly=True, anomaly_score=0.8))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.is_anomaly is True

    def test_providers_used_logged(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime())
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert "telemetry:override" in ctx.providers_used
        assert "ml_runtime" in ctx.providers_used

    def test_missing_providers_produce_missing_provenance(self):
        engine = ContextEngine()  # No providers at all
        ctx = engine.assemble("F-201A")
        assert ctx.operating_mode.provenance == DataProvenance.MISSING
        assert ctx.equipment_status.provenance == DataProvenance.MISSING
        assert ctx.personnel_count.provenance == DataProvenance.MISSING

    def test_assembly_duration_recorded(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime())
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.assembly_duration_ms >= 0.0


class TestEquipmentConditionScore:

    def test_healthy_status_gives_low_score(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.0))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        # No equipment provider → UNKNOWN → 0.3 base, anomaly=0.0
        assert ctx.equipment_condition_score <= 0.3 + 0.01  # float tolerance

    def test_anomaly_boosts_condition_score(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=0.85, force_anomaly=True))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        # Anomaly boosts equipment_condition_score to at least anomaly_score
        assert ctx.equipment_condition_score >= 0.85

    def test_score_is_clamped_to_1(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime(anomaly_score=1.0, force_anomaly=True))
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx.equipment_condition_score <= 1.0


class TestContextEngineProviderGracefulDegradation:

    def test_failing_ml_runtime_produces_empty_evidence(self):
        class BrokenRuntime:
            def run(self, asset_id, telemetry):
                raise RuntimeError("ML runtime crashed")

        engine = ContextEngine(ml_runtime=BrokenRuntime())
        ctx = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        # Should not crash — returns empty evidence + warning
        assert ctx.ml_evidence == []
        assert any("ML runtime error" in w for w in ctx.warnings)

    def test_context_id_unique_per_call(self):
        engine = ContextEngine(ml_runtime=build_mock_ml_runtime())
        ctx1 = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        ctx2 = engine.assemble("F-201A", telemetry_override=SAMPLE_TELEMETRY)
        assert ctx1.context_id != ctx2.context_id
