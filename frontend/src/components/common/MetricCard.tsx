import React from 'react'

export interface MetricCardProps {
  label: string
  value: string | number
  unit?: string
  trendDelta?: string
  trendDirection?: 'up' | 'down' | 'neutral'
  status?: 'normal' | 'warning' | 'critical'
  variant?: 'navy' | 'teal' | 'gray' | 'gold' | 'default'
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
  variant = 'default',
  icon,
  subtext,
  className = '',
  onClick,
}) => {
  // If a color-blocked variant is specified
  if (variant !== 'default') {
    const variantStyles = {
      navy: {
        container: 'bg-[#1E293B] text-white border-[#273549]',
        label: 'text-slate-300',
        value: 'text-white',
        subtext: 'text-slate-300/80',
        trendDelta: 'text-slate-200',
      },
      teal: {
        container: 'bg-[#4A7C7C] text-white border-[#558a8a]',
        label: 'text-teal-100',
        value: 'text-white',
        subtext: 'text-teal-100/80',
        trendDelta: 'text-teal-50',
      },
      gray: {
        container: 'bg-[#94A3B8] text-slate-900 border-[#8393a8]',
        label: 'text-slate-800',
        value: 'text-slate-900',
        subtext: 'text-slate-800/80',
        trendDelta: 'text-slate-900',
      },
      gold: {
        container: 'bg-[#C9A227] text-slate-950 border-[#b9931f]',
        label: 'text-amber-950 font-semibold',
        value: 'text-slate-950',
        subtext: 'text-amber-950/90 font-medium',
        trendDelta: 'text-slate-950 font-bold',
      },
    }[variant]

    return (
      <div
        onClick={onClick}
        className={`rounded-[26px] p-6 border transition-all duration-200 flex flex-col justify-between shadow-[0_2px_10px_rgba(0,0,0,0.03)] ${variantStyles.container} ${
          onClick ? 'cursor-pointer hover:brightness-105 hover:shadow-md' : ''
        } ${className}`}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className={`text-xs tracking-wider uppercase font-subheading ${variantStyles.label}`}>
              {label}
            </span>
            <div className="flex items-baseline gap-1.5 mt-1.5">
              <span className={`text-3xl font-heading tracking-tight ${variantStyles.value}`}>
                {value}
              </span>
              {unit && (
                <span className={`text-xs font-mono font-medium ${variantStyles.subtext}`}>
                  {unit}
                </span>
              )}
            </div>
          </div>
          {icon && (
            <div className="p-2 rounded-xl bg-black/10 shrink-0 flex items-center justify-center">
              {icon}
            </div>
          )}
        </div>

        {(subtext || trendDelta) && (
          <div className="flex items-center gap-1.5 mt-3 pt-2 text-xs font-sans">
            {trendDelta && (
              <span className={`font-semibold font-mono ${variantStyles.trendDelta}`}>
                {trendDelta}
              </span>
            )}
            {subtext && (
              <span className={`text-[11px] ${variantStyles.subtext} ${trendDelta ? 'ml-auto' : ''}`}>
                {subtext}
              </span>
            )}
          </div>
        )}
      </div>
    )
  }

  // Standard white card fallback (Reference image card shape)
  const statusBorder = {
    normal: 'border-slate-200/90 hover:border-slate-300',
    warning: 'border-amber-300 bg-amber-50/20',
    critical: 'border-red-300 bg-red-50/20',
  }[status]

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-[26px] border p-6 transition-all duration-200 shadow-[0_2px_12px_rgba(0,0,0,0.03)] ${statusBorder} ${
        onClick ? 'cursor-pointer hover:border-slate-300 hover:shadow-md' : ''
      } ${className}`}
    >
      <div className="flex items-start justify-between text-slate-500 text-xs mb-2">
        <span className="uppercase tracking-wider font-subheading text-xs text-slate-600">{label}</span>
        {icon && <div className="text-slate-400 shrink-0">{icon}</div>}
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="text-3xl font-heading text-slate-900 tracking-tight">
          {value}
        </span>
        {unit && <span className="text-xs font-mono text-slate-500">{unit}</span>}
      </div>

      <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100 text-xs font-sans">
        {trendDelta && (
          <span
            className={`font-semibold font-mono ${
              trendDirection === 'up'
                ? status === 'critical'
                  ? 'text-red-600'
                  : 'text-emerald-600'
                : 'text-slate-600'
            }`}
          >
            {trendDelta}
          </span>
        )}
        {subtext && <span className="text-slate-400 text-[11px] ml-auto">{subtext}</span>}
      </div>
    </div>
  )
}

export const StatCard = MetricCard

