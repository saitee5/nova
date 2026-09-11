"""
backend/tests/test_industrial_migration.py — Test suite for NOVA Phase 1 Industrial Migration.
"""
from __future__ import annotations

import os
import pytest
import yaml
from backend.config_reference_plant import REFERENCE_ASSETS, get_reference_plant_summary
from backend.ml.inference.pipeline import ml_pipeline
from backend.models.industrial_domain import (
    Asset,
    IndustrialRiskAssessment,
    OperationalEvent,
    ProcessTelemetry,
    RiskTier,
    SensorQuality,
)
from backend.policy_engine.safety_guard import DirectControlAttemptError, safety_guard
from backend.services.industrial_risk_service import industrial_risk_engine


def test_industrial_domain_models():
    """Verify Petrochemical domain Pydantic models."""
    telem = ProcessTelemetry(
        asset_id="F-201A",
        tag="TI-20101",
        value=845.5,
        unit="°C",
        quality=SensorQuality.GOOD,
    )
    assert telem.asset_id == "F-201A"
    assert telem.value == 845.5

    event = OperationalEvent(
        event_id="EVT-001",
        asset_id="K-201",
        event_type="vibration_warning",
        source="dcs",
        payload={"vibration_mm_s": 4.8},
    )
    assert event.asset_id == "K-201"
    assert event.payload["vibration_mm_s"] == 4.8


def test_reference_plant_config():
    """Verify Ethylene Steam Cracker reference plant catalog."""
    summary = get_reference_plant_summary()
    assert summary["total_assets"] >= 7
    asset_ids = [a["asset_id"] for a in summary["assets"]]
    assert "F-201A" in asset_ids
    assert "E-201" in asset_ids
    assert "K-201" in asset_ids
    assert "V-201" in asset_ids
    assert "P-201A" in asset_ids
    assert "SYS-FLARE" in asset_ids


def test_ml_contract_fallbacks():
    """Verify ML inference suite returns MODEL_NOT_AVAILABLE when model files do not exist."""
    results = ml_pipeline.run_inference_suite("F-201A", {"TI-20101": 845.5})
    assert len(results) == 4
    for key, assessment in results.items():
        assert assessment.status == "MODEL_NOT_AVAILABLE"
        assert assessment.prediction is None


def test_industrial_risk_engine():
    """Verify dynamic multi-factor process risk calculation."""
    assessment = industrial_risk_engine.evaluate_asset_risk(
        asset_id="F-201A",
        process_anomaly_score=0.8,
        equipment_condition_score=0.6,
        alarm_severity="HIGH",
        has_active_permit=True,
        is_simops=True,
        personnel_count_in_zone=3,
        asset_criticality="CRITICAL",
    )
    assert isinstance(assessment, IndustrialRiskAssessment)
    assert assessment.risk_tier in (RiskTier.HIGH, RiskTier.CRITICAL)
    assert assessment.risk_score > 0.5
    assert len(assessment.recommended_actions) > 0


def test_safety_guard_enforcement():
    """Verify SafetyGuard allows advisory queries but blocks direct control writes."""
    assert safety_guard.validate_action("get_asset_status") is True
    assert safety_guard.validate_action("generate_risk_report") is True

    with pytest.raises(DirectControlAttemptError):
        safety_guard.validate_action("plc_write_setpoint")

    with pytest.raises(DirectControlAttemptError):
        safety_guard.validate_action("trigger_esd_command")


def test_data_provenance_manifest():
    """Verify data/manifest.yaml exists and parses correctly."""
    manifest_path = os.path.join("data", "manifest.yaml")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "provenance_categories" in data
    assert "SIMULATED_BENCHMARK" in data["provenance_categories"]
    assert "REAL_INDUSTRIAL_DATA" in data["provenance_categories"]
