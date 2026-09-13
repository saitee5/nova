import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layers,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import { Card, CardHeader } from '../components/common/Card'
import { MetricCard } from '../components/common/MetricCard'
import { Button } from '../components/common/Button'
import { RiskBadge, StatusBadge, AlertSeverityBadge } from '../components/common/Badge'
import { useRealtimeStore, useRiskOverview, useEquipmentList } from '../stores/useRealtimeStore'
import { useTwinStore } from '../components/plant-twin/store/useTwinStore'
import { getRiskState } from '../components/plant-twin/utils/riskUtils'

export const CommandCenterPage: React.FC = () => {
  const navigate = useNavigate()
  const riskOverview = useRiskOverview()
  const equipmentList = useEquipmentList()
  const alerts = useRealtimeStore((s) => s.alerts)
  const compoundAnomalies = useRealtimeStore((s) => s.compoundAnomalies)
  const selectEquipment = useRealtimeStore((s) => s.selectEquipment)
  const openCopilot = useRealtimeStore((s) => s.openCopilot)
  const approveRecommendation = useRealtimeStore((s) => s.approveRecommendation)
  const fetchLivePlantData = useRealtimeStore((s) => s.fetchLivePlantData)
  const isLiveLoading = useRealtimeStore((s) => s.isLiveLoading)
  const isLiveConnected = useRealtimeStore((s) => s.isLiveConnected)
  const isActionLoading = useRealtimeStore((s) => s.isActionLoading)
  const actionError = useRealtimeStore((s) => s.actionError)
  const lastLiveFetch = useRealtimeStore((s) => s.lastLiveFetch)

  // Polling hook: fetch live backend data on mount & every 5 seconds
  useEffect(() => {
    fetchLivePlantData()
    const interval = setInterval(fetchLivePlantData, 5000)
    return () => clearInterval(interval)
  }, [fetchLivePlantData])

  // Top risk equipment sorted descending
  const topRiskEquipment = [...equipmentList]
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 5)

  const activeAlerts = alerts.filter((a) => a.status !== 'RESOLVED').slice(0, 4)
  const criticalAnomaly = compoundAnomalies[0]

  const handleInspectEquipment = (equipmentId?: string, bayId?: string) => {
    let targetBay = bayId
    if (!targetBay && equipmentId) {
      const eq = equipmentList.find((e) => e.id === equipmentId || e.tag === equipmentId)
      if (eq) {
        targetBay = eq.bayId
      }
    }
    if (!targetBay) {
      targetBay = 'bay-3'
    }

    const normalizedBayId = targetBay.toLowerCase().replace(/\s+/g, '-')

    // Directly lead to the specific bay in 3D Digital Twin
    useTwinStore.getState().inspectBay(normalizedBayId, equipmentId)

    if (equipmentId) {
      selectEquipment(equipmentId)
    }
    useRealtimeStore.getState().selectBay(normalizedBayId)

    navigate('/digital-twin')
  }

  const handleAskNova = (tag: string) => {
    openCopilot({
      tag,
      prompt: `Command Center investigation: analyze risk factors for ${tag}, verify upstream/downstream dependencies, and suggest immediate mitigations.`,
    })
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 font-sans">
      {/* ── 1. Plant Status Banner ── */}
      <div
        className={`p-5 rounded-xl border shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-4 ${
          riskOverview.plantStatus === 'Critical'
            ? 'bg-red-50/70 border-red-200'
            : riskOverview.plantStatus === 'Degraded'
            ? 'bg-orange-50/70 border-orange-200'
            : 'bg-emerald-50/70 border-emerald-200'
        }`}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`w-3 h-3 rounded-full ${
                riskOverview.plantStatus === 'Critical'
                  ? 'bg-red-500 animate-ping'
                  : riskOverview.plantStatus === 'Degraded'
                  ? 'bg-orange-500 animate-pulse'
                  : 'bg-emerald-500'
              }`}
            />
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              NOVA Plant Command Center — Olefins Production Unit
            </h1>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded border uppercase ${
                riskOverview.plantStatus === 'Critical'
                  ? 'bg-red-100 text-red-800 border-red-300'
                  : riskOverview.plantStatus === 'Degraded'
                  ? 'bg-orange-100 text-orange-800 border-orange-300'
                  : 'bg-emerald-100 text-emerald-800 border-emerald-300'
              }`}
            >
              {riskOverview.plantStatus} Status
            </span>
            <span className="text-[11px] font-mono text-slate-500 ml-2">
              {isLiveConnected ? (
                <span className="text-emerald-700">
                  ● Live Backend Synchronized{' '}
                  {lastLiveFetch && (
                    <span className="text-slate-400">
                      ({new Date(lastLiveFetch).toLocaleTimeString()})
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-amber-700">○ Connecting to REST APIs...</span>
              )}
            </span>
          </div>
          <p className="text-xs text-slate-600 font-sans">
            {riskOverview.plantStatus === 'Degraded'
              ? 'Multi-signal thermal anomaly detected in Bay 3 (Furnace F-301A / Compressor K-301). Immediate operator intervention recommended.'
              : riskOverview.plantStatus === 'Critical'
              ? 'Critical process alarm trip active. Safety interlocks engaged. Immediate shift supervision intervention required.'
              : 'All plant systems operating within normal safety deadbands.'}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="nova"
            size="md"
            onClick={() =>
              openCopilot({
                tag: 'F-301A',
                prompt:
                  'Command Center Briefing: Explain active compound anomaly in Bay 3 and recommended procedure.',
              })
            }
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            <span>Ask NOVA to Brief Shift</span>
          </Button>

          <Button
            variant="outline"
            size="md"
            onClick={() => handleInspectEquipment(undefined, 'bay-3')}
          >
            <Layers className="w-4 h-4 mr-1.5 text-orange-600" />
            <span>Open 3D Live Twin</span>
          </Button>

          <button
            onClick={() => fetchLivePlantData()}
            title="Refresh from Backend"
            className="p-2 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-white transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${isLiveLoading ? 'animate-spin text-orange-500' : ''}`} />
          </button>
        </div>
      </div>

      {/* SafetyGuard Block or Action Failure Alert */}
      {actionError && (
        <div className="p-3.5 bg-red-50 border border-red-300 rounded-xl text-xs text-red-900 flex items-start gap-2.5 shadow-xs">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="font-bold text-red-900">SafetyGuard Block / Decision Validation Error</div>
            <p className="text-red-800">{actionError}</p>
          </div>
        </div>
      )}

      {/* ── 2. Top Metric Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Overall Plant Risk"
          value={`${riskOverview.overallScore}/100`}
          status={riskOverview.overallScore > 60 ? 'critical' : riskOverview.overallScore > 30 ? 'warning' : 'normal'}
          trendDelta={riskOverview.overallScore > 40 ? 'High Risk Regime' : 'Nominal Margin'}
          trendDirection={riskOverview.overallScore > 40 ? 'up' : 'down'}
          subtext="Target < 25"
        />
        <MetricCard
          label="Active Critical Alerts"
          value={activeAlerts.filter((a) => a.severity === 'critical').length}
          status={activeAlerts.some((a) => a.severity === 'critical') ? 'critical' : 'normal'}
          trendDelta={`${activeAlerts.length} total active`}
          trendDirection={activeAlerts.length > 0 ? 'up' : 'neutral'}
          subtext="Olefins Unit"
        />
        <MetricCard
          label="Equipment at Risk"
          value={riskOverview.atRiskCount}
          unit={`of ${riskOverview.totalCount} units`}
          status={riskOverview.atRiskCount > 0 ? 'warning' : 'normal'}
          trendDelta="Deterministic ML Evaluation"
          trendDirection="neutral"
          subtext="High & Critical"
        />
      </div>

      {/* ── 3. High-Value Compound Anomaly Correlation Card ── */}
      {criticalAnomaly ? (
        <Card variant="accent" className="border-orange-300">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-3 border-b border-orange-200">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200 uppercase">
                  Compound Anomaly Correlation
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Bay 3 • Correlation Score: <strong>{(criticalAnomaly.correlationScore * 100).toFixed(0)}%</strong>
                </span>
              </div>
              <h2 className="text-sm font-bold text-slate-900">
                {criticalAnomaly.title}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                disabled={isActionLoading}
                onClick={() => approveRecommendation()}
              >
                <CheckCircle2 className={`w-3.5 h-3.5 mr-1 ${isActionLoading ? 'animate-spin' : ''}`} />
                {isActionLoading ? 'Submitting to Runtime...' : 'Approve Recommended Mitigation'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleInspectEquipment('F-301A', criticalAnomaly?.bayId || 'bay-3')}
              >
                Inspect in 3D Twin
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-3 text-xs">
            {/* Plain-Language AI Explanation */}
            <div className="lg:col-span-2 space-y-2">
              <div className="text-[11px] font-mono font-semibold uppercase text-slate-500 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-orange-500" />
                <span>NOVA Cross-Unit Correlation Explanation</span>
              </div>
              <p className="text-slate-700 leading-relaxed bg-white p-3 rounded-lg border border-orange-200 shadow-2xs font-sans">
                {criticalAnomaly.novaExplanation}
              </p>
              <div className="p-2.5 rounded bg-orange-50/60 border border-orange-200 text-slate-800 font-mono text-[11px]">
                <strong>Recommended Action:</strong> {criticalAnomaly.recommendedMitigation}
              </div>
            </div>

            {/* Correlated Signals Column */}
            <div className="space-y-1.5">
              <div className="text-[11px] font-mono font-semibold uppercase text-slate-500">
                Correlated Signal Deviations
              </div>
              <div className="space-y-1">
                {criticalAnomaly.signals.map((sig, idx) => (
                  <div
                    key={idx}
                    className="p-2 rounded bg-white border border-slate-200 flex items-center justify-between text-[11px] font-mono"
                  >
                    <span className="text-slate-600">{sig.name}</span>
                    <span className="font-bold text-red-600">{sig.value} (▲)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      ) : (
        <Card variant="default" className="border-emerald-200 bg-emerald-50/40">
          <div className="flex items-center gap-2 text-emerald-800 text-xs font-semibold py-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>All monitored plant units are operating within nominal baseline parameters. No active compound anomalies.</span>
          </div>
        </Card>
      )}

      {/* ── 4. Main Two-Column Layout: Top Risk Equipment + Live Alert Stream ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Top Risk Equipment Table */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader
              title="Top Risk Equipment Items"
              subtitle="Ranked by compound risk score & real-time sensor divergence"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/equipment')}
                >
                  View All ({equipmentList.length})
                </Button>
              }
            />

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-sans">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-mono text-slate-500 uppercase tracking-wider">
                    <th className="py-2.5 px-3">Equipment</th>
                    <th className="py-2.5 px-3">Bay</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Risk Tier</th>
                    <th className="py-2.5 px-3">Key Telemetry</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {topRiskEquipment.map((item) => {
                    const tier = getRiskState(item)
                    return (
                      <tr
                        key={item.id}
                        className="hover:bg-slate-50/80 transition-colors group"
                      >
                        <td className="py-3 px-3">
                          <div className="font-mono font-bold text-slate-900">
                            {item.tag}
                          </div>
                          <div className="text-[11px] text-slate-500">{item.name}</div>
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-600">
                          {item.bayId}
                        </td>
                        <td className="py-3 px-3">
                          <StatusBadge status={item.status} />
                        </td>
                        <td className="py-3 px-3">
                          <RiskBadge tier={tier} score={item.riskScore} />
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-700">
                          {item.telemetry.temperature !== undefined ? (
                            <div>{item.telemetry.temperature.toFixed(1)}°C</div>
                          ) : (
                            <span className="text-slate-400">Nominal</span>
                          )}
                          {item.telemetry.vibration !== undefined && (
                            <div className="text-[11px] text-slate-500">
                              {item.telemetry.vibration.toFixed(2)} mm/s
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleInspectEquipment(item.id, item.bayId)}
                            >
                              Inspect 3D
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                              onClick={() => handleAskNova(item.tag)}
                            >
                              <Sparkles className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Right Col: Live Alert Stream */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Live Alert Stream"
              subtitle="Real-time predictive alarms from backend"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/alerts')}
                >
                  All Alerts
                </Button>
              }
            />

            <div className="space-y-3">
              {activeAlerts.length > 0 ? (
                activeAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    onClick={() => handleInspectEquipment(alert.equipmentId)}
                    className="p-3 rounded-lg border border-slate-200 bg-white hover:border-orange-300 hover:shadow-xs transition-all cursor-pointer space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <AlertSeverityBadge severity={alert.severity} />
                        <span className="font-mono font-bold text-xs text-slate-900">
                          {alert.equipmentTag}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">
                        {alert.timestamp}
                      </span>
                    </div>

                    <p className="text-xs text-slate-700 line-clamp-2 leading-relaxed font-sans">
                      {alert.title}
                    </p>

                    <div className="text-[11px] font-mono text-slate-500 pt-1 flex items-center justify-between">
                      <span>{alert.bayId}</span>
                      <span className="text-orange-600 flex items-center gap-0.5">
                        Inspect <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-xs text-slate-500 font-mono">
                  No active alarms recorded on backend.
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default CommandCenterPage
