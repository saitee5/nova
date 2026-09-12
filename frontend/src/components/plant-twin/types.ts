export type EquipmentType =
  | 'tank'
  | 'furnace'
  | 'burner'
  | 'preheater'
  | 'transferLineExchanger'
  | 'quenchTower'
  | 'compressor'
  | 'column'
  | 'knockoutDrum'
  | 'utilityHeader'
  | 'flareStack'
  | 'esdValve'
  | 'gasDetector'
  | 'heatExchanger'
  | 'pump'
  | 'valve'
  | 'coil'

export type EquipmentStatus = 'running' | 'idle' | 'alarm' | 'offline'

export type RiskTier = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface TelemetryData {
  temperature?: number
  pressure?: number
  flow?: number
  vibration?: number
  gasConcentration?: number
  // Furnace specific telemetry
  cot?: number // Coil Outlet Temperature °C — normal 840-860
  tmt?: number // Tube Metal Temperature °C (surrogate) — alarm 1040, trip 1080
  furnacePressure?: number
  stackTemperature?: number
  fuelGasFlow?: number
  combustionAirFlow?: number
  draft?: number
  burnerFlameStatus?: Record<string, 'on' | 'off' | 'fault'>
  lastUpdated: string
}

export interface TrendPoint {
  timestamp: string
  value: number
}

export interface AlertItem {
  id: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  timestamp: string
}

export interface HistoricalIncident {
  id: string
  date: string
  title?: string
  summary: string
  damageType?: string
  severity?: 'critical' | 'high' | 'medium' | 'low'
  downtimeHours?: number
  costEstimate?: string
  actionTaken?: string
  preventativeMeasures?: string
}

export interface OperatingEnvelope {
  normalCOT: [number, number]
  highAlarmCOT: number
  highHighTripCOT: number
  tmtAlarm: number
  tmtTrip: number
}

export interface EquipmentItem {
  id: string
  tag: string
  name: string
  type: EquipmentType
  bayId: string
  position: [number, number, number]
  rotation?: [number, number, number]
  scale?: [number, number, number]
  status: EquipmentStatus
  riskScore: number // 0 - 100
  anomalyDetected: boolean
  anomalyDetails?: string
  telemetry: TelemetryData
  trend: TrendPoint[]
  relatedEquipmentIds: {
    upstream: string[]
    downstream: string[]
  }
  activeAlerts: AlertItem[]
  historicalIncidents: HistoricalIncident[]
  specs?: Record<string, string>
  mlModels?: string[]
  operatingEnvelope?: OperatingEnvelope
}

export interface BayDefinition {
  id: string
  code: string // e.g. "Bay 1"
  name: string // e.g. "Feedstock Receiving & Storage"
  subtitle?: string
  colorTheme: string // hex color
  accentColor: string
  position: [number, number, number] // center [x, y, z]
  size: [number, number] // [width, depth]
  cameraFocusPoint: {
    position: [number, number, number]
    target: [number, number, number]
  }
}

export interface PipeRouteDefinition {
  id: string
  name: string
  fromEquipmentId: string
  toEquipmentId: string
  waypoints: [number, number, number][]
  fluidType: 'crude' | 'gas' | 'steam' | 'coolingWater' | 'ethylene' | 'slurry' | 'chemical'
  nominalDiameter?: number
  flowRate?: number // e.g. m3/h or kg/s
  color?: string
}

export type CameraMode = 'overview' | 'focused' | 'bay' | 'equipment'
