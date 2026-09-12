import { EquipmentItem, RiskTier } from '../types'

/**
 * Computes derived risk state per equipment item from riskScore and anomalyDetected.
 *
 * Rules:
 * - riskScore < 30        → LOW
 * - 30 <= riskScore < 60  → MEDIUM
 * - 60 <= riskScore < 80  → HIGH
 * - riskScore >= 80       → CRITICAL
 * - anomalyDetected === true → escalate at least one level above what score alone gives:
 *     LOW + anomaly      → MEDIUM minimum
 *     MEDIUM + anomaly   → CRITICAL
 *     HIGH + anomaly     → CRITICAL
 *     CRITICAL + anomaly → CRITICAL
 */
export function getRiskState(equipment: Pick<EquipmentItem, 'riskScore' | 'anomalyDetected'>): RiskTier {
  const { riskScore, anomalyDetected } = equipment

  let baseTier: RiskTier = 'LOW'
  if (riskScore >= 80) {
    baseTier = 'CRITICAL'
  } else if (riskScore >= 60) {
    baseTier = 'HIGH'
  } else if (riskScore >= 30) {
    baseTier = 'MEDIUM'
  } else {
    baseTier = 'LOW'
  }

  if (!anomalyDetected) {
    return baseTier
  }

  // Escalation rule
  switch (baseTier) {
    case 'LOW':
      return 'MEDIUM'
    case 'MEDIUM':
      return 'CRITICAL'
    case 'HIGH':
    case 'CRITICAL':
    default:
      return 'CRITICAL'
  }
}

/**
 * Clean Light White + Orange Theme Palette:
 * - Normal/Low: green (#16A34A)
 * - Medium: amber/yellow (#CA8A04)
 * - High: deeper orange-red (#C2410C) — distinctly redder/deeper than the brand orange #F97316
 * - Critical: red (#DC2626)
 * - Offline: gray (#64748B)
 */
export const RISK_COLORS: Record<RiskTier, {
  hex: string
  threeHex: number
  bgClass: string
  textClass: string
  borderClass: string
  badgeClass: string
  glowIntensity: number
}> = {
  LOW: {
    hex: '#16A34A',
    threeHex: 0x16a34a,
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-700',
    borderClass: 'border-emerald-200',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-300',
    glowIntensity: 0.1,
  },
  MEDIUM: {
    hex: '#CA8A04',
    threeHex: 0xca8a04,
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-200',
    badgeClass: 'bg-amber-50 text-amber-800 border-amber-300',
    glowIntensity: 0.3,
  },
  HIGH: {
    hex: '#C2410C', // Deeper orange-red, semantically distinct from brand #F97316
    threeHex: 0xc2410c,
    bgClass: 'bg-orange-50',
    textClass: 'text-orange-800',
    borderClass: 'border-orange-300',
    badgeClass: 'bg-orange-50 text-orange-900 border-orange-400 font-semibold',
    glowIntensity: 0.8,
  },
  CRITICAL: {
    hex: '#DC2626', // Red
    threeHex: 0xdc2626,
    bgClass: 'bg-red-50',
    textClass: 'text-red-700',
    borderClass: 'border-red-300',
    badgeClass: 'bg-red-50 text-red-700 border-red-400 font-bold',
    glowIntensity: 1.5,
  },
}

export const STATUS_COLORS: Record<EquipmentItem['status'], {
  hex: string
  threeHex: number
  label: string
  badgeClass: string
}> = {
  running: {
    hex: '#16A34A',
    threeHex: 0x16a34a,
    label: 'Running',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  idle: {
    hex: '#64748B',
    threeHex: 0x64748b,
    label: 'Idle',
    badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
  },
  alarm: {
    hex: '#DC2626',
    threeHex: 0xdc2626,
    label: 'Alarm',
    badgeClass: 'bg-red-50 text-red-700 border-red-300 font-bold',
  },
  offline: {
    hex: '#94A3B8',
    threeHex: 0x94a3b8,
    label: 'Offline',
    badgeClass: 'bg-slate-50 text-slate-500 border-slate-200',
  },
}

export const FLUID_COLORS: Record<string, { hex: string; threeHex: number }> = {
  crude: { hex: '#64748b', threeHex: 0x475569 },
  gas: { hex: '#0284c7', threeHex: 0x0284c7 },
  steam: { hex: '#94a3b8', threeHex: 0x94a3b8 },
  coolingWater: { hex: '#2563eb', threeHex: 0x2563eb },
  ethylene: { hex: '#059669', threeHex: 0x059669 },
  slurry: { hex: '#d97706', threeHex: 0xd97706 },
  chemical: { hex: '#7c3aed', threeHex: 0x7c3aed },
}
