import React from 'react'

interface MetricCardProps {
  label: string
  value: string | number
  unit?: string
  trendDelta?: string
  trendDirection?: 'up' | 'down' | 'neutral'
  status?: 'normal' | 'warning' | 'critical'
  icon?: React.ReactNode
  subtext?: string
  className?: string
  onClick?: () => void
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  trendDelta,
  trendDirection,
  status = 'normal',
  icon,
  subtext,
  className = '',
  onClick,
}) => {
  const statusBorder = {
    normal: 'border-slate-200 hover:border-slate-300',
    warning: 'border-amber-300 bg-amber-50/20',
    critical: 'border-red-300 bg-red-50/20',
  }[status]

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-lg border p-4 shadow-sm transition-all duration-200 ${statusBorder} ${
        onClick ? 'cursor-pointer hover:shadow-md' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between text-slate-500 text-xs font-mono mb-2">
        <span className="uppercase tracking-wider font-medium">{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold font-mono text-slate-900 tracking-tight">
          {value}
        </span>
        {unit && <span className="text-xs font-mono text-slate-500">{unit}</span>}
      </div>

      <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100 text-xs font-mono">
        {trendDelta && (
          <span
            className={`flex items-center gap-1 font-semibold ${
              trendDirection === 'up'
                ? status === 'critical'
                  ? 'text-red-600'
                  : 'text-emerald-600'
                : trendDirection === 'down'
                ? 'text-slate-600'
                : 'text-slate-500'
            }`}
          >
            {trendDirection === 'up' && '▲'}
            {trendDirection === 'down' && '▼'}
            {trendDelta}
          </span>
        )}
        {subtext && <span className="text-slate-400 text-[11px] ml-auto">{subtext}</span>}
      </div>
    </div>
  )
}
