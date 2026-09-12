import { create } from 'zustand'
import { BayDefinition, CameraMode, EquipmentItem, PipeRouteDefinition, RiskTier } from '../types'
import { PLANT_BAYS } from '../data/plantLayout'
import { EQUIPMENT_ITEMS } from '../data/equipmentLayout'
import { PIPE_ROUTES } from '../data/pipeRoutes'

interface TwinState {
  // Data
  bays: BayDefinition[]
  equipmentList: EquipmentItem[]
  pipeRoutes: PipeRouteDefinition[]

  // Selection & Navigation
  selectedBayId: string | null
  selectedEquipmentId: string | null
  cameraMode: CameraMode
  isDrawerOpen: boolean

  // Filters & Search
  searchQuery: string
  filterRisk: RiskTier | 'ALL'

  // Pre-filled prompt to pass to NOVA
  novaQueryPayload: {
    equipmentTag: string
    equipmentName: string
    prompt: string
  } | null

  // Actions
  selectBay: (bayId: string | null) => void
  selectEquipment: (equipmentId: string | null) => void
  inspectBay: (bayId: string, equipmentId?: string | null) => void
  closeDrawer: () => void
  resetToOverview: () => void
  setSearchQuery: (query: string) => void
  setFilterRisk: (tier: RiskTier | 'ALL') => void
  askNova: (equipment: EquipmentItem) => void
  clearNovaPayload: () => void
}

export const useTwinStore = create<TwinState>((set, get) => ({
  bays: PLANT_BAYS,
  equipmentList: EQUIPMENT_ITEMS,
  pipeRoutes: PIPE_ROUTES,

  selectedBayId: null,
  selectedEquipmentId: null,
  cameraMode: 'overview',
  isDrawerOpen: false,

  searchQuery: '',
  filterRisk: 'ALL',
  novaQueryPayload: null,

  selectBay: (bayId) => {
    if (!bayId) {
      set({
        selectedBayId: null,
        cameraMode: 'overview',
      })
      return
    }

    set({
      selectedBayId: bayId,
      cameraMode: 'bay',
    })
  },

  inspectBay: (bayId, equipmentId) => {
    set({
      selectedBayId: bayId,
      selectedEquipmentId: equipmentId || null,
      cameraMode: 'bay',
      isDrawerOpen: !!equipmentId,
    })
  },

  selectEquipment: (equipmentId) => {
    if (!equipmentId) {
      set({
        selectedEquipmentId: null,
        isDrawerOpen: false,
      })
      return
    }

    const item = get().equipmentList.find((e) => e.id === equipmentId)
    set({
      selectedEquipmentId: equipmentId,
      selectedBayId: item ? item.bayId : get().selectedBayId,
      cameraMode: 'equipment',
      isDrawerOpen: true,
    })
  },

  closeDrawer: () => {
    set({
      isDrawerOpen: false,
      selectedEquipmentId: null,
    })
  },

  resetToOverview: () => {
    set({
      selectedBayId: null,
      selectedEquipmentId: null,
      cameraMode: 'overview',
      isDrawerOpen: false,
    })
  },

  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setFilterRisk: (filterRisk) => set({ filterRisk }),

  askNova: (equipment) => {
    const prompt = `Inspect telemetry anomaly on ${equipment.name} (${equipment.tag}). Risk score is ${equipment.riskScore}/100. Current status is ${equipment.status}. Active anomalies: ${equipment.anomalyDetails || 'None'}. Suggest immediate mitigations, check related upstream/downstream assets, and generate standard operating procedure.`
    set({
      novaQueryPayload: {
        equipmentTag: equipment.tag,
        equipmentName: equipment.name,
        prompt,
      },
    })
  },

  clearNovaPayload: () => set({ novaQueryPayload: null }),
}))
