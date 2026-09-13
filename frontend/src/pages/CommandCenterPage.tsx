import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layers,
  ArrowRight,
  CheckCircle2,
  Shield,
} from 'lucide-react'
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

  // Top risk equipment sorted descending
  const topRiskEquipment = [...equipmentList]
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 5)

  const activeAlerts = alerts.filter((a) => a.status !== 'RESOLVED')
  const criticalAnomaly = compoundAnomalies[0]

  // Calculate Risk Breakdown for the Segmented Progress Bar (Matsetu Style)
  const riskDistribution = React.useMemo(() => {
    let normal = 0
    let warning = 0
    let high = 0
    let critical = 0
    const total = equipmentList.length || 1

    equipmentList.forEach((e) => {
      const state = getRiskState(e)
      if (state === 'CRITICAL') critical++
      else if (state === 'HIGH') high++
      else if (state === 'MEDIUM') warning++
      else normal++
    })

    const normalPct = Math.round((normal / total) * 100)
    const warningPct = Math.round((warning / total) * 100)
    const highPct = Math.round((high / total) * 100)
    // Balance to 100
    const criticalPct = Math.max(0, 100 - (normalPct + warningPct + highPct))

    return { normalPct, warningPct, highPct, criticalPct }
  }, [equipmentList])

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
        className={`p-5 rounded-[24px] border flex flex-col lg:flex-row lg:items-center justify-between gap-4 ${riskOverview.plantStatus === 'Critical'
          ? 'bg-red-50/70 border-red-200'
          : riskOverview.plantStatus === 'Degraded'
            ? 'bg-orange-50/50 border-orange-200/80'
            : 'bg-emerald-50/70 border-emerald-200'
          }`}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${riskOverview.plantStatus === 'Critical'
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
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded border uppercase ${riskOverview.plantStatus === 'Critical'
                ? 'bg-red-100 text-red-800 border-red-300'
                : riskOverview.plantStatus === 'Degraded'
                  ? 'bg-orange-100 text-orange-800 border-orange-200'
                  : 'bg-emerald-100 text-emerald-800 border-emerald-300'
                }`}
            >
              {riskOverview.plantStatus} Status
            </span>
          </div>
          <p className="text-xs text-slate-600 font-sans">
            {riskOverview.plantStatus === 'Degraded'
              ? 'Multi-signal thermal anomaly detected in Bay 3 (Furnace F-301A / Compressor K-301). Immediate operator intervention recommended.'
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
            <span>Shift Briefing</span>
          </Button>

          <Button
            variant="outline"
            size="md"
            onClick={() => handleInspectEquipment(undefined, 'bay-3')}
          >
            <Layers className="w-4 h-4 mr-1.5 text-slate-700" />
            <span>Open 3D Live Twin</span>
          </Button>
        </div>
      </div>

      {/* ── 2. Top Color-Blocked Metric Cards (Matsetu Style) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Navy - Overall Plant Risk */}
        <MetricCard
          variant="navy"
          label="Overall Plant Risk"
          value={`${riskOverview.overallScore}`}
          unit="/100"
          trendDelta={riskOverview.overallScore > 40 ? '+14% last hour' : '-2%'}
          trendDirection={riskOverview.overallScore > 40 ? 'up' : 'down'}
          subtext="Target deadband < 25"
        />

        {/* Card 2: Muted Teal - Equipment Monitored */}
        <MetricCard
          variant="teal"
          label="Units Monitored"
          value={riskOverview.totalCount}
          unit="Active"
          trendDelta="Bay 1–5 Telemetry"
          trendDirection="neutral"
          subtext="100% sensors online"
        />

        {/* Card 3: Cool Slate Gray - Anomalies Detected */}
        <MetricCard
          variant="gray"
          label="Anomalies Detected"
          value={riskOverview.anomalyCount}
          unit="flags"
          trendDelta="~3% estimated flag rate"
          trendDirection="neutral"
          subtext="Bay 3 Cracking Hotspot"
        />

        {/* Card 4: Mustard / Gold - Active Critical Alerts */}
        <MetricCard
          variant="gold"
          label="Mitigations Required"
          value={activeAlerts.filter((a) => a.severity === 'critical').length}
          unit="pending"
          trendDelta="Approval required"
          trendDirection="up"
          subtext="Manual review needed"
        />
      </div>

      {/* ── 3. Risk Distribution Segmented Progress Bar (Rounded Reference Style) ── */}
      <div className="bg-white rounded-[28px] border border-slate-200/80 p-6 space-y-4 shadow-[0_2px_12px_rgba(0,0,0,0.03)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-orange-500" />
            <span className="text-base font-bold text-slate-900 font-heading">Risk Distribution</span>
          </div>
          <span className="text-xs text-slate-500 font-sans">
            Based on multi-sensor risk concentration
          </span>
        </div>

        {/* Single Segmented Bar */}
        <div className="w-full h-3.5 rounded-full overflow-hidden flex bg-slate-100">
          <div
            style={{ width: `${riskDistribution.normalPct}%` }}
            className="bg-[#4A7C7C] h-full transition-all duration-500"
            title={`Normal: ${riskDistribution.normalPct}%`}
          />
          <div
            style={{ width: `${riskDistribution.warningPct}%` }}
            className="bg-[#C9A227] h-full transition-all duration-500"
            title={`Warning: ${riskDistribution.warningPct}%`}
          />
          <div
            style={{ width: `${riskDistribution.highPct}%` }}
            className="bg-[#94A3B8] h-full transition-all duration-500"
            title={`High: ${riskDistribution.highPct}%`}
          />
          <div
            style={{ width: `${riskDistribution.criticalPct}%` }}
            className="bg-[#1E293B] h-full transition-all duration-500"
            title={`Critical: ${riskDistribution.criticalPct}%`}
          />
        </div>

        {/* Plain Legend Below */}
        <div className="flex flex-wrap items-center gap-6 pt-1 text-xs text-slate-600 font-sans">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#4A7C7C]" />
            <span>Normal {riskDistribution.normalPct}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#C9A227]" />
            <span>Warning {riskDistribution.warningPct}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#94A3B8]" />
            <span>High {riskDistribution.highPct}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#1E293B]" />
            <span>Critical {riskDistribution.criticalPct}%</span>
          </div>
        </div>
      </div>

      {/* ── 4. Compound Anomaly Correlation Card (Soft light gray, rounded-[28px]) ── */}
      {criticalAnomaly && (
        <div className="bg-slate-50/70 border border-slate-200/80 rounded-[28px] p-6 shadow-[0_2px_14px_rgba(0,0,0,0.03)] transition-all font-sans">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-red-100 text-red-800 border border-red-200 uppercase">
                  Compound Anomaly Correlation
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Bay 3 • Correlation Score: <strong>{(criticalAnomaly.correlationScore * 100).toFixed(0)}%</strong>
                </span>
              </div>
              <h2 className="text-base font-bold text-slate-900 font-heading">
                {criticalAnomaly.title}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              {/* Primary CTA: Reserved Orange */}
              <Button
                variant="primary"
                size="sm"
                onClick={() => approveRecommendation()}
              >
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                Approve Recommended Mitigation
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-4 text-xs">
            {/* Plain-Language AI Explanation */}
            <div className="lg:col-span-2 space-y-2">
              <div className="text-[11px] font-mono font-semibold uppercase text-slate-500 flex items-center gap-1.5">
                <span>NOVA Cross-Unit Correlation Explanation</span>
              </div>
              <p className="text-slate-800 leading-relaxed bg-white p-5 rounded-2xl border border-slate-200/80 font-sans shadow-2xs text-[13px]">
                {criticalAnomaly.novaExplanation}
              </p>
            </div>

            {/* Correlated Signals Column */}
            <div className="space-y-1.5">
              <div className="text-[11px] font-mono font-semibold uppercase text-slate-500">
                Correlated Signal Deviations
              </div>
              <div className="space-y-2">
                {criticalAnomaly.signals.map((sig, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-white border border-slate-200/80 flex items-center justify-between text-xs font-mono shadow-2xs"
                  >
                    <span className="text-slate-700">{sig.name}</span>
                    <span className="font-bold text-red-600 font-mono">{sig.value} (▲)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 5. Main Two-Column Layout: Top Risk Equipment + Live Alert Stream ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Top Risk Equipment Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-[28px] border border-slate-200/80 p-6 shadow-[0_2px_14px_rgba(0,0,0,0.03)] font-sans">
            <div className="flex items-start justify-between pb-4 border-b border-slate-100 mb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 font-heading tracking-tight">
                  Top Risk Equipment Items
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Ranked by compound risk score & real-time sensor divergence
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/equipment')}
              >
                View All ({equipmentList.length})
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm font-sans">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-subheading text-slate-500 uppercase tracking-wider bg-slate-50/50">
                    <th className="py-3 px-3.5 font-semibold">Equipment</th>
                    <th className="py-3 px-3.5 font-semibold">Bay</th>
                    <th className="py-3 px-3.5 font-semibold">Status</th>
                    <th className="py-3 px-3.5 font-semibold">Risk Tier</th>
                    <th className="py-3 px-3.5 font-semibold">Key Telemetry</th>
                    <th className="py-3 px-3.5 text-right font-semibold">Actions</th>
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
                        <td className="py-3.5 px-3.5">
                          <div className="font-subheading font-bold text-slate-900 text-sm">
                            {item.tag}
                          </div>
                          <div className="text-xs text-slate-600 mt-0.5">{item.name}</div>
                        </td>
                        <td className="py-3.5 px-3.5 font-subheading text-xs text-slate-700 font-medium">
                          {item.bayId}
                        </td>
                        <td className="py-3.5 px-3.5">
                          <StatusBadge status={item.status} />
                        </td>
                        <td className="py-3.5 px-3.5">
                          <RiskBadge tier={tier} score={item.riskScore} />
                        </td>
                        <td className="py-3.5 px-3.5 font-mono text-xs text-slate-800">
                          {item.telemetry.temperature !== undefined && (
                            <div className="font-bold">{item.telemetry.temperature.toFixed(1)}°C</div>
                          )}
                          {item.telemetry.vibration !== undefined && (
                            <div className="text-[11px] text-slate-500 font-normal">
                              {item.telemetry.vibration.toFixed(2)} mm/s
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-3.5 text-right">
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
                              className="text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-sans text-xs"
                              onClick={() => handleAskNova(item.tag)}
                              title="Ask NOVA Copilot"
                            >
                              Query
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Col: Live Alert Stream (Reference image card shape) */}
        <div className="space-y-4">
          <div className="bg-slate-50/70 rounded-[28px] border border-slate-200/80 p-6 shadow-[0_2px_14px_rgba(0,0,0,0.03)] font-sans">
            <div className="flex items-start justify-between pb-3 border-b border-slate-200 mb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 font-heading tracking-tight">
                  Live Alert Stream
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Real-time predictive alarms
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/alerts')}
              >
                All Alerts
              </Button>
            </div>

            <div className="space-y-3">
              {activeAlerts.slice(0, 4).map((alert) => (
                <div
                  key={alert.id}
                  onClick={() => handleInspectEquipment(alert.equipmentId)}
                  className="p-4 rounded-2xl border border-slate-200/90 bg-white hover:border-slate-300 hover:shadow-xs transition-all cursor-pointer space-y-1.5 shadow-2xs"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <AlertSeverityBadge severity={alert.severity} />
                      <span className="font-mono font-bold text-xs text-slate-900">
                        {alert.equipmentTag}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400">
                      {alert.timestamp}
                    </span>
                  </div>

                  <p className="text-xs text-slate-800 line-clamp-2 leading-relaxed font-sans font-medium">
                    {alert.title}
                  </p>

                  <div className="text-[11px] font-mono text-slate-500 pt-1 flex items-center justify-between">
                    <span>{alert.bayId}</span>
                    <span className="text-slate-700 font-semibold flex items-center gap-0.5">
                      Inspect <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CommandCenterPage
