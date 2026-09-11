"""
backend/policy_engine/safety_guard.py — Safety Boundary Enforcement Guard.

NOVA is strictly read-only and advisory.
This safety guard intercepts and rejects any attempts to issue:
- PLC writes
- DCS writes
- SIS (Safety Instrumented System) commands
- ESD (Emergency Shut-Down) commands
- Direct setpoint changes
- Actuator output control commands

The LLM and agent orchestration MUST NEVER bypass this boundary.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("nova.safety_guard")

PROHIBITED_COMMAND_PATTERNS = [
    "plc_write",
    "dcs_write",
    "sis_command",
    "esd_command",
    "setpoint_change",
    "actuator_control",
    "override_interlock",
    "force_output",
]


class DirectControlAttemptError(PermissionError):
    """Raised when an action attempts to issue direct control commands to industrial control systems."""
    pass


class SafetyGuard:
    """Enforces read-only advisory architecture boundaries."""

    @staticmethod
    def validate_action(action_name: str, parameters: dict | None = None) -> bool:
        """
        Validate whether action_name is permissible under NOVA's read-only advisory model.

        Raises DirectControlAttemptError if action_name matches prohibited control patterns.
        """
        act_lower = action_name.lower().strip()
        for prohibited in PROHIBITED_COMMAND_PATTERNS:
            if prohibited in act_lower:
                msg = f"SAFETY GUARDRALL VIOLATION: Action '{action_name}' is a direct control command. NOVA operates strictly in READ-ONLY / ADVISORY mode."
                logger.critical(msg)
                raise DirectControlAttemptError(msg)

        logger.info("SafetyGuard validated action '%s' as advisory-compliant.", action_name)
        return True


# Global singleton instance
safety_guard = SafetyGuard()
