import React, { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Cpu,
  Search,
  Layers,
  Activity,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '../components/common/Button'
import { StatCard } from '../components/common/MetricCard'
import { RiskBadge, StatusBadge } from '../components/common/Badge'
import { TelemetrySparkline } from '../components/common/TelemetrySparkline'
import { useRealtimeStore, useEquipmentList } from '../stores/useRealtimeStore'
import { getRiskState } from '../components/plant-twin/utils/riskUtils'
import { EquipmentType, RiskTier } from '../components/plant-twin/types'

export const EquipmentPage: React.FC = () => {
  const { id: routeId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const equipmentList = useEquipmentList()
  const selectEquipment = useRealtimeStore((s) => s.selectEquipment)
  const openCopilot = useRealtimeStore((s) => s.openCopilot)
  const fetchLivePlantData = useRealtimeStore((s) => s.fetchLivePlantData)

  React.useEffect(() => {
    fetchLivePlantData()
  }, [fetchLivePlantData])

  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<EquipmentType | 'ALL'>('ALL')
  const [riskFilter, setRiskFilter] = useState<RiskTier | 'ALL'>('ALL')
  const [selectedId, setSelectedId] = useState<string>(routeId || 'F-301A')

  // Filtered equipment list
  const filteredList = useMemo(() => {
    return equipmentList.filter((item) => {
      const tier = getRiskState(item)
      if (typeFilter !== 'ALL' && item.type !== typeFilter) return false
      if (riskFilter !== 'ALL' && tier !== riskFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        return item.tag.toLowerCase().includes(q) || item.name.toLowerCase().includes(q)
      }
      return true
    })
  }, [equipmentList, typeFilter, riskFilter, searchQuery])

  const currentItem = equipmentList.find((e) => e.id === selectedId) || filteredList[0] || equipmentList[0]

  const handleInspectInTwin = (id: string) => {
    selectEquipment(id)
    navigate('/digital-twin')
  }

  const handleAskNova = (tag: string) => {
    openCopilot({
      tag,
      prompt: `Full equipment audit for ${tag}: check thermal operating margins, historical vibration trends, and upstream/downstream dependencies.`,
    })
  }

  const criticalEquipCount = equipmentList.filter((e) => getRiskState(e) === 'CRITICAL').length
  const highEquipCount = equipmentList.filter((e) => getRiskState(e) === 'HIGH').length
  const normalEquipCount = equipmentList.filter((e) => getRiskState(e) === 'LOW').length

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12 font-sans">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Cpu className="w-5 h-5 text-slate-700" />
            Equipment Explorer & Asset Intelligence
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Real-time telemetry, operating specs, and upstream/downstream process topology
          </p>
        </div>
      </div>

      {/* ── Top Stat Cards (Matsetu Style) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          variant="navy"
          label="Total Active Equipment"
          value={equipmentList.length}
          unit="Units"
          icon={<Cpu className="w-5 h-5 text-white" />}
          subtext="Distributed across 5 Bays"
        />
        <StatCard
          variant="gold"
          label="Critical Assets at Risk"
          value={criticalEquipCount}
          unit="Hotspots"
          icon={<AlertTriangle className="w-5 h-5 text-white" />}
          trendDelta="Immediate inspection"
          trendDirection="up"
          subtext="Furnace F-301A / Comp K-301"
        />
        <StatCard
          variant="gray"
          label="Elevated Risk (High)"
          value={highEquipCount}
          unit="Units"
          icon={<Activity className="w-5 h-5 text-slate-900" />}
          subtext="Sensor divergence detected"
        />
        <StatCard
          variant="teal"
          label="Nominal Operation"
          value={normalEquipCount}
          unit="Units"
          icon={<CheckCircle2 className="w-5 h-5 text-white" />}
          subtext="Within design limits"
        />
      </div>

      {/* ── Filters Bar ── */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Risk Filter */}
          <span className="text-[10px] font-mono text-slate-500 font-semibold uppercase mr-1">
            Risk:
          </span>
          {(['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const).map((tier) => (
            <button
              key={tier}
              onClick={() => setRiskFilter(tier)}
              className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors cursor-pointer border ${
                riskFilter === tier
                  ? 'bg-orange-500 text-white font-semibold border-orange-600'
                  : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border-slate-200'
              }`}
            >
              {tier}
            </button>
          ))}

          {/* Type Filter */}
          <span className="text-[10px] font-mono text-slate-500 font-semibold uppercase ml-2 mr-1">
            Type:
          </span>
          {(['ALL', 'furnace', 'compressor', 'column', 'heatExchanger', 'pump', 'tank', 'valve'] as const).map(
            (tp) => (
              <button
                key={tp}
                onClick={() => setTypeFilter(tp)}
                className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize transition-colors cursor-pointer border ${
                  typeFilter === tp
                    ? 'bg-orange-500 text-white font-semibold border-orange-600'
                    : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border-slate-200'
                }`}
              >
                {tp}
              </button>
            )
          )}
        </div>

        {/* Search */}
        <div className="flex items-center bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 w-56">
          <Search className="w-3.5 h-3.5 text-slate-400 mr-1.5 shrink-0" />
          <input
            type="text"
            placeholder="Filter tag or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-0 text-xs text-slate-900 placeholder-slate-400 focus:outline-none w-full font-sans"
          />
        </div>
      </div>

      {/* ── Two-Pane Layout: Equipment Catalog (Left) + Detail (Right) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left List (5 cols) */}
        <div className="lg:col-span-5 space-y-2 max-h-[750px] overflow-y-auto pr-1">
          {filteredList.map((item) => {
            const isSelected = item.id === currentItem?.id
            const tier = getRiskState(item)
            const borderAccent =
              tier === 'CRITICAL'
                ? 'border-l-red-600'
                : tier === 'HIGH'
                ? 'border-l-orange-500'
                : tier === 'MEDIUM'
                ? 'border-l-amber-500'
                : 'border-l-emerald-500'

            return (
              <div
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                className={`p-3 rounded-xl border border-slate-200 transition-all cursor-pointer space-y-1.5 relative border-l-4 ${borderAccent} ${
                  isSelected
                    ? 'bg-slate-50/90 ring-1 ring-slate-300'
                    : 'bg-white hover:bg-slate-50/50 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs text-slate-900">
                      {item.tag}
                    </span>
                    <span className="text-[11px] font-mono text-slate-500 uppercase">
                      {item.type}
                    </span>
                  </div>
                  <RiskBadge tier={tier} score={item.riskScore} />
                </div>

                <div className="text-xs font-semibold text-slate-800 font-heading">{item.name}</div>

                <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 pt-1 border-t border-slate-100">
                  <span>{item.bayId}</span>
                  <StatusBadge status={item.status} />
                </div>
              </div>
            )
          })}
        </div>

        {/* Right Reusable Detail Panel (7 cols - Lighter grayish background, rounded-2xl) */}
        {currentItem && (
          <div className="lg:col-span-7 space-y-4">
            <div className="bg-slate-50/70 rounded-2xl border border-slate-200 p-5 shadow-xs font-sans">
              {/* Header */}
              <div className="pb-4 border-b border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold px-2 py-0.5 rounded bg-white text-slate-900 border border-slate-200">
                      {currentItem.tag}
                    </span>
                    <span className="text-xs font-mono uppercase text-slate-500">
                      {currentItem.type}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      • {currentItem.bayId}
                    </span>
                  </div>
                  <RiskBadge tier={getRiskState(currentItem)} score={currentItem.riskScore} />
                </div>

                <h2 className="text-base font-bold text-slate-900">
                  {currentItem.name}
                </h2>

                <div className="flex items-center gap-3 pt-1">
                  {/* Single Primary Action in Solid Orange */}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleAskNova(currentItem.tag)}
                  >
                    Ask NOVA About {currentItem.tag}
                  </Button>
                  {/* Secondary Action in Outline */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleInspectInTwin(currentItem.id)}
                  >
                    <Layers className="w-3.5 h-3.5 mr-1 text-slate-700" />
                    Inspect in 3D Live Twin
                  </Button>
                </div>
              </div>

              {/* Live Telemetry Grid */}
              <div className="py-4 space-y-2 border-b border-slate-200">
                <h3 className="text-xs font-bold font-mono text-slate-700 uppercase tracking-wider">
                  Live Sensor Streams
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs font-mono">
                  {currentItem.telemetry.temperature !== undefined && (
                    <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-500 text-[10px]">TEMPERATURE</div>
                      <div className="text-base font-bold text-slate-900">
                        {currentItem.telemetry.temperature.toFixed(1)}°C
                      </div>
                    </div>
                  )}
                  {currentItem.telemetry.pressure !== undefined && (
                    <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-500 text-[10px]">PRESSURE</div>
                      <div className="text-base font-bold text-slate-900">
                        {currentItem.telemetry.pressure.toFixed(1)} bar
                      </div>
                    </div>
                  )}
                  {currentItem.telemetry.flow !== undefined && (
                    <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-500 text-[10px]">FLOW RATE</div>
                      <div className="text-base font-bold text-slate-900">
                        {currentItem.telemetry.flow.toFixed(1)} m³/h
                      </div>
                    </div>
                  )}
                  {currentItem.telemetry.vibration !== undefined && (
                    <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-500 text-[10px]">VIBRATION</div>
                      <div className="text-base font-bold text-slate-900">
                        {currentItem.telemetry.vibration.toFixed(2)} mm/s
                      </div>
                    </div>
                  )}
                  {currentItem.telemetry.gasConcentration !== undefined && (
                    <div className="p-2.5 rounded bg-slate-50 border border-slate-200">
                      <div className="text-slate-500 text-[10px]">GAS (LEL)</div>
                      <div className="text-base font-bold text-slate-900">
                        {currentItem.telemetry.gasConcentration.toFixed(1)}%
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Sparkline Trend */}
              {currentItem.trend && currentItem.trend.length > 0 && (
                <div className="py-4 space-y-2 border-b border-slate-200">
                  <h3 className="text-xs font-bold font-mono text-slate-700 uppercase tracking-wider">
                    Recent Operating Trend (60 min)
                  </h3>
                  <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                    <TelemetrySparkline
                      data={currentItem.trend}
                      color={getRiskState(currentItem) === 'CRITICAL' ? '#DC2626' : '#F97316'}
                      height={48}
                    />
                  </div>
                </div>
              )}

              {/* Technical Specifications */}
              {currentItem.specs && Object.keys(currentItem.specs).length > 0 && (
                <div className="py-4 space-y-2 border-b border-slate-200">
                  <h3 className="text-xs font-bold font-mono text-slate-700 uppercase tracking-wider">
                    Design & Operating Specifications
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-xs font-sans">
                    {Object.entries(currentItem.specs).map(([k, v]) => (
                      <div key={k} className="p-2 rounded bg-slate-50 border border-slate-200">
                        <span className="text-slate-500 block text-[10px] font-mono uppercase">{k}</span>
                        <span className="font-semibold text-slate-900 font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Upstream & Downstream Process Topology */}
              <div className="pt-4 space-y-2">
                <h3 className="text-xs font-bold font-mono text-slate-700 uppercase tracking-wider">
                  Process Topology Connections
                </h3>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-mono text-slate-500 block mb-1">Upstream</span>
                    <div className="flex flex-wrap gap-1">
                      {currentItem.relatedEquipmentIds.upstream.map((up) => (
                        <button
                          key={up}
                          onClick={() => setSelectedId(up)}
                          className="px-2 py-0.5 rounded bg-white text-orange-800 font-mono text-xs border border-slate-200 hover:border-orange-400 cursor-pointer"
                        >
                          {up}
                        </button>
                      ))}
                      {currentItem.relatedEquipmentIds.upstream.length === 0 && (
                        <span className="text-slate-400 italic">None (Feed Header)</span>
                      )}
                    </div>
                  </div>

                  <div className="p-3 rounded bg-slate-50 border border-slate-200">
                    <span className="text-[11px] font-mono text-slate-500 block mb-1">Downstream</span>
                    <div className="flex flex-wrap gap-1">
                      {currentItem.relatedEquipmentIds.downstream.map((down) => (
                        <button
                          key={down}
                          onClick={() => setSelectedId(down)}
                          className="px-2 py-0.5 rounded bg-white text-emerald-800 font-mono text-xs border border-slate-200 hover:border-emerald-400 cursor-pointer"
                        >
                          {down}
                        </button>
                      ))}
                      {currentItem.relatedEquipmentIds.downstream.length === 0 && (
                        <span className="text-slate-400 italic">None (Export Header)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default EquipmentPage
