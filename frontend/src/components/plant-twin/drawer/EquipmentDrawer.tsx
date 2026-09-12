import React from 'react'
import {
  X,
  AlertTriangle,
  Activity,
  Thermometer,
  Gauge,
  Wind,
  Zap,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  CheckCircle2,
  AlertOctagon,
  ShieldAlert,
  History,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Tooltip as RechartsTooltip,
  YAxis,
} from 'recharts'
import { useTwinStore } from '../store/useTwinStore'
import { useRealtimeStore } from '../../../stores/useRealtimeStore'
import { getRiskState, RISK_COLORS, STATUS_COLORS } from '../utils/riskUtils'
import { toCanonicalAssetId } from '../../../utils/assetAliases'
import { getTelemetry, getTelemetryTimeseries, getEpisodes } from '../../../services/api'
import type { OperationalEpisode } from '../../../types/industrial'

export const EquipmentDrawer: React.FC = () => {
  const isDrawerOpen = useTwinStore((s) => s.isDrawerOpen)
  const selectedEquipmentId = useTwinStore((s) => s.selectedEquipmentId)
  const equipmentList = useTwinStore((s) => s.equipmentList)
  const closeDrawer = useTwinStore((s) => s.closeDrawer)
  const selectEquipment = useTwinStore((s) => s.selectEquipment)
  const openCopilot = useRealtimeStore((s) => s.openCopilot)

  const [liveTrend, setLiveTrend] = React.useState<{ timestamp: string; value: number }[]>([])
  const [liveTelemetry, setLiveTelemetry] = React.useState<Record<string, number>>({})
  const [liveEpisodes, setLiveEpisodes] = React.useState<OperationalEpisode[]>([])

  if (!isDrawerOpen || !selectedEquipmentId) {
    return null
  }

  const equipment = equipmentList.find((e) => e.id === selectedEquipmentId)
  if (!equipment) return null

  // Fetch live telemetry, timeseries, and correlated episodes on asset selection
  React.useEffect(() => {
    if (!equipment) return
    const canonicalId = toCanonicalAssetId(equipment.tag || equipment.id)

    // 1. Live timeseries trend
    getTelemetryTimeseries(canonicalId, undefined, 20)
      .then((points) => {
        if (points && points.length > 0) {
          setLiveTrend(
            points.map((p) => ({
              timestamp: new Date(p.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              }),
              value: p.value,
            }))
          )
        }
      })
      .catch(() => {})

    // 2. Live telemetry points
    getTelemetry(canonicalId)
      .then((records) => {
        if (records && records.length > 0) {
          const map: Record<string, number> = {}
          records.forEach((r) => {
            const key = (r.parameter || r.tag).toLowerCase()
            if (key.includes('temp') || key.includes('ti-')) map.temperature = r.value
            else if (key.includes('vib') || key.includes('vi-')) map.vibration = r.value
            else if (key.includes('pres') || key.includes('pi-')) map.pressure = r.value
            else if (key.includes('flow') || key.includes('fi-')) map.flow = r.value
          })
          setLiveTelemetry(map)
        }
      })
      .catch(() => {})

    // 3. Correlated operational episodes
    getEpisodes()
      .then((eps) => {
        const filtered = eps.filter(
          (ep) =>
            ep.asset_id === canonicalId ||
            (ep.assets && ep.assets.includes(canonicalId))
        )
        setLiveEpisodes(filtered)
      })
      .catch(() => {})
  }, [equipment.id, equipment.tag])

  const riskTier = getRiskState(equipment)
  const riskMeta = RISK_COLORS[riskTier]
  const statusMeta = STATUS_COLORS[equipment.status]
  const telemetry = { ...equipment.telemetry, ...liveTelemetry }
  const trendData = liveTrend.length > 0 ? liveTrend : equipment.trend

  const backendIncidents = React.useMemo(() => {
    return liveEpisodes.map((ep) => ({
      id: ep.episode_id,
      date: new Date(ep.start_time).toLocaleDateString(),
      title: ep.title,
      damageType: 'Operational Episode',
      severity: (ep.severity.toLowerCase() as 'critical' | 'high' | 'medium' | 'low') || 'high',
      summary: ep.summary || 'Correlated operational episode logged by NOVA.',
      downtimeHours: ep.end_time ? 2 : 0,
      actionTaken: ep.risk_assessment?.recommended_actions?.[0] || 'Under advisory observation',
    }))
  }, [liveEpisodes])

  const incidentsToDisplay =
    backendIncidents.length > 0 ? backendIncidents : equipment.historicalIncidents

  const handleEquipmentHop = (id: string) => {
    selectEquipment(id)
  }

  const handleAskNova = () => {
    openCopilot({
      tag: equipment.tag,
      prompt: `Analyze current state and anomalies for ${equipment.name} (${equipment.tag}). Risk score is ${equipment.riskScore}/100. Status: ${equipment.status}. Active anomaly: ${equipment.anomalyDetails || 'Elevated temperature/vibration'}. Recommend operating adjustments and mitigation steps.`,
    })
  }

  return (
    <div className="fixed top-0 right-0 bottom-0 w-full sm:w-[460px] bg-white border-l border-slate-200 shadow-2xl z-40 flex flex-col transition-all duration-300 animate-in slide-in-from-right font-sans">
      {/* ── HEADER ── */}
      <div className="p-4 border-b border-slate-200 flex items-start justify-between bg-slate-50/80">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-orange-100 text-orange-900 border border-orange-200">
              {equipment.tag}
            </span>
            <span className="text-xs text-slate-500 font-mono uppercase tracking-wider">
              {equipment.type}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              • {equipment.bayId}
            </span>
          </div>
          <h2 className="text-base font-bold text-slate-900 tracking-tight leading-tight">
            {equipment.name}
          </h2>
        </div>

        <button
          onClick={closeDrawer}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
          title="Close details"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* ── BODY (Scrollable) ── */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
        {/* Status & Risk Banner */}
        <div className="grid grid-cols-2 gap-3">
          {/* Status Badge */}
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs flex flex-col justify-between">
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              Status
            </span>
            <div className="flex items-center gap-2 mt-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: statusMeta.hex }}
              />
              <span className="font-bold text-slate-900">{statusMeta.label}</span>
            </div>
          </div>

          {/* Computed Risk State Badge */}
          <div
            className={`p-3 rounded-lg border shadow-2xs flex flex-col justify-between ${riskMeta.bgClass} ${riskMeta.borderClass}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-600">
                Risk Tier
              </span>
              <span className="font-mono text-xs font-bold text-slate-700">
                {equipment.riskScore}/100
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-1.5">
              {riskTier === 'CRITICAL' ? (
                <AlertOctagon className="w-4 h-4 text-red-600" />
              ) : riskTier === 'HIGH' ? (
                <ShieldAlert className="w-4 h-4 text-orange-600" />
              ) : riskTier === 'MEDIUM' ? (
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              )}
              <span className={`font-bold ${riskMeta.textClass}`}>
                {riskTier}
              </span>
            </div>
          </div>
        </div>

        {/* Anomaly Callout Banner (if detected) */}
        {equipment.anomalyDetected && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 space-y-1">
            <div className="flex items-center gap-2 text-red-800 font-bold text-xs">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              <span>ACTIVE ANOMALY DETECTED</span>
            </div>
            <p className="text-xs text-red-700 leading-relaxed font-sans">
              {equipment.anomalyDetails ||
                'Signal deviations exceed acceptable operating threshold.'}
            </p>
          </div>
        )}

        {/* Real-time Telemetry Cards */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
              Live Telemetry
            </span>
            <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
              <Clock className="w-3 h-3" />
              {new Date(telemetry.lastUpdated).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {telemetry.temperature !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-0.5">
                  <Thermometer className="w-3 h-3 text-rose-500" />
                  <span>Temperature</span>
                </div>
                <div className="text-base font-mono font-bold text-slate-900">
                  {telemetry.temperature.toFixed(1)}
                  <span className="text-xs text-slate-500 font-normal ml-1">°C</span>
                </div>
              </div>
            )}

            {telemetry.pressure !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-0.5">
                  <Gauge className="w-3 h-3 text-sky-500" />
                  <span>Pressure</span>
                </div>
                <div className="text-base font-mono font-bold text-slate-900">
                  {telemetry.pressure.toFixed(1)}
                  <span className="text-xs text-slate-500 font-normal ml-1">bar</span>
                </div>
              </div>
            )}

            {telemetry.flow !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-0.5">
                  <Wind className="w-3 h-3 text-emerald-500" />
                  <span>Flow Rate</span>
                </div>
                <div className="text-base font-mono font-bold text-slate-900">
                  {telemetry.flow.toFixed(1)}
                  <span className="text-xs text-slate-500 font-normal ml-1">m³/h</span>
                </div>
              </div>
            )}

            {telemetry.vibration !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-0.5">
                  <Activity className="w-3 h-3 text-amber-500" />
                  <span>Vibration</span>
                </div>
                <div className="text-base font-mono font-bold text-slate-900">
                  {telemetry.vibration.toFixed(2)}
                  <span className="text-xs text-slate-500 font-normal ml-1">mm/s</span>
                </div>
              </div>
            )}

            {telemetry.gasConcentration !== undefined && (
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 col-span-2">
                <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-0.5">
                  <Zap className="w-3 h-3 text-purple-500" />
                  <span>Combustible Gas / LEL</span>
                </div>
                <div className="text-base font-mono font-bold text-slate-900">
                  {telemetry.gasConcentration.toFixed(1)}
                  <span className="text-xs text-slate-500 font-normal ml-1">% LEL</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Recent Trend Sparkline */}
        {trendData && trendData.length > 0 && (
          <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
                Operational Trend (Live Sensor Timeseries)
              </span>
            </div>
            <div className="h-24 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={trendData}
                  margin={{ top: 5, right: 5, left: -25, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="trendLightGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={riskTier === 'CRITICAL' ? '#DC2626' : '#F97316'}
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor={riskTier === 'CRITICAL' ? '#DC2626' : '#F97316'}
                        stopOpacity={0.0}
                      />
                    </linearGradient>
                  </defs>
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fill: '#64748B', fontSize: 10 }}
                    width={35}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#FFFFFF',
                      borderColor: '#E2E8F0',
                      borderRadius: '6px',
                      fontSize: '11px',
                      color: '#0F172A',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={riskTier === 'CRITICAL' ? '#DC2626' : '#F97316'}
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#trendLightGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Process Topology: Upstream & Downstream */}
        <div className="space-y-1.5">
          <span className="font-mono text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
            Process Topology
          </span>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-1">
                <ArrowDownRight className="w-3.5 h-3.5 text-sky-600" />
                <span>Upstream</span>
              </div>
              {equipment.relatedEquipmentIds.upstream.length === 0 ? (
                <div className="text-[11px] text-slate-400 italic">None (Feed start)</div>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {equipment.relatedEquipmentIds.upstream.map((upId) => (
                    <button
                      key={upId}
                      onClick={() => handleEquipmentHop(upId)}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-white hover:bg-orange-50 hover:text-orange-700 text-slate-700 border border-slate-200 shadow-2xs transition-colors cursor-pointer"
                    >
                      {upId}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-1 text-slate-500 text-[11px] mb-1">
                <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
                <span>Downstream</span>
              </div>
              {equipment.relatedEquipmentIds.downstream.length === 0 ? (
                <div className="text-[11px] text-slate-400 italic">None (Export end)</div>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {equipment.relatedEquipmentIds.downstream.map((downId) => (
                    <button
                      key={downId}
                      onClick={() => handleEquipmentHop(downId)}
                      className="text-[11px] font-mono px-2 py-0.5 rounded bg-white hover:bg-emerald-50 hover:text-emerald-700 text-slate-700 border border-slate-200 shadow-2xs transition-colors cursor-pointer"
                    >
                      {downId}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── PREVIOUS DAMAGE & INCIDENT TIMELINE ── */}
        <div className="space-y-2.5 pt-3 border-t border-slate-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-orange-600" />
              <span
                style={{
                  fontFamily: "'Bebas Neue', 'Archivo Black', sans-serif",
                  letterSpacing: '0.06em',
                  fontSize: '1.2rem',
                  lineHeight: 1,
                  color: '#0F172A',
                }}
              >
                DAMAGE & INCIDENT TIMELINE
              </span>
            </div>
            {incidentsToDisplay && incidentsToDisplay.length > 0 ? (
              <span
                style={{ fontFamily: "'Roboto Mono', monospace" }}
                className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200"
              >
                {incidentsToDisplay.length} Event{incidentsToDisplay.length > 1 ? 's' : ''}
              </span>
            ) : (
              <span
                style={{ fontFamily: "'Roboto Mono', monospace" }}
                className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200"
              >
                0 Incidents
              </span>
            )}
          </div>

          {incidentsToDisplay && incidentsToDisplay.length > 0 ? (
            <div className="relative pl-5 space-y-3.5 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {incidentsToDisplay.map((inc, i) => (
                <div key={inc.id || i} className="relative group">
                  {/* Timeline node */}
                  <span
                    className={`absolute -left-5 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-white shadow-xs ${
                      inc.severity === 'critical'
                        ? 'bg-red-500 ring-2 ring-red-200'
                        : inc.severity === 'high'
                        ? 'bg-orange-500 ring-2 ring-orange-200'
                        : 'bg-amber-500 ring-2 ring-amber-200'
                    }`}
                  />

                  {/* Incident Card */}
                  <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs space-y-2 hover:border-slate-300 transition-colors">
                    {/* Date and Tags row */}
                    <div className="flex items-center justify-between gap-2">
                      <span
                        style={{ fontFamily: "'Roboto Mono', monospace" }}
                        className="text-[11px] font-bold text-slate-800 flex items-center gap-1.5"
                      >
                        <Clock className="w-3 h-3 text-slate-400" />
                        {inc.date}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {inc.damageType && (
                          <span
                            style={{ fontFamily: "'Roboto Mono', monospace" }}
                            className="text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200"
                          >
                            {inc.damageType}
                          </span>
                        )}
                        <span
                          style={{ fontFamily: "'Roboto Mono', monospace" }}
                          className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                            inc.severity === 'critical'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : inc.severity === 'high'
                              ? 'bg-orange-50 text-orange-700 border border-orange-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {inc.severity || 'Damage'}
                        </span>
                      </div>
                    </div>

                    {/* Damage Title */}
                    {inc.title && (
                      <h4
                        style={{
                          fontFamily: "'Doppio One', 'Saira', sans-serif",
                          letterSpacing: '0.01em',
                        }}
                        className="text-xs font-bold text-slate-900 leading-snug"
                      >
                        {inc.title}
                      </h4>
                    )}

                    {/* Detailed Damage Summary */}
                    <p
                      style={{
                        fontFamily: "'Titillium Web', sans-serif",
                        fontSize: '0.84rem',
                        lineHeight: 1.45,
                      }}
                      className="text-slate-600 font-normal"
                    >
                      {inc.summary}
                    </p>

                    {/* Action Taken & Downtime */}
                    {(inc.downtimeHours || inc.actionTaken) && (
                      <div className="pt-2 border-t border-slate-100 space-y-1.5">
                        {inc.downtimeHours && (
                          <div className="flex items-center gap-1 text-[10px] font-mono text-slate-600">
                            <span className="text-slate-400">Repair Downtime:</span>
                            <span className="font-bold text-red-600">{inc.downtimeHours} Hours</span>
                          </div>
                        )}
                        {inc.actionTaken && (
                          <div
                            style={{
                              fontFamily: "'Roboto Slab', 'Titillium Web', serif",
                              fontSize: '0.78rem',
                            }}
                            className="flex items-start gap-1.5 text-slate-700 bg-slate-50 p-2 rounded border border-slate-200"
                          >
                            <Wrench className="w-3.5 h-3.5 text-orange-500 shrink-0 mt-0.5" />
                            <div>
                              <strong className="font-semibold text-slate-900">Corrective Action: </strong>
                              {inc.actionTaken}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3.5 rounded-lg bg-emerald-50/70 border border-emerald-200 flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <div
                  style={{
                    fontFamily: "'Doppio One', 'Saira', sans-serif",
                  }}
                  className="text-xs font-bold text-emerald-950"
                >
                  No Previous Damage Incidents Recorded
                </div>
                <p
                  style={{
                    fontFamily: "'Titillium Web', sans-serif",
                    fontSize: '0.8rem',
                    lineHeight: 1.4,
                  }}
                  className="text-emerald-800/90 font-normal"
                >
                  This machinery has 0 recorded catastrophic failures, mechanical ruptures, or un-scheduled emergency replacements. Continuous structural baseline integrity verified.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Active Alerts */}
        {equipment.activeAlerts.length > 0 && (
          <div className="space-y-1.5">
            <span className="font-mono text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
              Active Alerts ({equipment.activeAlerts.length})
            </span>
            <div className="space-y-1">
              {equipment.activeAlerts.map((alt) => (
                <div
                  key={alt.id}
                  className={`p-2 rounded border text-xs leading-relaxed ${
                    alt.severity === 'critical'
                      ? 'bg-red-50 border-red-200 text-red-800'
                      : alt.severity === 'high'
                      ? 'bg-orange-50 border-orange-200 text-orange-900'
                      : 'bg-amber-50 border-amber-200 text-amber-900'
                  }`}
                >
                  <div className="flex items-center justify-between font-mono text-[10px] text-slate-500 mb-0.5">
                    <span className="uppercase font-bold">{alt.severity}</span>
                    <span>{alt.timestamp}</span>
                  </div>
                  {alt.message}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── FOOTER: "Ask NOVA" Button ── */}
      <div className="p-4 border-t border-slate-200 bg-slate-50">
        <button
          onClick={handleAskNova}
          className="w-full py-2.5 px-4 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-medium text-xs shadow-md shadow-orange-500/20 flex items-center justify-center gap-2 transition-all active:scale-[0.99] cursor-pointer"
        >
          <Sparkles className="w-4 h-4" />
          <span>Ask NOVA About {equipment.tag}</span>
        </button>
      </div>
    </div>
  )
}
