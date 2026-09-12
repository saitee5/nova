# NOVA Industrial Safety Boundary & Advisory Policy

**Owner Module:** `backend/policy_engine/safety_guard.py`  
**Classification:** Critical Industrial Safety Constraint (Fail-Closed)

---

## 1. Zero-Actuation Boundary

NOVA is an **Industrial AI Co-Pilot and Safety Advisory System**. It is architecturally and policy-constrained to the following operational verbs:

```text
               ┌────────────────────────────────────────────────────────┐
               │                  PERMITTED OPERATIONS                  │
               ├────────────────────────────────────────────────────────┤
               │  ✓ READ live and historical plant telemetry            │
               │  ✓ ANALYZE multi-variate process states & trends       │
               │  ✓ EXPLAIN anomalies, alarms, and SIMOPS hazards       │
               │  ✓ RECOMMEND procedural mitigations & SOP checklists   │
               │  ✓ AUDIT system events, operator logs, and overrides   │
               └────────────────────────────────────────────────────────┘
```

---

## 2. Strictly Prohibited Actions (Zero Tolerance)

NOVA is explicitly blocked from issuing control or actuation commands. Under no circumstances may NOVA:

```text
               ┌────────────────────────────────────────────────────────┐
               │                  PROHIBITED ACTIONS                    │
               ├────────────────────────────────────────────────────────┤
               │  ✗ Write or alter PLC registers (Modbus/Profinet/Ether) │
               │  ✗ Send setpoint modification commands to DCS          │
               │  ✗ Issue Safety Instrumented System (SIS) commands     │
               │  ✗ Trigger Emergency Shutdown (ESD) valves or relays   │
               │  ✗ Directly open/close valves, breakers, or dampers    │
               │  ✗ Override automated safety interlocks or trips       │
               └────────────────────────────────────────────────────────┘
```

---

## 3. Enforcement Mechanism: `SafetyGuard`

Every generated recommendation, agent tool call, and API execution is intercepted by `backend/policy_engine/safety_guard.py`:
1. **Keyword & Regex Filtering:** Scans for forbidden phrases (e.g. `write_plc`, `modify_setpoint`, `trigger_esd`, `open_valve`, `trip_plant`).
2. **Deterministic Blocking:** If any forbidden actuation is detected, the action is immediately blocked with `is_safe=False`.
3. **Audit Logging:** An incident violation is written to the `audit_events` database table with timestamp, user/agent ID, and rejected action text.
4. **Advisory Affirmation:** All outward-facing recommendations must include an explicit disclaimer:
   > *"NOVA is an advisory tool. Final operational verification and control actions must be performed by qualified human control room operators in accordance with plant standard operating procedures."*
