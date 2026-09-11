"""Risk service coordination layer (§11.5).

Provides deterministic safety checks and risk score to authorization level composition.
Note: Complex multi-factor risk reasoning lives in agents/risk_reasoner/ (TODO: Phase 2).
"""

from __future__ import annotations

from backend.models.event import NormalizedEvent
from backend.policy_engine.authorization import required_authorization
from backend.policy_engine.safety_rules import deterministic_alarm_check
from backend.policy_engine.thresholds import score_to_tier


def apply_deterministic_check(event: NormalizedEvent) -> bool:
    """Apply non-LLM, SCADA-style deterministic safety threshold checks directly.

    Bypasses the AI/LLM path entirely for safety-critical telemetry.

    Args:
        event: The incoming telemetry ``NormalizedEvent``.

    Returns:
        True if hard safety threshold is triggered, False otherwise.
    """
    return deterministic_alarm_check(event)


def score_to_tier_and_authorization(score: float) -> tuple[str, str]:
    """Compose score-to-tier mapping and required authorization level.

    Args:
        score: Continuous risk score [0.0, 1.0].

    Returns:
        Tuple of ``(tier_name, authorization_level)`` where tier_name is one of
        ("low", "medium", "high", "critical") and authorization_level is one of
        ("none", "notify", "confirm").
    """
    tier = score_to_tier(score)
    auth_level = required_authorization(tier)
    return tier, auth_level


def calculate_decomposed_risk(
    threat_severity: float,  # 0.0 - 1.0
    asset_criticality: str = "MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
    vulnerability_count: int = 0,
    exposure_multiplier: float = 1.0,
) -> dict[str, any]:
    """Calculate multi-factor decomposed risk score and matrix breakdown."""
    crit_weights = {"LOW": 0.4, "MEDIUM": 0.65, "HIGH": 0.85, "CRITICAL": 1.0}
    crit_factor = crit_weights.get(asset_criticality.upper(), 0.65)
    vuln_factor = min(0.3, vulnerability_count * 0.1)

    raw_score = (threat_severity * 0.5 + crit_factor * 0.35 + vuln_factor * 0.15) * exposure_multiplier
    final_score = round(max(0.0, min(1.0, raw_score)), 3)
    tier, auth_level = score_to_tier_and_authorization(final_score)

    return {
        "score": final_score,
        "tier": tier,
        "required_authorization": auth_level,
        "breakdown": {
            "threat_severity": threat_severity,
            "asset_criticality": asset_criticality,
            "asset_criticality_factor": crit_factor,
            "vulnerability_factor": vuln_factor,
            "exposure_multiplier": exposure_multiplier,
        },
    }

