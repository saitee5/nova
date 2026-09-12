import React from 'react'
import { ResponsiveContainer, AreaChart, Area, YAxis } from 'recharts'

interface TelemetrySparklineProps {
  data: { timestamp: string; value: number }[]
  color?: string
  height?: number
  className?: string
}

export const TelemetrySparkline: React.FC<TelemetrySparklineProps> = ({
  data,
  color = '#F97316',
  height = 36,
  className = '',
}) => {
  if (!data || data.length === 0) return null

  const gradientId = `sparkline-grad-${Math.random().toString(36).substring(2, 9)}`

  return (
    <div className={`w-full ${className}`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.25} />
              <stop offset="95%" stopColor={color} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <YAxis domain={['auto', 'auto']} hide />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.75}
            fillOpacity={1}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
