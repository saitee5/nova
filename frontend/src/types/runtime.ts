/**
 * frontend/src/types/runtime.ts
 *
 * Strongly-typed domain contracts for the NOVA Runtime / HITL workflow,
 * mirroring backend/runtime/models.py.
 */

export type RuntimeCaseState =
  | 'READY_FOR_REVIEW'
  | 'UNDER_REVIEW'
  | 'ACTION_SELECTED'
  | 'APPROVED'
  | 'REJECTED'
  | 'RESOLVED'
  | 'CLOSED'

export type ActionStatus =
  | 'AVAILABLE'
  | 'SELECTED'
  | 'APPROVED'
  | 'REJECTED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'BLOCKED'

export type CasePriority = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export type DecisionOutcome = 'APPROVE' | 'REJECT'

export interface OperatorAction {
  action_id: string
  action_name: string
  title: string
  description: string
  reason: string
  priority: CasePriority
  risk_level: string
  supporting_evidence_refs: string[]
  required_approval: boolean
  safety_constraints: string[]
  status: ActionStatus
  is_blocked: boolean
  blocked_reason?: string | null
  parameters?: Record<string, unknown>
}

export interface RuntimeDecision {
  decision: DecisionOutcome
  action_id: string
  actor: string
  reason?: string
  timestamp?: string
}

export interface RuntimeCase {
  case_id: string
  operational_case_ref: string
  equipment_id: string
  runtime_state: RuntimeCaseState
  priority: CasePriority
  selected_action_id?: string | null
  actor?: string | null
  resolution_summary?: string | null
  created_at: string
  updated_at: string
  resolved_at?: string | null
  closed_at?: string | null
}

export interface EvidenceSummary {
  knowledge_count: number
  maintenance_count: number
  safety_count: number
  permit_count: number
  incident_count: number
  top_knowledge: Record<string, unknown>[]
  top_safety: Record<string, unknown>[]
  top_maintenance: Record<string, unknown>[]
}

export interface MLSummary {
  model_name: string
  status: string
  is_available: boolean
  predicted_value?: unknown
  confidence?: number | null
  summary: string
}

export interface TimelineEvent {
  event_id: string
  case_id: string
  event_type: string
  description: string
  actor?: string | null
  decision?: string | null
  previous_state?: string | null
  new_state?: string | null
  timestamp: string
  payload?: Record<string, unknown> | null
}

export interface RuntimeResult {
  case_id: string
  equipment_id: string
  unit_area: string
  runtime_state: RuntimeCaseState
  priority: CasePriority
  title: string
  summary: string
  overall_state: string
  operator_actions: OperatorAction[]
  evidence_summary: EvidenceSummary
  ml_summaries: MLSummary[]
  risk_indicators: Record<string, unknown>[]
  safety_constraints: string[]
  limitations: string[]
  provenance_note: string
  scenario_type?: string | null
  selected_action_id?: string | null
  resolution_summary?: string | null
  actor?: string | null
  timeline_events: TimelineEvent[]
  created_at: string
  updated_at: string
  resolved_at?: string | null
  closed_at?: string | null
}

export interface RuntimeAuditRecord {
  record_id: string
  case_id: string
  event_type: string
  action?: string | null
  actor: string
  decision?: string | null
  payload?: Record<string, unknown>
  timestamp: string
}

export interface TransitionRequest {
  to_state: RuntimeCaseState
  actor?: string
}

export interface SelectActionRequest {
  action_id: string
  actor?: string
}

export interface DecisionRequest {
  decision: DecisionOutcome
  action_id: string
  actor: string
  reason?: string
}

export interface ResolveRequest {
  resolution_summary: string
  actor?: string
}

export interface CloseRequest {
  actor?: string
}
