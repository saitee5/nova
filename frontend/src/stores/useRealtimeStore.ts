import { create } from 'zustand'
import { EquipmentItem } from '../components/plant-twin/types'
import { EQUIPMENT_ITEMS } from '../components/plant-twin/data/equipmentLayout'
import { getRiskState } from '../components/plant-twin/utils/riskUtils'

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

  // Actions
  selectEquipment: (id: string | null) => void
  selectBay: (bayId: string | null) => void
  selectAlert: (alertId: string | null) => void
  openCopilot: (initialContext?: { tag?: string; prompt?: string }) => void
  closeCopilot: () => void
  toggleCopilot: () => void
  setVoiceState: (state: VoiceState) => void
  updateAlertStatus: (alertId: string, status: AlertStatus) => void
  sendUserMessage: (text: string) => void
  approveRecommendation: (actionId?: string) => void
  dismissToast: (id: string) => void
  triggerManualMitigation: (equipmentId: string) => void
}

// Initial Alert Data
const INITIAL_ALERTS: RealtimeAlert[] = [
  {
    id: 'ALT-8921',
    title: 'Radiant Coil Skin Temperature Exceeded Trip Limit',
    equipmentId: 'F-301A',
    equipmentTag: 'F-301A',
    equipmentName: 'Pyrolysis Cracking Furnace A',
    bayId: 'bay-3',
    severity: 'critical',
    message: 'Tube skin thermocouple TC-301-4 reached 1,064.2°C (> 1,045°C safety interlock).',
    aiExplanation:
      'NOVA correlated local burner air-register distortion with heavy coking inside pass 4, creating an localized flame impingement zone.',
    status: 'NEW',
    timestamp: '11:08:19',
    riskScore: 88,
    signalDeltas: [
      { signal: 'Skin Temperature', current: 1064.2, baseline: 990.0, unit: '°C', deltaPercent: 7.5 },
      { signal: 'Pass 4 DP', current: 3.8, baseline: 2.8, unit: 'bar', deltaPercent: 35.7 },
      { signal: 'Burner Acoustic RMS', current: 5.6, baseline: 1.8, unit: 'mm/s', deltaPercent: 211.0 },
    ],
    historicalMatchCount: 3,
    suggestedAction:
      'Reduce fuel gas rate by 8.5%, bias airflow +3.2%, and divert 45 t/h crude feed to Furnace B.',
  },
  {
    id: 'ALT-8920',
    title: 'Stage 3 Radial Vibration Amplitude Surge',
    equipmentId: 'K-301',
    equipmentTag: 'K-301',
    equipmentName: 'Cracked Gas Compressor Train',
    bayId: 'bay-3',
    severity: 'critical',
    message: 'Drive-end radial shaft displacement surged to 6.8 mm/s RMS (trip warning threshold: 6.0 mm/s).',
    aiExplanation:
      'High quench effluent temperature entering compressor inlet caused liquid droplet carryover onto stage 3 impeller.',
    status: 'INVESTIGATING',
    timestamp: '11:09:02',
    riskScore: 78,
    signalDeltas: [
      { signal: 'Radial Vibration', current: 6.8, baseline: 2.4, unit: 'mm/s', deltaPercent: 183.3 },
      { signal: 'Bearing DE Temp', current: 88.4, baseline: 64.0, unit: '°C', deltaPercent: 38.1 },
    ],
    historicalMatchCount: 2,
    suggestedAction: 'Increase suction drum demister wash; verify dry gas seal DP before trip limit.',
  },
  {
    id: 'ALT-8918',
    title: 'Transfer Line Exchanger Quench Delta Elevated',
    equipmentId: 'TLE-301',
    equipmentTag: 'TLE-301',
    equipmentName: 'Transfer Line Exchanger',
    bayId: 'bay-3',
    severity: 'high',
    message: 'Outlet quench temp reached 420.5°C; HP steam generation efficiency decreased by 14%.',
    aiExplanation:
      'Shell-side boiler feedwater flow starvation suspected due to rapid thermal expansion in upstream furnace outlet header.',
    status: 'ACKNOWLEDGED',
    timestamp: '11:04:12',
    riskScore: 65,
    signalDeltas: [
      { signal: 'Outlet Temp', current: 420.5, baseline: 380.0, unit: '°C', deltaPercent: 10.6 },
      { signal: 'HP Steam Output', current: 350.0, baseline: 410.0, unit: 't/h', deltaPercent: -14.6 },
    ],
    historicalMatchCount: 4,
    suggestedAction: 'Increase boiler feed pump discharge pressure by +5 bar to overcome resistance.',
  },
  {
    id: 'ALT-8915',
    title: 'Pre-Flash Column Bottom Tray Differential Pressure',
    equipmentId: 'C-201',
    equipmentTag: 'C-201',
    equipmentName: 'Pre-Flash Distillation Column',
    bayId: 'bay-2',
    severity: 'medium',
    message: 'Tray 8-12 DP elevated +18% above nominal operating line.',
    aiExplanation: 'Moderate froth buildup detected in desalted feed tray area.',
    status: 'ACKNOWLEDGED',
    timestamp: '11:05:32',
    riskScore: 54,
    signalDeltas: [
      { signal: 'Tray 8-12 DP', current: 0.48, baseline: 0.40, unit: 'bar', deltaPercent: 20.0 },
    ],
    historicalMatchCount: 1,
    suggestedAction: 'Adjust reflux ratio by -2% to stabilize vapor velocity.',
  },
]

// Initial Compound Anomaly Data
const INITIAL_COMPOUND_ANOMALIES: CompoundAnomaly[] = [
  {
    id: 'CMP-01',
    title: 'Pyrolysis Furnace Thermal Overload & Compressor Liquid Carryover',
    equipmentIds: ['F-301A', 'TLE-301', 'C-302', 'K-301'],
    primaryEquipmentTag: 'F-301A',
    bayId: 'bay-3',
    severity: 'critical',
    correlationScore: 0.94,
    signals: [
      { name: 'F-301A Tube Skin Temp', value: '1,064.2°C', trend: 'rising' },
      { name: 'TLE-301 Effluent Temp', value: '420.5°C', trend: 'rising' },
      { name: 'C-302 Quench Delta', value: '114.2°C', trend: 'rising' },
      { name: 'K-301 Radial Vibration', value: '6.8 mm/s', trend: 'rising' },
    ],
    novaExplanation:
      'A flame hotspot on Furnace F-301A caused rapid gas expansion that degraded TLE-301 quench efficiency (+40°C), elevating quench column overhead temperature and allowing heavy hydrocarbon aerosol droplets to hit Cracked Gas Compressor K-301 stage 3 impellers.',
    recommendedMitigation:
      'Execute coordinated mitigation: throttle F-301A fuel gas -8.5%, shift 45 t/h feed to F-301B, and cycle suction drum mist eliminator bypass.',
    confidence: 0.96,
  },
]

// Initial Equipment Dictionary
const INITIAL_EQUIPMENT_RECORD = EQUIPMENT_ITEMS.reduce<Record<string, EquipmentItem>>(
  (acc, item) => {
    acc[item.id] = item
    return acc
  },
  {}
)

export const useRealtimeStore = create<RealtimeStoreState>((set, get) => ({
  plantName: 'NOVA Petrochemical Complex — Bay 1–6',
  plantStatus: 'Degraded',
  throughputRate: 1250,
  powerConsumptionMw: 42,
  co2EmissionsRate: 12.4,
  safetyStatus: 'Alert',

  equipment: INITIAL_EQUIPMENT_RECORD,
  alerts: INITIAL_ALERTS,
  compoundAnomalies: INITIAL_COMPOUND_ANOMALIES,

  selectedEquipmentId: null,
  selectedBayId: null,
  selectedAlertId: null,

  systemHealth: {
    telemetryWs: 'connected',
    simulator: 'running',
    aiPipelineLatencyMs: 142,
    qdrantStatus: 'healthy',
    voiceEngineStatus: 'ready',
    lastSyncTimestamp: new Date().toISOString(),
    signalsPerSecond: 1284,
  },

  isCopilotOpen: false,
  voiceState: 'idle',
  copilotMessages: [
    {
      id: 'msg-init',
      sender: 'nova',
      text: 'Good afternoon, Operator. I am actively monitoring Bay 1 through Bay 6. A CRITICAL compound anomaly is active on Cracking Furnace F-301A and Compressor K-301 in Bay 3. How would you like to proceed?',
      timestamp: '11:10:00',
    },
  ],
  copilotStreaming: false,
  activeVoiceTranscript: '',
  toastNotifications: [
    {
      id: 'toast-1',
      type: 'critical',
      title: 'CRITICAL ALERT — Bay 3',
      message: 'F-301A coil skin temp exceeded 1,060°C. Click to inspect.',
    },
  ],

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
      const userMsg: CopilotMessage = {
        id: `msg-${Date.now()}`,
        sender: 'user',
        text: context.prompt,
        timestamp: new Date().toLocaleTimeString(),
      }

      set((state) => ({
        copilotMessages: [...state.copilotMessages, userMsg],
        copilotStreaming: true,
      }))

      // Simulated NOVA intelligence response
      setTimeout(() => {
        const novaReply: CopilotMessage = {
          id: `msg-${Date.now() + 1}`,
          sender: 'nova',
          text: `Analyzing ${context.tag}. Root cause: localized flame impingement on pass 4 due to burner damper drift (+6%), with acoustic excitation at 5.6 mm/s. Based on 2 similar historical incidents in Qdrant (top similarity 0.94 on INC-2024-08-14), I recommend executing the standard thermal de-escalation procedure.`,
          timestamp: new Date().toLocaleTimeString(),
          recommendation: {
            actionTitle: 'Throttle F-301A Fuel Gas by -8.5% & Divert 45 t/h feed to F-301B',
            targetEquipmentTag: context.tag || 'F-301A',
            confidencePercent: 96,
            evidenceCount: 3,
            correlatedSignalsCount: 4,
            approved: false,
          },
        }
        set((state) => ({
          copilotMessages: [...state.copilotMessages, novaReply],
          copilotStreaming: false,
        }))
      }, 700)
    }
  },

  closeCopilot: () => set({ isCopilotOpen: false }),
  toggleCopilot: () => set((state) => ({ isCopilotOpen: !state.isCopilotOpen })),

  setVoiceState: (voiceState) => set({ voiceState }),

  updateAlertStatus: (alertId, status) => {
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === alertId ? { ...a, status } : a)),
    }))
  },

  sendUserMessage: (text) => {
    const userMsg: CopilotMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    }
    set((state) => ({
      copilotMessages: [...state.copilotMessages, userMsg],
      copilotStreaming: true,
    }))

    setTimeout(() => {
      const novaResponse: CopilotMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: 'nova',
        text: `Understood. Telemetry across Bay 1 through Bay 6 remains synchronized. You can approve the active mitigation below to reset coil skin temperature and re-establish safety margin.`,
        timestamp: new Date().toLocaleTimeString(),
        recommendation: {
          actionTitle: 'Apply Active Operating Procedure SOP-PYR-301',
          targetEquipmentTag: 'F-301A',
          confidencePercent: 94,
          evidenceCount: 3,
          correlatedSignalsCount: 3,
          approved: false,
        },
      }
      set((state) => ({
        copilotMessages: [...state.copilotMessages, novaResponse],
        copilotStreaming: false,
      }))
    }, 600)
  },

  approveRecommendation: () => {
    // ── CORE OPERATOR STORY: RISK MITIGATION EFFECT ── //
    // Mitigate equipment F-301A and K-301
    set((state) => {
      const updatedEquipment = { ...state.equipment }

      if (updatedEquipment['F-301A']) {
        const item = { ...updatedEquipment['F-301A'] }
        item.riskScore = 24 // Drops from 88 to 24 (LOW)
        item.status = 'running'
        item.anomalyDetected = false
        item.telemetry = {
          ...item.telemetry,
          temperature: 982.0, // Normalizes from 1064°C
          vibration: 2.1,
          gasConcentration: 12.0,
        }
        item.activeAlerts = []
        updatedEquipment['F-301A'] = item
      }

      if (updatedEquipment['C-301']) {
        const item = { ...updatedEquipment['C-301'] }
        item.riskScore = 22
        item.status = 'running'
        item.anomalyDetected = false
        item.telemetry = { ...item.telemetry, temperature: 980.0 }
        updatedEquipment['C-301'] = item
      }

      if (updatedEquipment['K-301']) {
        const item = { ...updatedEquipment['K-301'] }
        item.riskScore = 28 // Drops from 78 to 28
        item.status = 'running'
        item.anomalyDetected = false
        item.telemetry = { ...item.telemetry, vibration: 2.4, temperature: 68.0 }
        updatedEquipment['K-301'] = item
      }

      const updatedAlerts = state.alerts.map((a) =>
        a.equipmentId === 'F-301A' || a.equipmentId === 'K-301'
          ? { ...a, status: 'RESOLVED' as AlertStatus }
          : a
      )

      const updatedMessages = state.copilotMessages.map((m) => {
        if (m.recommendation) {
          return {
            ...m,
            recommendation: { ...m.recommendation, approved: true },
          }
        }
        return m
      })

      const confirmationMsg: CopilotMessage = {
        id: `msg-${Date.now()}`,
        sender: 'nova',
        text: 'Action Approved & Executed: Fuel gas rate reduced by 8.5%, 45 t/h shifted to Furnace B. Telemetry feedback shows F-301A coil skin temp dropped to 982.0°C (Normal). Bay 3 safety interlocks restored.',
        timestamp: new Date().toLocaleTimeString(),
      }

      return {
        equipment: updatedEquipment,
        alerts: updatedAlerts,
        plantStatus: 'Running',
        safetyStatus: 'Normal',
        copilotMessages: [...updatedMessages, confirmationMsg],
      }
    })
  },

  triggerManualMitigation: (equipmentId) => {
    set((state) => {
      const updatedEquipment = { ...state.equipment }
      if (updatedEquipment[equipmentId]) {
        const item = { ...updatedEquipment[equipmentId] }
        item.riskScore = 22
        item.status = 'running'
        item.anomalyDetected = false
        updatedEquipment[equipmentId] = item
      }
      return { equipment: updatedEquipment }
    })
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
    const overallScore = Math.round(
      list.reduce((sum, item) => sum + item.riskScore, 0) / (list.length || 1)
    )
    const atRiskCount = list.filter((e) => getRiskState(e) === 'HIGH' || getRiskState(e) === 'CRITICAL').length
    const anomalyCount = list.filter((e) => e.anomalyDetected).length

    // Risk by bay
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
