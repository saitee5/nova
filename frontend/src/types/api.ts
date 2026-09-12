/**
 * frontend/src/types/api.ts
 *
 * Shared TypeScript types that mirror the backend Pydantic models.
 * No `any` — use `unknown` and narrow where JSON payloads are untyped.
 */

// ── Pipeline / UI state ─────────────────────────────────────────────────── //

export type PipelineStage =
  | 'signals'
  | 'retrieval'
  | 'voice'
  | 'confirm'
  | 'audit'
  | 'memory'

export type RiskTier = 'low' | 'medium' | 'high' | 'critical'

export type WsStatus = 'connected' | 'disconnected' | 'reconnecting'

// ── Case models ─────────────────────────────────────────────────────────── //

export interface Case {
  case_id: string
  zone_id: string
  state: string
  risk_tier: RiskTier
  compound_score: number
  authorized: boolean
  authorized_by: string | null
  authorized_at: string | null
  created_at: string
  updated_at: string
}

export interface AuditEntry {
  id: number
  case_id: string
  action: string
  actor: string
  decision: string | null
  payload: Record<string, unknown> | null
  ts: string
}

export interface AuthResult {
  case_id: string
  authorized: boolean
  decision: 'yes' | 'no'
  ts: string
}

// ── Risk models ─────────────────────────────────────────────────────────── //

export interface ZoneStatus {
  zone_id: string
  tier: RiskTier
  compound_score: number
  active_case_id: string | null
}

export interface EvidenceItem {
  evidence_id: string
  source: string
  description: string
  value: number | null
  unit: string | null
  weight: number
  ts: string
  metadata: Record<string, unknown>
}

export interface HistoricalMatch {
  match_id: string
  collection: string
  similarity_score: number
  description: string
  occurred_at: string | null
  outcome: string | null
  metadata: Record<string, unknown>
}

// ── Retrieval ────────────────────────────────────────────────────────────── //

export interface RetrievalResponse {
  case_id: string
  matches: HistoricalMatch[]
  pipeline_steps: Record<string, number>
}

// ── Voice ────────────────────────────────────────────────────────────────── //

export interface TranscriptLine {
  speaker: 'vigil' | 'officer'
  text: string
  ts: string
}

export interface VoiceStatus {
  case_id: string
  transcript: TranscriptLine[]
  latency_marks: Record<string, number>
}

// ── Memory ───────────────────────────────────────────────────────────────── //

export interface CollectionRecords {
  name: string
  records: Record<string, unknown>[]
}

// ── Demo ─────────────────────────────────────────────────────────────────── //

export interface DemoStatus {
  active_scenario: string | null
  playing: boolean
}

// ── WebSocket envelope types (§11.5) ─────────────────────────────────────── //

export interface RiskUpdatedPayload {
  zone_id: string
  case_id: string
  compound_score: number
  tier: RiskTier
  evidence: EvidenceItem[]
}

export type WsEnvelope =
  | {
      type: 'connection.status'
      payload: { status: string; session_id: string }
      ts: string
    }
  | {
      type: 'risk.updated'
      payload: RiskUpdatedPayload
      ts: string
    }
  | {
      type: 'case.state_changed'
      payload: { case_id: string; new_state: string }
      ts: string
    }
  | {
      type: 'transcript.delta'
      payload: { case_id: string; speaker: 'vigil' | 'officer'; text: string }
      ts: string
    }
  | {
      type: 'audit.entry'
      payload: AuditEntry
      ts: string
    }
  | {
      type: 'authorization.requested'
      payload: { case_id: string; tool_name: string; action_preview: string }
      ts: string
    }
  | {
      type: 'interruption.detected'
      payload: { case_id: string }
      ts: string
    }
