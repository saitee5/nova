/**
 * frontend/src/types/industrial.ts
 *
 * Strongly-typed domain contracts for petrochemical plant operations,
 * mirroring backend/models/industrial_domain.py and backend/models/evidence.py.
 */

export type OperatingMode =
  | 'NORMAL'
  | 'STARTUP'
  | 'SHUTDOWN'
  | 'TURNDOWN'
  | 'HOT_STANDBY'
  | 'MAINTENANCE'
  | 'DEGRADED'
  | 'EMERGENCY_TRIP'
  | 'STEADY_STATE'
  | 'RAMP_UP'
  | 'RAMP_DOWN'
  | 'EMERGENCY'
  | 'UNKNOWN'

export type SensorQuality = 'GOOD' | 'UNCERTAIN' | 'BAD' | 'SUBSTITUTED'

export type RiskTier = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export type EpisodeStatus =
  | 'NORMAL'
  | 'DEVIATION'
  | 'ANOMALY'
  | 'DIAGNOSIS'
  | 'ELEVATED_RISK'
  | 'MITIGATION_OBSERVATION'
  | 'RESOLVED'

export type MLAssessmentStatus =
  | 'OK'
  | 'SUCCESS'
  | 'MODEL_NOT_AVAILABLE'
  | 'INVALID_INPUT'
  | 'INFERENCE_ERROR'

export interface ProcessTelemetry {
  asset_id: string
  tag: string
  timestamp: string
  value: number
  unit: string
  quality: SensorQuality
  source: string
  operating_mode: OperatingMode
  event_id?: string
  plant_id?: string
  unit_id?: string
  asset_type?: string | null
  sensor_id?: string | null
  parameter?: string | null
  provenance?: string
}

export interface OperationalEvent {
  event_id: string
  timestamp: string
  asset_id: string
  event_type: string
  source: string
  schema_version?: string
  payload?: Record<string, unknown>
  provenance?: string
}

export interface Plant {
  plant_id: string
  name: string
  location: string
  units: string[]
}

export interface Unit {
  unit_id: string
  plant_id: string
  name: string
  unit_type: string
  assets: string[]
}

export interface Asset {
  asset_id: string
  unit_id: string
  name: string
  asset_class: string
  criticality: RiskTier
  operating_mode?: OperatingMode
  tags?: string[]
  description?: string
  key_tags?: string[]
}

export interface Sensor {
  sensor_id: string
  tag: string
  equipment_id: string
  sensor_type: string
  unit: string
  min_range: number
  max_range: number
  alarm_high: number
  alarm_low: number
}

export interface ProcessTag {
  tag: string
  description: string
  unit: string
  current_value?: number | null
  quality: SensorQuality
}

export interface Alarm {
  alarm_id: string
  tag: string
  asset_id: string
  severity: RiskTier
  message: string
  timestamp: string
  acknowledged: boolean
  parameter?: string | null
  value?: number | null
  threshold?: number | null
  state?: string
}

export interface MaintenanceRecord {
  record_id: string
  asset_id: string
  work_order: string
  description: string
  logged_at: string
  status: string
  type?: string
  start_time?: string | null
  planned_end_time?: string | null
  crew?: string[]
}

export interface Permit {
  permit_id: string
  permit_type: string
  asset_id: string
  issued_to: string
  status: string
  valid_from?: string | null
  valid_until?: string | null
  zone_id?: string | null
  affected_assets?: string[]
  start_time?: string | null
  end_time?: string | null
}

export interface OccupancyRecord {
  zone_id: string
  personnel_count: number
  updated_at: string
  timestamp?: string | null
  source?: string
}

export interface MLAssessment {
  model_name: string
  model_version: string
  status: MLAssessmentStatus | string
  prediction?: Record<string, unknown> | null
  score?: number | null
  confidence?: number | null
  labels?: string[]
  features_used?: string[]
  provenance?: Record<string, unknown>
  evaluated_at: string
  timestamp?: string | null
}

export interface IndustrialRiskAssessment {
  assessment_id: string
  asset_id: string
  timestamp: string
  risk_score: number // 0.0 to 1.0
  risk_tier: RiskTier
  process_anomaly_factor?: number
  equipment_condition_factor?: number
  alarm_state_factor?: number
  permit_simops_factor?: number
  personnel_exposure_factor?: number
  factors?: Record<string, number>
  policy_version?: string
  model_versions?: Record<string, string>
  advisory_only: boolean
  explanation: string
  recommended_actions: string[]
}

export interface OperationalEpisode {
  episode_id: string
  plant_id: string
  unit_id: string
  asset_id: string
  assets: string[]
  operating_mode: OperatingMode
  status: EpisodeStatus
  title: string
  start_time: string
  end_time?: string | null
  severity: RiskTier
  trigger?: Record<string, unknown>
  telemetry_summary?: Record<string, unknown>
  ml_assessments?: MLAssessment[]
  alarms?: Alarm[]
  maintenance?: MaintenanceRecord[]
  permits?: Permit[]
  occupancy?: OccupancyRecord | null
  risk_assessment?: IndustrialRiskAssessment | null
  summary: string
  root_causes: string[]
  tags?: string[]
  outcome?: string | null
  provenance?: Record<string, unknown>
}

export interface PlantState {
  plant_id: string
  unit_id: string
  timestamp: string
  operating_mode: OperatingMode
  telemetry: Record<string, ProcessTelemetry>
  active_alarms: Alarm[]
  equipment_status: Record<string, string>
  active_maintenance: MaintenanceRecord[]
  active_permits: Permit[]
  occupancy: Record<string, number>
  recent_events?: OperationalEvent[]
  metadata?: {
    throughput_tph?: number
    power_mw?: number
    co2_rate_tph?: number
    safety_status?: string
    simops_active?: boolean
    [key: string]: unknown
  }
}

export interface EvidenceItem {
  source: string
  fact: string
  raw_value: unknown
  ts: string
  weight: number
}

export interface HistoricalMatch {
  record_id: string
  collection: string
  similarity_score: number
  rerank_score?: number | null
  title: string
  date: string
  matched_on: string[]
  metadata?: Record<string, unknown>
}

export interface EvidencePackage {
  package_id: string
  timestamp: string
  plant_id: string
  unit_id: string
  asset_id: string
  plant_state?: Record<string, unknown> | null
  ml_assessments?: Record<string, unknown>
  risk_assessment?: Record<string, unknown> | null
  active_alarms?: Record<string, unknown>[]
  maintenance_records?: Record<string, unknown>[]
  permits?: Record<string, unknown>[]
  occupancy?: Record<string, unknown> | null
  historical_matches?: HistoricalMatch[]
  engineering_knowledge?: Record<string, unknown>[]
  evidence_items?: EvidenceItem[]
  provenance?: Record<string, unknown>
}

export interface CopilotQueryRequest {
  prompt: string
  asset_id?: string
}

export interface CopilotQueryResponse {
  response: string
  spoken_text?: string
  evidence_package?: EvidencePackage
  recommended_actions: string[]
  advisory_only: boolean
}

export interface MemorySearchRequest {
  query: string
  collection?: string
  top_k?: number
}

export interface MemorySearchResponse {
  query: string
  collection: string
  matches: Array<{
    id?: string
    score?: number
    payload?: Record<string, unknown>
    [key: string]: unknown
  }>
  error?: string
}

export interface TimeseriesPoint {
  timestamp: string
  value: number
  quality?: string
}

export interface AlarmAcknowledgeResponse {
  status: string
  alarm_id: string
  acknowledged_by: string
  acknowledged_at: string
}

export interface RiskSnapshot {
  assessment_id: string
  asset_id: string
  episode_id?: string
  timestamp: string
  risk_score: number
  risk_tier: string
  factors: Record<string, number>
  policy_version?: string
  advisory_only: boolean
}
