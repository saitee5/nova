import { create } from 'zustand'
import { EquipmentItem } from '../components/plant-twin/types'
import { EQUIPMENT_ITEMS } from '../components/plant-twin/data/equipmentLayout'
import { getRiskState } from '../components/plant-twin/utils/riskUtils'
import { toCanonicalAssetId, toDisplayTag } from '../utils/assetAliases'
import {
  getPlantState,
  getRisk,
  getAlarms,
  getEpisodes,
  getRuntimeCases,
  getRuntimeCase,
  selectRuntimeAction,
  decideRuntimeCase,
  acknowledgeAlarm,
  queryCopilot,
} from '../services/api'
import type { Alarm, OperationalEpisode, PlantState, IndustrialRiskAssessment } from '../types/industrial'
import type { OperatorAction, RuntimeCase } from '../types/runtime'
import type { WsEnvelope } from '../types/api'
import { voiceService } from '../services/voiceService'

export type AlertStatus =
  | 'NEW'
  | 'ACKNOWLEDGED'
  | 'INVESTIGATING'
  | 'MITIGATED'
  | 'RESOLVED'
  | 'DISMISSED'

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low'

export interface RealtimeAlert {
  id: string
  title: string
  equipmentId: string
  equipmentTag: string
  equipmentName: string
  bayId: string
  severity: AlertSeverity
  message: string
  aiExplanation: string
  status: AlertStatus
  timestamp: string
  riskScore: number
  signalDeltas: {
    signal: string
    current: number
    baseline: number
    unit: string
    deltaPercent: number
  }[]
  historicalMatchCount: number
  suggestedAction: string
}

export interface CompoundAnomaly {
  id: string
  title: string
  equipmentIds: string[]
  primaryEquipmentTag: string
  bayId: string
  severity: AlertSeverity
  correlationScore: number // 0 - 1
  signals: {
    name: string
    value: string
    trend: 'rising' | 'falling' | 'oscillating'
  }[]
  novaExplanation: string
  recommendedMitigation: string
  confidence: number
}

export interface SystemHealth {
  telemetryWs: 'connected' | 'reconnecting' | 'disconnected'
  simulator: 'running' | 'stopped'
  aiPipelineLatencyMs: number
  qdrantStatus: 'healthy' | 'degraded' | 'offline'
  voiceEngineStatus: 'ready' | 'active' | 'error'
  lastSyncTimestamp: string
  signalsPerSecond: number
}

export type VoiceState =
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'interrupted'
  | 'error'

export interface CopilotMessage {
  id: string
  sender: 'user' | 'nova'
  text: string
  timestamp: string
  recommendation?: {
    actionTitle: string
    targetEquipmentTag: string
    confidencePercent: number
    evidenceCount: number
    correlatedSignalsCount: number
    approved: boolean
  }
}

interface RealtimeStoreState {
  // Plant State
  plantName: string
  plantStatus: 'Running' | 'Degraded' | 'Critical'
  throughputRate: number // t/h
  powerConsumptionMw: number
  co2EmissionsRate: number // t/h
  safetyStatus: 'Normal' | 'Warning' | 'Alert'

  // Server state caches
  plantStateData: PlantState | null
  overallRiskData: IndustrialRiskAssessment | null
  runtimeCases: RuntimeCase[]
  isLiveLoading: boolean
  isLiveConnected: boolean
  serverError: string | null
  isActionLoading: boolean
  actionError: string | null
  lastLiveFetch: string | null

  // Equipment Map
  equipment: Record<string, EquipmentItem>

  // Alerts & Anomalies
  alerts: RealtimeAlert[]
  compoundAnomalies: CompoundAnomaly[]

  // Selected entities for contextual navigation
  selectedEquipmentId: string | null
  selectedBayId: string | null
  selectedAlertId: string | null

  // System Health
  systemHealth: SystemHealth

  // Copilot & Voice state
  isCopilotOpen: boolean
  voiceState: VoiceState
  copilotMessages: CopilotMessage[]
  copilotStreaming: boolean
  activeVoiceTranscript: string

  // Notification Queue
  toastNotifications: {
    id: string
    type: 'info' | 'warning' | 'high' | 'critical'
    title: string
    message: string
  }[]

  // Core Actions
  fetchLivePlantData: () => Promise<void>
  approveMitigationAction: (
    caseId?: string,
    actionId?: string,
    actor?: string
  ) => Promise<{ success: boolean; blocked?: boolean; reason?: string }>
  selectEquipment: (id: string | null) => void
  selectBay: (bayId: string | null) => void
  selectAlert: (alertId: string | null) => void
  openCopilot: (initialContext?: { tag?: string; prompt?: string }) => void
  closeCopilot: () => void
  toggleCopilot: () => void
  setVoiceState: (state: VoiceState) => void
  autoSpeakVoice: boolean
  voiceLatencyMs: number | null
  toggleAutoSpeakVoice: () => void
  speakCopilotMessage: (text: string) => Promise<void>
  bargeInVoice: () => void
  updateAlertStatus: (alertId: string, status: AlertStatus) => Promise<void>
  sendUserMessage: (text: string, fromVoice?: boolean) => Promise<void>
  approveRecommendation: (actionId?: string) => Promise<void>
  dismissToast: (id: string) => void
  triggerManualMitigation: (equipmentId: string) => void
  handleWsMessage: (msg: WsEnvelope) => void
}

// Initial Equipment Dictionary preserved for 3D coordinates & spatial layout
const INITIAL_EQUIPMENT_RECORD = EQUIPMENT_ITEMS.reduce<Record<string, EquipmentItem>>(
  (acc, item) => {
    acc[item.id] = {
      ...item,
      riskScore: 0,
      activeAlerts: [],
      trend: item.trend || [],
    }
    return acc
  },
  {}
)

export const useRealtimeStore = create<RealtimeStoreState>((set, get) => ({
  plantName: 'NOVA Petrochemical Complex — Bay 1–6',
  plantStatus: 'Running',
  throughputRate: 0,
  powerConsumptionMw: 0,
  co2EmissionsRate: 0,
  safetyStatus: 'Normal',

  plantStateData: null,
  overallRiskData: null,
  runtimeCases: [],
  isLiveLoading: false,
  isLiveConnected: false,
  serverError: null,
  isActionLoading: false,
  actionError: null,
  lastLiveFetch: null,

  equipment: INITIAL_EQUIPMENT_RECORD,
  alerts: [],
  compoundAnomalies: [],

  selectedEquipmentId: null,
  selectedBayId: null,
  selectedAlertId: null,

  systemHealth: {
    telemetryWs: 'disconnected',
    simulator: 'running',
    aiPipelineLatencyMs: 0,
    qdrantStatus: 'healthy',
    voiceEngineStatus: 'ready',
    lastSyncTimestamp: new Date().toISOString(),
    signalsPerSecond: 0,
  },

  isCopilotOpen: false,
  voiceState: 'idle',
  autoSpeakVoice: true,
  voiceLatencyMs: 142,
  copilotMessages: [
    {
      id: 'msg-init',
      sender: 'nova',
      text: 'Good day, Operator. NOVA Operational Intelligence is connected to plant telemetry. Inquire about any asset, alarm, or active compound anomaly.',
      timestamp: new Date().toLocaleTimeString(),
    },
  ],
  copilotStreaming: false,
  activeVoiceTranscript: '',
  toastNotifications: [],

  // ── Live Backend Synchronization ────────────────────────────────────────── //

  fetchLivePlantData: async () => {
    try {
      set({ isLiveLoading: true })

      const [plantState, overallRisk, rawAlarms, rawEpisodes, cases] =
        await Promise.all([
          getPlantState().catch(() => null),
          getRisk().catch(() => null),
          getAlarms().catch(() => [] as Alarm[]),
          getEpisodes().catch(() => [] as OperationalEpisode[]),
          getRuntimeCases().catch(() => [] as RuntimeCase[]),
        ])

      if (!plantState) {
        set({
          isLiveLoading: false,
          isLiveConnected: false,
          serverError: 'Plant state API unavailable',
        })
        return
      }

      // 1. Map Plant State KPIs
      const meta = plantState.metadata || {}
      const throughputRate = typeof meta.throughput_tph === 'number' ? meta.throughput_tph : 0
      const powerConsumptionMw = typeof meta.power_mw === 'number' ? meta.power_mw : 0
      const co2EmissionsRate = typeof meta.co2_rate_tph === 'number' ? meta.co2_rate_tph : 0

      let plantStatus: 'Running' | 'Degraded' | 'Critical' = 'Running'
      if (plantState.operating_mode === 'EMERGENCY_TRIP' || plantState.operating_mode === 'EMERGENCY') {
        plantStatus = 'Critical'
      } else if (
        plantState.operating_mode === 'DEGRADED' ||
        plantState.operating_mode === 'TURNDOWN' ||
        rawAlarms.some((a) => a.severity === 'CRITICAL')
      ) {
        plantStatus = 'Degraded'
      }

      const safetyStatus: 'Normal' | 'Warning' | 'Alert' =
        rawAlarms.some((a) => a.severity === 'CRITICAL')
          ? 'Alert'
          : rawAlarms.length > 0
          ? 'Warning'
          : 'Normal'

      // 2. Map Alarms into RealtimeAlerts
      const mappedAlerts: RealtimeAlert[] = rawAlarms.map((a) => {
        const displayTag = toDisplayTag(a.asset_id)
        const sevLower = (a.severity.toLowerCase() as AlertSeverity) || 'medium'
        const riskScore =
          sevLower === 'critical' ? 88 : sevLower === 'high' ? 68 : sevLower === 'medium' ? 45 : 20

        return {
          id: a.alarm_id,
          title: a.message || `${a.severity} Alarm on ${displayTag}`,
          equipmentId: displayTag,
          equipmentTag: displayTag,
          equipmentName: `${displayTag} Monitored Equipment`,
          bayId: 'bay-3',
          severity: sevLower,
          message: a.message,
          aiExplanation: `Evaluated by NOVA Safety Logic for asset ${a.asset_id} (${displayTag}). Parameter ${a.parameter || 'reading'}: ${a.value !== null && a.value !== undefined ? a.value : 'threshold reached'}.`,
          status: a.acknowledged
            ? 'ACKNOWLEDGED'
            : a.state === 'ACTIVE'
            ? 'NEW'
            : 'RESOLVED',
          timestamp: new Date(a.timestamp).toLocaleTimeString(),
          riskScore,
          signalDeltas: [
            {
              signal: a.parameter || 'Process Sensor',
              current: a.value ?? 0,
              baseline: a.threshold ?? 0,
              unit: '',
              deltaPercent:
                a.threshold && a.value
                  ? Math.round(((a.value - a.threshold) / a.threshold) * 100)
                  : 0,
            },
          ],
          historicalMatchCount: 2,
          suggestedAction: `Inspect ${displayTag} process variables and verify safety margins.`,
        }
      })

      // 3. Map OperationalEpisodes into CompoundAnomalies
      const mappedAnomalies: CompoundAnomaly[] = rawEpisodes.map((ep) => {
        const primaryTag = toDisplayTag(ep.asset_id)
        const eqIds = (ep.assets || [ep.asset_id]).map(toDisplayTag)

        const signals = Object.entries(ep.telemetry_summary || {}).map(
          ([key, val]) => ({
            name: `${primaryTag} ${key}`,
            value: typeof val === 'number' ? val.toFixed(1) : String(val),
            trend: 'rising' as const,
          })
        )

        return {
          id: ep.episode_id,
          title: ep.title,
          equipmentIds: eqIds,
          primaryEquipmentTag: primaryTag,
          bayId: 'bay-3',
          severity: (ep.severity.toLowerCase() as AlertSeverity) || 'high',
          correlationScore: ep.risk_assessment ? ep.risk_assessment.risk_score : 0.92,
          signals: signals.length > 0 ? signals : [
            { name: `${primaryTag} Temperature`, value: 'Elevated', trend: 'rising' },
            { name: `${primaryTag} Vibration`, value: 'Elevated', trend: 'rising' },
          ],
          novaExplanation:
            ep.summary ||
            (ep.root_causes && ep.root_causes.length > 0
              ? ep.root_causes.join('; ')
              : 'Cross-unit process correlation indicates multi-signal deviation across operating boundaries.'),
          recommendedMitigation:
            ep.risk_assessment?.recommended_actions?.[0] ||
            'Verify control margins, review SIMOPS constraints, and execute advisory mitigation procedure.',
          confidence: 0.95,
        }
      })

      // 4. Update Equipment Operational State from Backend Telemetry
      const updatedEquipment = { ...get().equipment }
      const telemMap = plantState.telemetry || {}

      Object.keys(updatedEquipment).forEach((eqId) => {
        const item = { ...updatedEquipment[eqId] }
        const canonicalId = toCanonicalAssetId(item.tag || item.id)

        // Find relevant telemetry
        let tempVal: number | undefined
        let vibVal: number | undefined
        let presVal: number | undefined
        let flowVal: number | undefined

        Object.values(telemMap).forEach((t) => {
          if (t.asset_id === canonicalId) {
            const param = (t.parameter || t.tag || '').toLowerCase()
            if (param.includes('temp') || param.includes('ti-')) tempVal = t.value
            else if (param.includes('vib') || param.includes('vi-')) vibVal = t.value
            else if (param.includes('pres') || param.includes('pi-')) presVal = t.value
            else if (param.includes('flow') || param.includes('fi-')) flowVal = t.value
          }
        })

        if (tempVal !== undefined || vibVal !== undefined || presVal !== undefined) {
          item.telemetry = {
            ...item.telemetry,
            ...(tempVal !== undefined ? { temperature: tempVal } : {}),
            ...(vibVal !== undefined ? { vibration: vibVal } : {}),
            ...(presVal !== undefined ? { pressure: presVal } : {}),
            ...(flowVal !== undefined ? { flow: flowVal } : {}),
            lastUpdated: new Date().toISOString(),
          }
        }

        // Status from plant equipment_status
        const beStatus = plantState.equipment_status[canonicalId]
        if (beStatus) {
          item.status = beStatus === 'OPERATIONAL' ? 'running' : 'alarm'
        }

        // Check if there are active alarms for this equipment
        const eqAlarms = mappedAlerts.filter((a) => a.equipmentTag === item.tag)
        item.activeAlerts = eqAlarms.map((a) => ({
          id: a.id,
          severity: a.severity,
          message: a.message,
          timestamp: a.timestamp,
        }))

        // Derive risk score
        if (overallRisk && (canonicalId === overallRisk.asset_id || item.tag === toDisplayTag(overallRisk.asset_id))) {
          item.riskScore = Math.round(overallRisk.risk_score * 100)
        } else if (eqAlarms.length > 0) {
          item.riskScore = Math.max(...eqAlarms.map((a) => a.riskScore))
        } else {
          item.riskScore = 15 // Nominal low
        }

        item.anomalyDetected = eqAlarms.some(
          (a) => a.severity === 'critical' || a.severity === 'high'
        )

        updatedEquipment[eqId] = item
      })

      set({
        plantStateData: plantState,
        overallRiskData: overallRisk,
        runtimeCases: cases,
        plantStatus,
        safetyStatus,
        throughputRate,
        powerConsumptionMw,
        co2EmissionsRate,
        alerts: mappedAlerts,
        compoundAnomalies: mappedAnomalies,
        equipment: updatedEquipment,
        isLiveLoading: false,
        isLiveConnected: true,
        serverError: null,
        lastLiveFetch: new Date().toISOString(),
        systemHealth: {
          telemetryWs: 'connected',
          simulator: 'running',
          aiPipelineLatencyMs: 85,
          qdrantStatus: 'healthy',
          voiceEngineStatus: 'ready',
          lastSyncTimestamp: new Date().toISOString(),
          signalsPerSecond: Object.keys(telemMap).length * 15 || 850,
        },
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      set({
        isLiveLoading: false,
        isLiveConnected: false,
        serverError: msg,
      })
    }
  },

  // ── Runtime / HITL Real Decision Execution ──────────────────────────────── //

  approveMitigationAction: async (caseId?: string, actionId?: string, actor = 'lead_operator') => {
    set({ isActionLoading: true, actionError: null })
    try {
      // 1. Identify RuntimeCase
      let targetCaseId = caseId
      if (!targetCaseId) {
        const cases = await getRuntimeCases()
        const activeCase =
          cases.find((c) => c.runtime_state !== 'CLOSED' && c.runtime_state !== 'RESOLVED') ||
          cases[0]
        if (activeCase) {
          targetCaseId = activeCase.case_id
        }
      }

      if (!targetCaseId) {
        throw new Error('No active runtime case available for operator decision.')
      }

      // 2. Fetch full presentation to verify actions and SafetyGuard constraints
      const presentation = await getRuntimeCase(targetCaseId)
      let actionToExecute: OperatorAction | undefined
      if (actionId) {
        actionToExecute = presentation.operator_actions.find((a) => a.action_id === actionId)
      } else {
        // Pick first non-blocked action
        actionToExecute =
          presentation.operator_actions.find((a) => !a.is_blocked) ||
          presentation.operator_actions[0]
      }

      if (!actionToExecute) {
        throw new Error(`No advisory operator action found for case ${targetCaseId}`)
      }

      // 3. SafetyGuard Verification — never bypass or hide blocked reason
      if (actionToExecute.is_blocked) {
        const blockReason =
          actionToExecute.blocked_reason ||
          'Action blocked by backend SafetyGuard: safety constraints violated.'
        set((state) => ({
          isActionLoading: false,
          actionError: blockReason,
          toastNotifications: [
            ...state.toastNotifications,
            {
              id: `toast-${Date.now()}`,
              type: 'critical',
              title: 'SAFETYGUARD BLOCKED ACTION',
              message: blockReason,
            },
          ],
        }))
        return { success: false, blocked: true, reason: blockReason }
      }

      // 4. State transition: select action if in review state
      if (
        presentation.runtime_state === 'READY_FOR_REVIEW' ||
        presentation.runtime_state === 'UNDER_REVIEW'
      ) {
        try {
          await selectRuntimeAction(targetCaseId, {
            action_id: actionToExecute.action_id,
            actor,
          })
        } catch {
          // May already have transitioned
        }
      }

      // 5. Submit typed RuntimeDecision to backend RuntimeService
      const updatedCase = await decideRuntimeCase(targetCaseId, {
        decision: 'APPROVE',
        action_id: actionToExecute.action_id,
        actor,
      })

      // 6. Refresh case and plant state from real backend
      await get().fetchLivePlantData()

      // 7. Emit success notification
      set((state) => ({
        isActionLoading: false,
        toastNotifications: [
          ...state.toastNotifications,
          {
            id: `toast-${Date.now()}`,
            type: 'high',
            title: 'RUNTIME DECISION APPROVED',
            message: `Action '${actionToExecute?.title}' approved for ${targetCaseId}. State: ${updatedCase.runtime_state}. Audited to immutable log.`,
          },
        ],
      }))

      return { success: true }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      set((state) => ({
        isActionLoading: false,
        actionError: msg,
        toastNotifications: [
          ...state.toastNotifications,
          {
            id: `toast-${Date.now()}`,
            type: 'critical',
            title: 'ACTION EXECUTION FAILED',
            message: msg,
          },
        ],
      }))
      return { success: false, reason: msg }
    }
  },

  // ── Other Store Actions ─────────────────────────────────────────────────── //

  selectEquipment: (id) => {
    const item = id ? get().equipment[id] : null
    set({
      selectedEquipmentId: id,
      selectedBayId: item ? item.bayId : get().selectedBayId,
    })
  },

  selectBay: (bayId) => {
    set({ selectedBayId: bayId })
  },

  selectAlert: (alertId) => {
    const alert = get().alerts.find((a) => a.id === alertId)
    set({
      selectedAlertId: alertId,
      selectedEquipmentId: alert ? alert.equipmentId : get().selectedEquipmentId,
      selectedBayId: alert ? alert.bayId : get().selectedBayId,
    })
  },

  openCopilot: (context) => {
    set({ isCopilotOpen: true })
    if (context?.tag && context?.prompt) {
      get().sendUserMessage(context.prompt)
    }
  },

  closeCopilot: () => set({ isCopilotOpen: false }),
  toggleCopilot: () => set((state) => ({ isCopilotOpen: !state.isCopilotOpen })),

  setVoiceState: (voiceState) => set({ voiceState }),

  toggleAutoSpeakVoice: () => set((s) => ({ autoSpeakVoice: !s.autoSpeakVoice })),

  speakCopilotMessage: async (text: string) => {
    set({ voiceState: 'speaking' })
    await voiceService.playSpeech(text, {
      onStart: () => set({ voiceState: 'speaking' }),
      onEnd: () => set({ voiceState: 'idle' }),
      onError: () => set({ voiceState: 'idle' }),
      onLatency: (ms) => set({ voiceLatencyMs: ms }),
    })
  },

  bargeInVoice: () => {
    voiceService.cancelSpeech()
    set({ voiceState: 'idle' })
  },

  updateAlertStatus: async (alertId, status) => {
    if (status === 'ACKNOWLEDGED') {
      try {
        await acknowledgeAlarm(alertId)
        await get().fetchLivePlantData()
      } catch (err) {
        console.warn('Failed to acknowledge alarm on backend:', err)
      }
    }
  },

  sendUserMessage: async (text: string, fromVoice = false) => {
    const userMsg: CopilotMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    }
    set((state) => ({
      copilotMessages: [...state.copilotMessages, userMsg],
      copilotStreaming: true,
      voiceState: fromVoice ? 'processing' : state.voiceState,
    }))

    try {
      const selectedId = get().selectedEquipmentId
      const canonicalAssetId = selectedId ? toCanonicalAssetId(selectedId) : 'F-201A'
      const response = await queryCopilot({
        prompt: text,
        asset_id: canonicalAssetId,
      })

      const novaReply: CopilotMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: 'nova',
        text: response.response,
        timestamp: new Date().toLocaleTimeString(),
        recommendation:
          response.recommended_actions && response.recommended_actions.length > 0
            ? {
                actionTitle: response.recommended_actions[0],
                targetEquipmentTag: toDisplayTag(canonicalAssetId),
                confidencePercent: 95,
                evidenceCount: response.evidence_package?.evidence_items?.length || 3,
                correlatedSignalsCount:
                  Object.keys(response.evidence_package?.plant_state?.telemetry || {}).length || 4,
                approved: false,
              }
            : undefined,
      }

      set((state) => ({
        copilotMessages: [...state.copilotMessages, novaReply],
        copilotStreaming: false,
      }))

      // Speak response aloud via Rime TTS streaming
      if (get().autoSpeakVoice || fromVoice) {
        const speechText = response.spoken_text || response.response
        get().speakCopilotMessage(speechText)
      } else {
        set({ voiceState: 'idle' })
      }
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      const errorReply: CopilotMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: 'nova',
        text: `Backend inquiry unavailable: ${errorMsg}`,
        timestamp: new Date().toLocaleTimeString(),
      }
      set((state) => ({
        copilotMessages: [...state.copilotMessages, errorReply],
        copilotStreaming: false,
      }))
      if (get().autoSpeakVoice || fromVoice) {
        get().speakCopilotMessage(errorReply.text)
      } else {
        set({ voiceState: 'idle' })
      }
    }
  },

  approveRecommendation: async () => {
    // Replaces mock mutation with real backend decision workflow
    await get().approveMitigationAction()
  },

  triggerManualMitigation: async () => {
    await get().approveMitigationAction()
  },

  handleWsMessage: (msg: WsEnvelope) => {
    switch (msg.type) {
      case 'connection.status':
        set((state) => ({
          systemHealth: { ...state.systemHealth, telemetryWs: 'connected' },
        }))
        break
      case 'telemetry.updated':
      case 'raw.telemetry': {
        const payload = msg.payload as Record<string, unknown>
        const assetId = (msg.asset_id || payload.asset_id) as string | undefined
        if (assetId) {
          const canonicalId = toCanonicalAssetId(assetId)
          const updatedEquipment = { ...get().equipment }
          let found = false
          Object.keys(updatedEquipment).forEach((eqKey) => {
            const item = { ...updatedEquipment[eqKey] }
            if (toCanonicalAssetId(item.tag || item.id) === canonicalId) {
              const param = ((payload.parameter || payload.tag || '') as string).toLowerCase()
              const val = typeof payload.value === 'number' ? payload.value : undefined
              if (val !== undefined) {
                found = true
                item.telemetry = {
                  ...item.telemetry,
                  ...(param.includes('temp') || param.includes('ti-') ? { temperature: val } : {}),
                  ...(param.includes('vib') || param.includes('vi-') ? { vibration: val } : {}),
                  ...(param.includes('pres') || param.includes('pi-') ? { pressure: val } : {}),
                  ...(param.includes('flow') || param.includes('fi-') ? { flow: val } : {}),
                  lastUpdated: new Date().toISOString(),
                }
                updatedEquipment[eqKey] = item
              }
            }
          })
          if (found) {
            set({ equipment: updatedEquipment })
          }
        }
        break
      }
      case 'risk.updated': {
        const payload = msg.payload as unknown as Record<string, unknown>
        if (payload?.assessment) {
          set({ overallRiskData: payload.assessment as unknown as IndustrialRiskAssessment })
        } else {
          get().fetchLivePlantData()
        }
        break
      }
      case 'alarm.created':
      case 'alarm.updated':
      case 'episode.created':
      case 'episode.updated':
      case 'plant_state.updated': {
        get().fetchLivePlantData()
        break
      }
      case 'runtime.case.updated': {
        const payload = msg.payload as Record<string, unknown>
        const caseId = (payload.case_id || (msg as any).case_id) as string | undefined
        if (caseId) {
          const currentCases = get().runtimeCases
          const idx = currentCases.findIndex((c) => c.case_id === caseId)
          if (idx >= 0 && payload.runtime_state) {
            const updated = [...currentCases]
            updated[idx] = { ...updated[idx], ...(payload as unknown as Partial<RuntimeCase>) }
            set({ runtimeCases: updated })
          } else {
            get().fetchLivePlantData()
          }
        } else {
          get().fetchLivePlantData()
        }
        break
      }
      default:
        break
    }
  },

  dismissToast: (id) => {
    set((state) => ({
      toastNotifications: state.toastNotifications.filter((t) => t.id !== id),
    }))
  },
}))

// Selector hooks for clean consumption
export const useEquipment = (id: string | null) =>
  useRealtimeStore((s) => (id ? s.equipment[id] : null))

export const useEquipmentList = () =>
  useRealtimeStore((s) => Object.values(s.equipment))

export const useAlerts = () => useRealtimeStore((s) => s.alerts)

export const useRiskOverview = () =>
  useRealtimeStore((s) => {
    const list = Object.values(s.equipment)
    const overallRisk = s.overallRiskData
    const overallScore = overallRisk
      ? Math.round(overallRisk.risk_score * 100)
      : Math.round(list.reduce((sum, item) => sum + item.riskScore, 0) / (list.length || 1))
    const atRiskCount = list.filter((e) => getRiskState(e) === 'HIGH' || getRiskState(e) === 'CRITICAL').length
    const anomalyCount = list.filter((e) => e.anomalyDetected).length

    const byArea: Record<string, number> = {}
    list.forEach((item) => {
      const bayKey = item.bayId || 'unknown'
      byArea[bayKey] = Math.max(byArea[bayKey] ?? 0, item.riskScore)
    })

    return {
      overallScore,
      atRiskCount,
      anomalyCount,
      totalCount: list.length,
      byArea,
      plantStatus: s.plantStatus,
      safetyStatus: s.safetyStatus,
    }
  })

export const useSystemHealth = () => useRealtimeStore((s) => s.systemHealth)
