"""
backend/tests/intelligence/test_ml_runtime.py — ML Runtime and Contracts Test Suite.

Tests:
  - MLEvidence contract fields and convenience accessors
  - MLEvidenceStatus, quality, prediction_type enums
  - MockAnomalyModel / MockFaultModel / MockCOTModel / MockTubeTemperatureModel
  - MLRuntime dispatch and graceful degradation
  - build_mock_ml_runtime() factory
  - Protocol compliance

Zero-actuation: all tests are read-only — no ML model deployment required.
"""
from __future__ import annotations

import pytest

from backend.ml.runtime.contracts import (
    MLEvidence,
    MLEvidenceQuality,
    MLEvidenceStatus,
    MLPredictionType,
)
from backend.ml.runtime.mocks import (
    MockAnomalyModel,
    MockCOTModel,
    MockFaultModel,
    MockTubeTemperatureModel,
    build_mock_ml_runtime,
)
from backend.ml.runtime.runtime import MLRuntime, MLModelProtocol


# ---------------------------------------------------------------------------
# Sample telemetry
# ---------------------------------------------------------------------------

SAMPLE_TELEMETRY = {
    "TI-20101": 847.0,
    "TI-20102": 849.0,
    "tube_skin_temperature": 985.0,
    "compressor_vibration": 1.6,
    "compressor_suction_pressure": 2.1,
}


# ---------------------------------------------------------------------------
# MLEvidence contract
# ---------------------------------------------------------------------------

class TestMLEvidenceContract:

    def test_successful_evidence_fields(self):
        ev = MLEvidence(
            model_name="TestModel",
            model_version="1.0",
            prediction_type=MLPredictionType.ANOMALY,
            asset_id="F-201A",
            status=MLEvidenceStatus.OK,
            prediction={"is_anomaly": True, "anomaly_score": 0.72},
            confidence=0.80,
            quality=MLEvidenceQuality.GOOD,
        )
        assert ev.is_successful is True
        assert ev.anomaly_score == pytest.approx(0.72)
        assert ev.is_anomaly is True
        assert ev.source == "runtime"

    def test_failed_evidence_is_not_successful(self):
        ev = MLEvidence(
            model_name="TestModel",
            model_version="1.0",
            prediction_type=MLPredictionType.ANOMALY,
            asset_id="F-201A",
            status=MLEvidenceStatus.MODEL_NOT_AVAILABLE,
            prediction=None,
            quality=MLEvidenceQuality.NOT_AVAILABLE,
        )
        assert ev.is_successful is False
        assert ev.prediction is None
        assert ev.confidence is None

    def test_convenience_accessors_return_none_for_wrong_type(self):
        ev = MLEvidence(
            model_name="FaultModel",
            model_version="1.0",
            prediction_type=MLPredictionType.FAULT_CLASSIFICATION,
            asset_id="K-201",
            status=MLEvidenceStatus.OK,
            prediction={"predicted_fault": "COMPRESSOR_SURGE", "confidence": 0.9},
        )
        assert ev.anomaly_score is None      # Wrong prediction type
        assert ev.is_anomaly is None         # Wrong prediction type
        assert ev.predicted_fault == "COMPRESSOR_SURGE"

    def test_cot_evidence_accessors(self):
        ev = MLEvidence(
            model_name="COTModel",
            model_version="1.0",
            prediction_type=MLPredictionType.COT_PREDICTION,
            asset_id="F-201A",
            status=MLEvidenceStatus.OK,
            prediction={"predicted_cot": 848.5, "unit": "celsius"},
        )
        assert ev.predicted_cot == pytest.approx(848.5)
        assert ev.predicted_fault is None

    def test_tube_temp_evidence_accessors(self):
        ev = MLEvidence(
            model_name="TubeModel",
            model_version="1.0",
            prediction_type=MLPredictionType.TUBE_TEMPERATURE,
            asset_id="F-201A",
            status=MLEvidenceStatus.OK,
            prediction={"predicted_tube_temperature": 987.0, "unit": "celsius"},
        )
        assert ev.predicted_tube_temperature == pytest.approx(987.0)


# ---------------------------------------------------------------------------
# Mock Models
# ---------------------------------------------------------------------------

class TestMockAnomalyModel:

    def test_normal_prediction(self):
        model = MockAnomalyModel(anomaly_score=0.1)
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.status == MLEvidenceStatus.OK
        assert ev.is_successful
        assert ev.prediction is not None
        assert ev.prediction["anomaly_score"] == pytest.approx(0.1)
        assert ev.prediction["is_anomaly"] is False
        assert ev.source == "mock"

    def test_forced_anomaly(self):
        model = MockAnomalyModel(force_anomaly=True, anomaly_score=0.2)
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.prediction["is_anomaly"] is True
        assert ev.prediction["anomaly_score"] == pytest.approx(0.2)

    def test_high_score_triggers_anomaly(self):
        model = MockAnomalyModel(anomaly_score=0.75)
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.prediction["is_anomaly"] is True

    def test_empty_telemetry_returns_invalid_input(self):
        model = MockAnomalyModel()
        ev = model.predict({}, "F-201A")
        assert ev.status == MLEvidenceStatus.INVALID_INPUT
        assert ev.prediction is None

    def test_prediction_type_is_anomaly(self):
        model = MockAnomalyModel()
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.prediction_type == MLPredictionType.ANOMALY

    def test_mock_label_in_model_name(self):
        model = MockAnomalyModel()
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert "MOCK" in ev.model_name.upper()


class TestMockFaultModel:

    def test_normal_fault(self):
        model = MockFaultModel(predicted_fault="NORMAL", confidence=0.9)
        ev = model.predict(SAMPLE_TELEMETRY, "K-201")
        assert ev.status == MLEvidenceStatus.OK
        assert ev.prediction["predicted_fault"] == "NORMAL"
        assert ev.confidence == pytest.approx(0.9)

    def test_custom_fault(self):
        model = MockFaultModel(predicted_fault="COMPRESSOR_SURGE", confidence=0.78)
        ev = model.predict(SAMPLE_TELEMETRY, "K-201")
        assert ev.prediction["predicted_fault"] == "COMPRESSOR_SURGE"
        assert ev.prediction["confidence"] == pytest.approx(0.78)

    def test_empty_telemetry_returns_invalid_input(self):
        model = MockFaultModel()
        ev = model.predict({}, "K-201")
        assert ev.status == MLEvidenceStatus.INVALID_INPUT

    def test_prediction_type_is_fault(self):
        model = MockFaultModel()
        ev = model.predict(SAMPLE_TELEMETRY, "K-201")
        assert ev.prediction_type == MLPredictionType.FAULT_CLASSIFICATION


class TestMockCOTModel:

    def test_normal_prediction(self):
        model = MockCOTModel(predicted_cot=845.0)
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.status == MLEvidenceStatus.OK
        assert ev.prediction["predicted_cot"] == pytest.approx(845.0)
        assert ev.units == "celsius"

    def test_with_actual_cot_in_telemetry(self):
        # Use only coil_outlet_temperature as the sole candidate key to avoid
        # TI-20101 (also a candidate) appearing first and shadowing the value.
        tel = {
            "tube_skin_temperature": 985.0,
            "compressor_vibration": 1.5,
            "coil_outlet_temperature": 848.0,  # Only COT candidate key present
        }
        model = MockCOTModel(predicted_cot=845.0)
        ev = model.predict(tel, "F-201A")
        assert ev.prediction["actual_cot"] == pytest.approx(848.0)
        assert ev.prediction["residual"] == pytest.approx(3.0)  # 848 - 845

    def test_confidence_is_none_for_regression(self):
        model = MockCOTModel()
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.confidence is None  # COT is regression, no calibrated probability

    def test_empty_telemetry(self):
        model = MockCOTModel()
        ev = model.predict({}, "F-201A")
        assert ev.status == MLEvidenceStatus.INVALID_INPUT


class TestMockTubeTemperatureModel:

    def test_normal_prediction(self):
        model = MockTubeTemperatureModel(predicted_temp=980.0)
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        assert ev.status == MLEvidenceStatus.OK
        assert ev.prediction["predicted_tube_temperature"] == pytest.approx(980.0)
        assert ev.units == "celsius"

    def test_coking_index_not_in_prediction(self):
        model = MockTubeTemperatureModel()
        ev = model.predict(SAMPLE_TELEMETRY, "F-201A")
        # coking_index must NEVER be present
        assert "coking_index" not in ev.prediction
        assert "coking_index_excluded" in ev.provenance

    def test_empty_telemetry(self):
        model = MockTubeTemperatureModel()
        ev = model.predict({}, "F-201A")
        assert ev.status == MLEvidenceStatus.INVALID_INPUT


# ---------------------------------------------------------------------------
# MLRuntime
# ---------------------------------------------------------------------------

class TestMLRuntime:

    def test_run_returns_four_evidence_records(self):
        runtime = build_mock_ml_runtime()
        results = runtime.run("F-201A", SAMPLE_TELEMETRY)
        assert len(results) == 4
        types = {ev.prediction_type for ev in results}
        assert types == {
            MLPredictionType.ANOMALY,
            MLPredictionType.FAULT_CLASSIFICATION,
            MLPredictionType.COT_PREDICTION,
            MLPredictionType.TUBE_TEMPERATURE,
        }

    def test_all_models_successful_with_valid_telemetry(self):
        runtime = build_mock_ml_runtime()
        results = runtime.run("F-201A", SAMPLE_TELEMETRY)
        for ev in results:
            assert ev.status == MLEvidenceStatus.OK, f"{ev.prediction_type} failed: {ev.status}"

    def test_empty_telemetry_returns_invalid_input_for_all(self):
        runtime = build_mock_ml_runtime()
        results = runtime.run("F-201A", {})
        for ev in results:
            assert ev.status == MLEvidenceStatus.INVALID_INPUT

    def test_anomaly_score_propagated_correctly(self):
        runtime = build_mock_ml_runtime(anomaly_score=0.65)
        results = runtime.run("F-201A", SAMPLE_TELEMETRY)
        anomaly = next(e for e in results if e.prediction_type == MLPredictionType.ANOMALY)
        assert anomaly.prediction["anomaly_score"] == pytest.approx(0.65)

    def test_runtime_gracefully_handles_model_failure(self):
        """Even if a model raises an unexpected exception, runtime returns INFERENCE_ERROR."""
        class BrokenModel:
            def predict(self, t, a):
                raise RuntimeError("Model exploded")

        runtime = MLRuntime(anomaly_model=BrokenModel())
        results = runtime.run("F-201A", SAMPLE_TELEMETRY)
        anomaly = next(e for e in results if e.prediction_type == MLPredictionType.ANOMALY)
        assert anomaly.status == MLEvidenceStatus.INFERENCE_ERROR

    def test_run_anomaly_only(self):
        runtime = build_mock_ml_runtime(anomaly_score=0.3)
        ev = runtime.run_anomaly("F-201A", SAMPLE_TELEMETRY)
        assert ev.prediction_type == MLPredictionType.ANOMALY
        assert ev.status == MLEvidenceStatus.OK

    def test_non_numeric_telemetry_values_skipped(self):
        """Non-numeric telemetry values must not crash the runtime."""
        tel = {**SAMPLE_TELEMETRY, "notes": "some_text", "flag": None}
        runtime = build_mock_ml_runtime()
        results = runtime.run("F-201A", tel)
        assert all(ev.is_successful for ev in results)

    def test_protocol_compliance(self):
        """Mock models must satisfy MLModelProtocol."""
        assert isinstance(MockAnomalyModel(), MLModelProtocol)
        assert isinstance(MockFaultModel(), MLModelProtocol)
        assert isinstance(MockCOTModel(), MLModelProtocol)
        assert isinstance(MockTubeTemperatureModel(), MLModelProtocol)

    def test_build_mock_runtime_factory(self):
        runtime = build_mock_ml_runtime(
            anomaly_score=0.8,
            force_anomaly=True,
            predicted_fault="TUBE_OVERTEMPERATURE",
            predicted_cot=880.0,
            predicted_tube_temp=1020.0,
        )
        results = runtime.run("F-201A", SAMPLE_TELEMETRY)
        assert len(results) == 4
        anomaly = next(e for e in results if e.prediction_type == MLPredictionType.ANOMALY)
        assert anomaly.prediction["is_anomaly"] is True
        cot = next(e for e in results if e.prediction_type == MLPredictionType.COT_PREDICTION)
        assert cot.prediction["predicted_cot"] == pytest.approx(880.0)
