# NOVA Operational Episode Lifecycle Specification

**Owner Module:** `backend/services/episode_engine.py`  
**Class Name:** `OperationalEpisodeEngine`  
**Database Table:** `operational_episodes`

---

## 1. Episode Purpose & Concept

An **Operational Episode** represents a coherent historical timeline tracking a process upset, deviation, or incident from inception to resolution. Rather than treating events as disconnected logs, an episode binds together:
- Telemetry summary & sliding window stats
- Correlated ML assessments (anomaly, fault diagnosis, temperature forecasts)
- Active process alarms
- Concurrent permits-to-work and maintenance logs
- Zone personnel occupancy
- Deterministic industrial risk assessments
- Operator mitigation steps and final resolution outcomes

---

## 2. Seven-Stage Lifecycle Progression

```text
    ┌──────────────┐
    │    NORMAL    │ Nominal steady-state monitoring
    └──────┬───────┘
           │ (Minor parameter drift, low alarm)
           ▼
    ┌──────────────┐
    │  DEVIATION   │ Parameter exceeding statistical baseline
    └──────┬───────┘
           │ (ML anomaly detector score > 0.5)
           ▼
    ┌──────────────┐
    │   ANOMALY    │ Statistically confirmed multivariate anomaly
    └──────┬───────┘
           │ (Fault classifier identifies root cause)
           ▼
    ┌──────────────┐
    │  DIAGNOSIS   │ Specific disturbance or equipment fault identified
    └──────┬───────┘
           │ (Risk tier reaches HIGH or CRITICAL / SIMOPS conflict)
           ▼
    ┌──────────────┐
    │ELEVATED_RISK │ Active advisory alert; supervisor intervention recommended
    └──────┬───────┘
           │ (Operator acknowledges and initiates SOP action)
           ▼
┌──────────────────────┐
│MITIGATION_OBSERVATION│ Monitoring plant response to operator action
└──────────┬───────────┘
           │ (Parameters return to normal envelope)
           ▼
    ┌──────────────┐
    │   RESOLVED   │ Episode archived to database with outcome summary
    └──────────────┘
```

---

## 3. Correlation & Database Persistence

1. **Active Episodes:** Held in high-speed in-memory cache keyed by `asset_id`.
2. **Correlation Updates:** As new telemetry, alarms, permits, or ML assessments arrive, `correlate_observation(...)` aggregates observations into the active episode.
3. **Resolution & Archival:** When transitioned to `RESOLVED`, the episode's `end_time` and `outcome` are recorded, and the full record is persisted into `operational_episodes` in PostgreSQL/SQLite for long-term audit and semantic embedding.
