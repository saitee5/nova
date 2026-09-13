import React from 'react'
import { RiskTier } from '../plant-twin/types'
import { RISK_COLORS, STATUS_COLORS } from '../plant-twin/utils/riskUtils'
import { AlertSeverity, AlertStatus } from '../../stores/useRealtimeStore'

export const RiskBadge: React.FC<{ tier: RiskTier; score?: number; className?: string }> = ({
  tier,
  score,
  className = '',
}) => {
  const meta = RISK_COLORS[tier]
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono border ${meta.badgeClass} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: meta.hex }} />
      <span>{tier}</span>
      {score !== undefined && <span className="opacity-75">({score})</span>}
    </span>
  )
}

export const StatusBadge: React.FC<{
  status: 'running' | 'idle' | 'alarm' | 'offline'
  className?: string
}> = ({ status, className = '' }) => {
  const meta = STATUS_COLORS[status] || STATUS_COLORS.offline
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-titillum border ${meta.badgeClass} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: meta.hex }} />
      <span>{meta.label}</span>
    </span>
  )
}

export const AlertSeverityBadge: React.FC<{ severity: AlertSeverity; className?: string }> = ({
  severity,
  className = '',
}) => {
  const styles: Record<AlertSeverity, string> = {
    critical: 'bg-red-50 text-red-700 border-red-300 font-bold',
    high: 'bg-orange-50 text-orange-900 border-orange-400 font-semibold',
    medium: 'bg-amber-50 text-amber-800 border-amber-300',
    low: 'bg-emerald-50 text-emerald-700 border-emerald-300',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono uppercase tracking-wider border ${styles[severity] || styles.low
        } ${className}`}
    >
      {severity}
    </span>
  )
}

export const AlertStatusBadge: React.FC<{ status: AlertStatus; className?: string }> = ({
  status,
  className = '',
}) => {
  const styles: Record<AlertStatus, string> = {
    NEW: 'bg-red-100 text-red-800 border-red-300 animate-pulse',
    ACKNOWLEDGED: 'bg-amber-100 text-amber-800 border-amber-300',
    INVESTIGATING: 'bg-sky-100 text-sky-800 border-sky-300',
    MITIGATED: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    RESOLVED: 'bg-slate-100 text-slate-700 border-slate-300',
    DISMISSED: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border ${styles[status] || styles.NEW
        } ${className}`}
    >
      {status}
    </span>
  )
}
