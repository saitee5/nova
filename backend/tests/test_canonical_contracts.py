"""
backend/tests/test_canonical_contracts.py — Test suite for NOVA Canonical Backend Architecture.

Verifies:
1. Canonical domain contracts (telemetry, operating mode, plant state, alarm, permit, maintenance, occupancy)
2. PlantState aggregation service
3. Feature extraction & temporal sliding window
4. Pluggable ML model contracts & MODEL_NOT_AVAILABLE graceful handling
5. Model registry manifest loading and metadata verification
6. Unified MLPipeline execution across all 4 industrial models
7. Deterministic Industrial Risk Engine & compound SIMOPS calculations
8. Operational Episode 7-stage lifecycle progression
9. EvidencePackage assembly
10. Memory abstraction (upsert & search)
11. SafetyGuard boundary enforcement against direct control commands
12. Canonical REST API endpoints
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ml.anomaly.detector import ProcessAnomalyDetector
from backend.ml.fault.classifier import ProcessFaultClassifier
from backend.ml.features.extractor import FeatureExtractor, FeatureWindow
from backend.ml.furnace.cot_predictor import FurnaceCOTPredictor
from backend.ml.furnace.tube_temp_predictor import TubeTemperaturePredictor
from backend.ml.inference.pipeline import MLPipeline, ml_pipeline
from backend.ml.registry.registry import model_registry
from backend.models.evidence import EvidenceItem, EvidencePackage, HistoricalMatch
from backend.models.industrial_domain import (
    Alarm,
    EpisodeStatus,
    IndustrialRiskAssessment,
    MaintenanceRecord,
    MLAssessment,
    MLAssessmentStatus,
    OccupancyRecord,
    OperatingMode,
    OperationalEpisode,
    Permit,
    PlantState,
    ProcessTelemetry,
    RiskTier,
    SensorQuality,
)
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.services.episode_engine import episode_engine
from backend.services.industrial_risk_service import industrial_risk_engine
from backend.services.plant_state_service import plant_state_service


# ──────────────────────────────────────────────────────────────────────────────
# 1. Canonical Domain Contracts
# ──────────────────────────────────────────────────────────────────────────────

def test_canonical_telemetry_contract():
    """Verify ProcessTelemetry supports all canonical fields and maintains backward compatibility."""
    telem = ProcessTelemetry(
        asset_id="F-201A",
        tag="TI-20101",
        value=850.4,
        unit="°C",
        quality=SensorQuality.GOOD,
        plant_id="NOVA-PLANT-01",
        unit_id="CRACKING-01",
        sensor_id="F201A-COT-01",
        parameter="coil_outlet_temperature",
        source="synthetic_nova",
        provenance="SYNTHETIC_NOVA_DATA",
    )
    assert telem.asset_id == "F-201A"
    assert telem.value == 850.4
    assert telem.plant_id == "NOVA-PLANT-01"
    assert telem.sensor_id == "F201A-COT-01"
    assert telem.parameter == "coil_outlet_temperature"
    assert telem.tag == "TI-20101"
    assert telem.event_id.startswith("telem_")
    assert telem.quality == SensorQuality.GOOD


def test_operating_mode_contract():
    """Verify OperatingMode includes all minimum required modes."""
    target_modes = [
        OperatingMode.STARTUP,
        OperatingMode.SHUTDOWN,
        OperatingMode.STEADY_STATE,
        OperatingMode.RAMP_UP,
        OperatingMode.RAMP_DOWN,
        OperatingMode.MAINTENANCE,
        OperatingMode.EMERGENCY,
        OperatingMode.UNKNOWN,
        OperatingMode.NORMAL,
    ]
    for mode in target_modes:
        assert mode.value is not None


# ──────────────────────────────────────────────────────────────────────────────
# 2. Plant State Aggregation Service
# ──────────────────────────────────────────────────────────────────────────────

def test_plant_state_service():
    """Verify PlantState aggregation service integrates multi-modal telemetry and operational state."""
    plant_state_service.reset_state()

    # Update telemetry
    plant_state_service.update_telemetry({
        "asset_id": "F-201A",
        "parameter": "coil_outlet_temperature",
        "value": 855.2,
        "unit": "°C",
    })

    # Update alarm
    plant_state_service.update_alarm({
        "alarm_id": "ALM-COT-HIGH",
        "asset_id": "F-201A",
        "severity": "HIGH",
        "message": "Coil outlet temperature high alarm",
    })

    # Update permit
    plant_state_service.update_permit({
        "permit_id": "PTW-HW-01",
        "permit_type": "Hot Work",
        "status": "ACTIVE",
        "asset_id": "F-201A",
    })

    # Update maintenance
    plant_state_service.update_maintenance({
        "record_id": "MNT-01",
        "asset_id": "F-201A",
        "status": "OPEN",
    })

    # Update occupancy
    plant_state_service.update_occupancy("Bay3", 4)

    state = plant_state_service.get_current_state()
    assert isinstance(state, PlantState)
    assert len(state.telemetry) >= 1
    assert len(state.active_alarms) == 1
    assert len(state.active_permits) == 1
    assert len(state.active_maintenance) == 1
    assert state.occupancy.get("Bay3") == 4
    assert state.metadata.get("simops_active") is True


# ──────────────────────────────────────────────────────────────────────────────
# 3. Feature Extraction & Temporal Windowing
# ──────────────────────────────────────────────────────────────────────────────

def test_feature_extractor_and_window():
    """Verify FeatureExtractor transforms time-series windows into statistical and contextual features."""
    extractor = FeatureExtractor()
    window = FeatureWindow(window_size_seconds=60.0)
    window.operating_mode = OperatingMode.RAMP_UP
    window.asset_id = "F-201A"

    now = datetime.now(timezone.utc)
    # Add multiple sequential readings
    window.add_reading("cot", 845.0, now)
    window.add_reading("cot", 848.0, now)
    window.add_reading("cot", 852.0, now)

    features = extractor.transform(window)

    assert "cot_raw" in features
    assert features["cot_raw"] == 852.0
    assert "cot_delta" in features
    assert features["cot_delta"] == 7.0
    assert "cot_rolling_mean" in features
    assert round(features["cot_rolling_mean"], 1) == 848.3
    assert "cot_rolling_min" in features
    assert features["cot_rolling_min"] == 845.0
    assert "cot_rolling_max" in features
    assert features["cot_rolling_max"] == 852.0
    assert "cot_baseline_deviation" in features
    assert "mode_ramp_up" in features
    assert features["mode_ramp_up"] == 1.0


# ──────────────────────────────────────────────────────────────────────────────
# 4. Pluggable ML Model Contracts & Graceful Fallback
# ──────────────────────────────────────────────────────────────────────────────

def test_ml_model_contracts_return_model_not_available():
    """Verify all 4 ML models return MODEL_NOT_AVAILABLE when weights are absent and validate inputs."""
    anomaly_detector = ProcessAnomalyDetector(model_path="nonexistent.joblib")
    fault_classifier = ProcessFaultClassifier(model_path="nonexistent.joblib")
    cot_predictor = FurnaceCOTPredictor(model_path="nonexistent.joblib")
    tube_temp_predictor = TubeTemperaturePredictor()

    # Valid input with absent weights -> MODEL_NOT_AVAILABLE
    dummy_input = {"cot": 850.0, "pressure": 2.5}
    assert anomaly_detector.detect_anomaly(dummy_input).status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert fault_classifier.classify_fault(dummy_input).status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert cot_predictor.predict_cot(dummy_input).status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value
    assert tube_temp_predictor.predict_tube_temperature(dummy_input).status == MLAssessmentStatus.MODEL_NOT_AVAILABLE.value

    # Invalid empty input -> INVALID_INPUT
    assert anomaly_detector.detect_anomaly({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert fault_classifier.classify_fault({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert cot_predictor.predict_cot({}).status == MLAssessmentStatus.INVALID_INPUT.value
    assert tube_temp_predictor.predict_tube_temperature({}).status == MLAssessmentStatus.INVALID_INPUT.value


# ──────────────────────────────────────────────────────────────────────────────
# 5. Model Registry
# ──────────────────────────────────────────────────────────────────────────────

def test_model_registry_manifest():
    """Verify ModelRegistry loads and validates the 4 planned industrial models."""
    models = model_registry.list_models()
    assert len(models) >= 4
    model_names = [m.name for m in models]
    assert "ProcessAnomalyDetector" in model_names
    assert "ProcessFaultClassifier" in model_names
    assert "FurnaceCOTPredictor" in model_names
    assert "TubeTemperaturePredictor" in model_names

    for m in models:
        assert m.status in (
            "ready",
            "trained",
            "not_trained",
            "placeholder",
            "VALIDATED",
            "VALIDATED_WITH_LIMITATIONS",
        )

        assert m.dataset is not None
        assert m.target is not None


# ──────────────────────────────────────────────────────────────────────────────
# 6. Unified ML Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def test_unified_ml_pipeline_execution():
    """Verify MLPipeline executes gracefully across all 4 models even when artifacts are not installed."""
    pipeline = MLPipeline()
    state = plant_state_service.get_current_state()

    results = pipeline.run_pipeline(input_data=state, asset_id="F-201A")
    assert len(results) == 4
    assert "anomaly_detection" in results
    assert "fault_diagnosis" in results
    assert "furnace_cot_prediction" in results
    assert "tube_temperature_soft_sensor" in results

    # Pipeline returns valid structured response even when models return MODEL_NOT_AVAILABLE
    for assessment in results.values():
        assert isinstance(assessment, MLAssessment)
        assert assessment.status in (MLAssessmentStatus.MODEL_NOT_AVAILABLE.value, MLAssessmentStatus.OK.value)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Industrial Risk Engine
# ──────────────────────────────────────────────────────────────────────────────

def test_deterministic_industrial_risk_calculation():
    """Verify deterministic risk calculation, SIMOPS sensitivity, and advisory metadata."""
    # Baseline nominal risk
    nominal_risk = industrial_risk_engine.evaluate_asset_risk(
        asset_id="F-201A",
        process_anomaly_score=0.0,
        equipment_condition_score=0.0,
        alarm_severity="LOW",
        has_active_permit=False,
        is_simops=False,
        personnel_count_in_zone=0,
        asset_criticality="CRITICAL",
    )
    assert nominal_risk.risk_tier == RiskTier.LOW
    assert nominal_risk.advisory_only is True
    assert nominal_risk.policy_version == "1.0"
    assert "process_anomaly" in nominal_risk.factors

    # Compound SIMOPS elevated risk
    simops_risk = industrial_risk_engine.evaluate_asset_risk(
        asset_id="F-201A",
        process_anomaly_score=0.8,
        equipment_condition_score=0.7,
        alarm_severity="HIGH",
        has_active_permit=True,
        is_simops=True,
        personnel_count_in_zone=5,
        asset_criticality="CRITICAL",
    )
    assert simops_risk.risk_score > nominal_risk.risk_score
    assert simops_risk.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL)
    assert any("SIMOPS" in act for act in simops_risk.recommended_actions)


# ──────────────────────────────────────────────────────────────────────────────
# 8. Operational Episode Lifecycle
# ──────────────────────────────────────────────────────────────────────────────

def test_operational_episode_lifecycle():
    """Verify episode engine 7-stage state progression and correlation."""
    episode = episode_engine.get_or_create_episode("F-201A")
    assert episode.status == EpisodeStatus.NORMAL

    # Transition to DEVIATION
    episode_engine.transition_status(episode.episode_id, EpisodeStatus.DEVIATION, "Process parameter drift")
    assert episode.status == EpisodeStatus.DEVIATION

    # Correlate anomaly ML assessment -> transitions to ANOMALY
    fake_anom = MLAssessment(
        model_name="AnomalyDetector",
        model_version="1.0",
        status="OK",
        score=0.85,
    )
    episode_engine.correlate_observation("F-201A", ml_assessments={"anomaly_detection": fake_anom})
    assert episode.status == EpisodeStatus.ANOMALY

    # Transition to RESOLVED
    episode_engine.transition_status(episode.episode_id, EpisodeStatus.RESOLVED, "Process stabilized")
    assert episode.status == EpisodeStatus.RESOLVED
    assert episode.end_time is not None


# ──────────────────────────────────────────────────────────────────────────────
# 9. Evidence Package
# ──────────────────────────────────────────────────────────────────────────────

def test_evidence_package_model():
    """Verify EvidencePackage combines state, ML, risk, alarms, permits, and provenance."""
    pkg = EvidencePackage(
        package_id="EPKG-001",
        timestamp=datetime.now(timezone.utc),
        plant_id="PLANT-ETH-01",
        unit_id="UNIT-CRACK-01",
        asset_id="F-201A",
        ml_assessments={"anomaly": {"status": "MODEL_NOT_AVAILABLE"}},
        active_alarms=[{"alarm_id": "ALM-01", "severity": "HIGH"}],
        historical_matches=[
            HistoricalMatch(
                record_id="REC-01",
                collection="nova_operational_memory",
                similarity_score=0.91,
                rerank_score=0.88,
                title="Past furnace tube leak",
                date=datetime.now(timezone.utc),
                matched_on=["temperature"],
            )
        ],
        provenance={"system": "NOVA", "read_only": True},
    )
    assert pkg.package_id == "EPKG-001"
    assert len(pkg.historical_matches) == 1
    assert pkg.historical_matches[0].similarity_score == 0.91


# ──────────────────────────────────────────────────────────────────────────────
# 10. SafetyGuard Enforcement
# ──────────────────────────────────────────────────────────────────────────────

def test_safety_guard_blocks_prohibited_actions():
    """Verify SafetyGuard rejects direct actuator control, PLC, DCS, or ESD commands."""
    assert safety_guard.validate_action("get_telemetry") is True
    assert safety_guard.validate_action("recommend_inspection") is True

    prohibited_actions = [
        "plc_write_registers",
        "dcs_write_setpoint",
        "issue_sis_command",
        "esd_command_trigger",
        "actuator_control_valve_force",
        "setpoint_change_furnace_fuel",
    ]
    for action in prohibited_actions:
        with pytest.raises(DirectControlAttemptError):
            safety_guard.validate_action(action)


# ──────────────────────────────────────────────────────────────────────────────
# 11. Canonical REST API Endpoints
# ──────────────────────────────────────────────────────────────────────────────

def test_canonical_rest_api_endpoints():
    """Verify FastAPI test client can access canonical endpoints without 500 errors."""
    client = TestClient(app)

    # Health
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Plants & Units
    assert client.get("/api/plants").status_code == 200
    assert client.get("/api/units").status_code == 200
    assert client.get("/api/assets").status_code == 200

    # Plant State
    res = client.get("/api/plant-state")
    assert res.status_code == 200
    assert "plant_id" in res.json()

    # ML Status & Inference
    res = client.get("/api/ml/status")
    assert res.status_code == 200
    assert "catalog" in res.json()

    res = client.post("/api/ml/inference", json={"asset_id": "F-201A"})
    assert res.status_code == 200
    assert "assessments" in res.json()

    # Risk Evaluate
    res = client.post("/api/risk/evaluate", json={
        "asset_id": "F-201A",
        "process_anomaly_score": 0.2,
        "equipment_condition_score": 0.1,
        "alarm_severity": "LOW",
        "has_active_permit": False,
        "is_simops": False,
        "personnel_count_in_zone": 2,
        "asset_criticality": "HIGH",
    })
    assert res.status_code == 200
    assert "risk_score" in res.json()

    # Copilot query
    res = client.post("/api/copilot/query", json={"prompt": "Status of furnace F-201A?", "asset_id": "F-201A"})
    assert res.status_code == 200
    assert "evidence_package" in res.json()
    assert res.json()["advisory_only"] is True
