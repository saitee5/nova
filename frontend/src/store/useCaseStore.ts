/**
 * frontend/src/store/useCaseStore.ts
 *
 * Zustand store for VIGIL case state and WebSocket status.
 * No `any` — all types imported from ../types/api.
 */
import { create } from 'zustand'
import type {
  Case,
  EvidenceItem,
  HistoricalMatch,
  PipelineStage,
  RiskTier,
  WsStatus,
} from '../types/api'

// Re-export for consumers that import from the store file
export type { PipelineStage, RiskTier, WsStatus }

// ── Stage derivation (pure function — no store reads) ─────────────────── //

/**
 * Map a backend case `state` string to a PipelineStage for the UI stepper.
 *
 * Mapping (from master doc):
 *   DETECTED | INVESTIGATING        → 'signals'
 *   NOTIFYING | AWAITING_RESPONSE   → 'voice'
 *   ACTING                          → 'confirm'
 *   MONITORING | RESOLVING          → 'audit'
 *   RESOLVED | ARCHIVED             → 'memory'
 *
 * 'retrieval' is a sub-state of 'signals' triggered by risk.updated events,
 * not by case state — handled separately in useSessionSocket.
 */
export function deriveStage(caseState: string): PipelineStage | null {
  switch (caseState.toUpperCase()) {
    case 'DETECTED':
    case 'INVESTIGATING':
      return 'signals'
    case 'NOTIFYING':
    case 'AWAITING_RESPONSE':
      return 'voice'
    case 'ACTING':
      return 'confirm'
    case 'MONITORING':
    case 'RESOLVING':
      return 'audit'
    case 'RESOLVED':
    case 'ARCHIVED':
      return 'memory'
    default:
      return null
  }
}

// ── Store interface ──────────────────────────────────────────────────── //

interface CaseState {
  // ── data ──────────────────────────────────────────────────────────── //
  cases: Case[]
  activeCase: Case | null
  currentStage: PipelineStage | null
  evidenceList: EvidenceItem[]
  retrievalMatches: HistoricalMatch[]
  latencyMarks: Record<string, number>
  connectionStatus: WsStatus

  // ── actions ───────────────────────────────────────────────────────── //
  setCases: (cases: Case[]) => void
  setActiveCase: (c: Case | null) => void
  /** Update case state string; re-derives currentStage automatically. */
  updateCaseStage: (caseId: string, state: string) => void
  setWsStatus: (s: WsStatus) => void
  appendEvidence: (items: EvidenceItem[]) => void
  setLatencyMark: (key: string, ts: number) => void
}

// ── Store implementation ─────────────────────────────────────────────── //

export const useCaseStore = create<CaseState>((set) => ({
  cases: [],
  activeCase: null,
  currentStage: null,
  evidenceList: [],
  retrievalMatches: [],
  latencyMarks: {},
  connectionStatus: 'disconnected',

  setCases: (cases) => set({ cases }),

  setActiveCase: (c) =>
    set({
      activeCase: c,
      currentStage: c ? deriveStage(c.state) : null,
    }),

  updateCaseStage: (caseId, state) =>
    set((prev) => {
      const updatedCases = prev.cases.map((c) =>
        c.case_id === caseId ? { ...c, state } : c,
      )
      const updatedActive =
        prev.activeCase?.case_id === caseId
          ? { ...prev.activeCase, state }
          : prev.activeCase

      return {
        cases: updatedCases,
        activeCase: updatedActive,
        currentStage: updatedActive ? deriveStage(updatedActive.state) : prev.currentStage,
      }
    }),

  setWsStatus: (connectionStatus) => set({ connectionStatus }),

  appendEvidence: (items) =>
    set((prev) => ({
      evidenceList: [...prev.evidenceList, ...items],
    })),

  setLatencyMark: (key, ts) =>
    set((prev) => ({
      latencyMarks: { ...prev.latencyMarks, [key]: ts },
    })),
}))
