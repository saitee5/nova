import React from 'react'
import {
  Activity,
  Zap,
  Gauge,
  Thermometer,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  CartesianGrid,
} from 'recharts'
import { Card, CardHeader } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { StatCard } from '../components/common/MetricCard'
import { useRealtimeStore } from '../stores/useRealtimeStore'

// Mock 24h temporal risk trend data
const TEMPORAL_TREND = [
  { time: '00:00', risk: 18, baseline: 25 },
  { time: '02:00', risk: 20, baseline: 25 },
  { time: '04:00', risk: 22, baseline: 25 },
  { time: '06:00', risk: 28, baseline: 25 },
  { time: '08:00', risk: 35, baseline: 25 },
  { time: '09:00', risk: 42, baseline: 25 },
  { time: '10:00', risk: 65, baseline: 25 },
  { time: '10:30', risk: 78, baseline: 25 },
  { time: '11:00', risk: 88, baseline: 25 }, // Spike on F-301A anomaly
  { time: '11:30', risk: 74, baseline: 25 },
]

export const AnalyticsPage: React.FC = () => {
  const compoundAnomalies = useRealtimeStore((s) => s.compoundAnomalies)
  const openCopilot = useRealtimeStore((s) => s.openCopilot)

  // Per-bay risk data for bar chart
  const bayRiskData = [
    { bay: 'Bay 1 (Feed)', risk: 28, color: '#16A34A' },
    { bay: 'Bay 2 (Pre-Treat)', risk: 54, color: '#2563EB' },
    { bay: 'Bay 3 (Cracking)', risk: 88, color: '#DC2626' }, // Critical
    { bay: 'Bay 4 (Separation)', risk: 52, color: '#CA8A04' },
    { bay: 'Bay 5 (Utilities)', risk: 38, color: '#9333EA' },
    { bay: 'Bay 6 (Offsites)', risk: 25, color: '#0891B2' },
  ]

  // Signal type anomaly distribution
  const signalBreakdown = [
    { type: 'Skin Temperature', count: 6, icon: Thermometer, color: 'text-rose-600' },
    { type: 'Radial Vibration', count: 4, icon: Activity, color: 'text-amber-600' },
    { type: 'Differential Pressure', count: 3, icon: Gauge, color: 'text-sky-600' },
    { type: 'Combustible Gas', count: 1, icon: Zap, color: 'text-purple-600' },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-slate-700" />
            Risk & Anomaly Analytics
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Cross-unit multi-signal correlation and temporal trend analysis
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            openCopilot({
              tag: 'Bay 3',
              prompt:
                'Generate multi-variate anomaly correlation report across all bays for current production shift.',
            })
          }
        >
          <span>Correlation Report</span>
        </Button>
      </div>

      {/* ── Top Stat Cards (Matsetu Style) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          variant="navy"
          label="Peak Observed Risk"
          value="88"
          unit="/100"
          trendDelta="+23 pts vs shift start"
          trendDirection="up"
          subtext="Bay 3 Pyrolysis Furnaces"
        />
        <StatCard
          variant="gold"
          label="Correlated Anomalies"
          value={compoundAnomalies.length}
          unit="Active"
          trendDelta="Multi-sensor linkage"
          trendDirection="up"
          subtext="Thermocouple + Vibration"
        />
        <StatCard
          variant="gray"
          label="Telemetry Drift Streams"
          value="14"
          unit="Sensors"
          subtext="Exceeding 2σ deadband"
        />
        <StatCard
          variant="teal"
          label="Estimated Recovery Window"
          value="45m"
          unit="MTTR"
          subtext="Post-mitigation stabilization"
        />
      </div>

      {/* ── 1. Temporal Risk Trend Chart (Recharts) ── */}
      <Card>
        <CardHeader
          title="Plant-Wide Temporal Risk Progression (Last 12 Hours)"
          subtitle="Multi-bay risk score trajectory leading to Bay 3 critical escalation"
        />

        <div className="h-72 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={TEMPORAL_TREND} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F97316" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#F97316" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis dataKey="time" tick={{ fill: '#64748B', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#64748B', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#FFFFFF',
                  borderColor: '#E2E8F0',
                  borderRadius: '8px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  fontSize: '11px',
                }}
              />
              <Area
                type="monotone"
                dataKey="risk"
                name="Compound Risk Score"
                stroke="#F97316"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#riskGrad)"
              />
              <Area
                type="monotone"
                dataKey="baseline"
                name="Operating Baseline"
                stroke="#94A3B8"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                fill="none"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* ── 2. Two-Column Analytics Grid: Per-Bay Risk + Signal Breakdown ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Per-Bay Risk Bar Chart */}
        <Card>
          <CardHeader
            title="Risk Index by Bay Region"
            subtitle="Normalized max risk tier across equipment within each bay"
          />

          <div className="h-60 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={bayRiskData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis
                  dataKey="bay"
                  tick={{ fill: '#475569', fontSize: 10 }}
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748B', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#E2E8F0',
                    borderRadius: '6px',
                    fontSize: '11px',
                  }}
                />
                <Bar dataKey="risk" radius={[4, 4, 0, 0]}>
                  {bayRiskData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Anomaly Signal Type Breakdown (Color-blocked KPI cards with hover effects) */}
        <div className="bg-slate-50/70 rounded-2xl border border-slate-200 p-5 shadow-xs font-sans">
          <div className="pb-3 border-b border-slate-200 mb-3">
            <h3 className="text-base font-bold text-slate-900 font-heading tracking-tight">
              Anomaly Distribution by Telemetry Signal
            </h3>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              Count of sensor streams exceeding 2σ standard deviation
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            {signalBreakdown.map((item, idx) => {
              // Distinct 4-Color theme blocks (No emojis/icons, clean typography)
              const cardThemes = [
                {
                  bg: 'bg-[#2D0000] text-[#FAF3E1] hover:bg-[#3D0A0A] border-[#4A0D0D]',
                  labelColor: 'text-[#F5E7C6]/80',
                  countColor: 'text-[#FAF3E1]',
                },
                {
                  bg: 'bg-[#FF6D1F] text-[#2D0000] hover:bg-[#E05A12] border-[#E05A12]',
                  labelColor: 'text-[#4A0D0D]',
                  countColor: 'text-[#2D0000]',
                },
                {
                  bg: 'bg-[#F5E7C6] text-[#2D0000] hover:bg-[#EADBBA] border-[#E8D7B0]',
                  labelColor: 'text-[#6B3530]',
                  countColor: 'text-[#2D0000]',
                },
                {
                  bg: 'bg-[#2D0000] text-[#FAF3E1] hover:bg-[#3D0A0A] border-[#FF6D1F]',
                  labelColor: 'text-[#FF6D1F]',
                  countColor: 'text-[#FAF3E1]',
                },
              ]
              const theme = cardThemes[idx % cardThemes.length]

              return (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border transition-all duration-200 cursor-pointer shadow-xs hover:scale-[1.02] hover:shadow-md flex items-center justify-between ${theme.bg}`}
                >
                  <div>
                    <div className="text-sm font-subheading tracking-wider uppercase">
                      {item.type}
                    </div>
                    <div className={`text-[11px] font-mono mt-0.5 ${theme.labelColor}`}>
                      Cross-unit deviation
                    </div>
                  </div>

                  <div className="text-right font-mono">
                    <span className={`text-2xl font-heading tracking-tight ${theme.countColor}`}>
                      {item.count}
                    </span>
                    <span className={`text-[11px] block font-sans ${theme.labelColor}`}>
                      sensors
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 3. Compound Anomaly Explanations ── */}
      <Card variant="default" className="border-slate-200">
        <CardHeader
          title="Active Compound Correlation Reasoning"
          subtitle="Cross-equipment feedback loop diagnosed by NOVA"
        />

        {compoundAnomalies.map((anom) => (
          <div key={anom.id} className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900">{anom.title}</h3>
            <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-200 font-sans">
              {anom.novaExplanation}
            </p>

            <div className="p-3 bg-white rounded-lg border border-slate-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider block">
                  Recommended Action:
                </span>
                <span className="font-semibold text-slate-900">{anom.recommendedMitigation}</span>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  openCopilot({
                    tag: anom.primaryEquipmentTag,
                    prompt: `Execute recommended compound mitigation for ${anom.primaryEquipmentTag}.`,
                  })
                }}
              >
                Execute in Copilot
              </Button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  )
}

export default AnalyticsPage
