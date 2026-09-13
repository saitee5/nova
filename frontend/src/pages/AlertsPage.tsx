import React, { useState, useMemo } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  ArrowRight,
  Search,
  Bell,
  AlertOctagon,
} from 'lucide-react'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { StatCard } from '../components/common/MetricCard'
import {
  AlertSeverityBadge,
  AlertStatusBadge,
} from '../components/common/Badge'
import { useRealtimeStore, AlertSeverity } from '../stores/useRealtimeStore'
import { useNavigate } from 'react-router-dom'

export const AlertsPage: React.FC = () => {
  const navigate = useNavigate()
  const alerts = useRealtimeStore((s) => s.alerts)
  const updateAlertStatus = useRealtimeStore((s) => s.updateAlertStatus)
  const selectEquipment = useRealtimeStore((s) => s.selectEquipment)
  const openCopilot = useRealtimeStore((s) => s.openCopilot)
  const approveRecommendation = useRealtimeStore((s) => s.approveRecommendation)

  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | 'ALL'>('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedAlertId, setSelectedAlertId] = useState<string>(alerts[0]?.id || '')

  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false
      if (statusFilter === 'ACTIVE' && a.status === 'RESOLVED') return false
      if (statusFilter !== 'ALL' && statusFilter !== 'ACTIVE' && a.status !== statusFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        return (
          a.title.toLowerCase().includes(q) ||
          a.equipmentTag.toLowerCase().includes(q) ||
          a.message.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [alerts, severityFilter, statusFilter, searchQuery])

  const currentAlert = alerts.find((a) => a.id === selectedAlertId) || filteredAlerts[0]

  const handleInspectInTwin = (equipmentId: string) => {
    selectEquipment(equipmentId)
    navigate('/digital-twin')
  }

  const handleAskNova = (tag: string, alertTitle: string) => {
    openCopilot({
      tag,
      prompt: `Explain root cause and mitigation steps for alert: "${alertTitle}" on ${tag}.`,
    })
  }

  const activeAlertsCount = alerts.filter((a) => a.status !== 'RESOLVED').length
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status !== 'RESOLVED').length
  const warningCount = alerts.filter((a) => (a.severity === 'high' || a.severity === 'medium') && a.status !== 'RESOLVED').length

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12 font-sans">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-slate-700" />
            Alerts & Anomaly Incident Manager
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Real-time multi-variate process alarms with root-cause signal deltas
          </p>
        </div>
      </div>

      {/* ── Top Stat Cards (Matsetu Style) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          variant="navy"
          label="Total Active Alarms"
          value={activeAlertsCount}
          unit="Events"
          icon={<Bell className="w-5 h-5 text-white" />}
          subtext="Plant-wide telemetry"
        />
        <StatCard
          variant="gold"
          label="Critical Requiring Review"
          value={criticalCount}
          unit="Urgent"
          icon={<AlertOctagon className="w-5 h-5 text-slate-950" />}
          trendDelta="Action required"
          trendDirection="up"
          subtext="Safety interlock range"
        />
        <StatCard
          variant="gray"
          label="Warning / Medium Level"
          value={warningCount}
          unit="Anomalies"
          icon={<AlertTriangle className="w-5 h-5 text-slate-900" />}
          subtext="Predictive deviation"
        />
        <StatCard
          variant="teal"
          label="Monitored Subsystems"
          value="6/6"
          unit="Bays"
          icon={<Cpu className="w-5 h-5 text-white" />}
          subtext="100% data ingestion"
        />
      </div>

      {/* ── Filter Toolbar ── */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-mono text-slate-500 font-semibold uppercase mr-1">
              Status:
            </span>
            {(['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-md text-xs font-mono uppercase transition-colors cursor-pointer ${
                  statusFilter === st
                    ? 'bg-slate-900 text-white font-bold'
                    : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Severity Pills */}
          <div className="flex items-center gap-1.5 border-l border-slate-200 pl-4">
            <span className="text-[11px] font-mono text-slate-500 font-semibold uppercase mr-1">
              Severity:
            </span>
            {(['ALL', 'critical', 'high', 'medium', 'low'] as const).map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev as any)}
                className={`px-2.5 py-1 rounded-md text-xs font-mono uppercase transition-colors cursor-pointer ${
                  severityFilter === sev
                    ? 'bg-orange-500 text-white font-bold border border-orange-600'
                    : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 w-56">
            <Search className="w-3.5 h-3.5 text-slate-400 mr-1.5 shrink-0" />
            <input
              type="text"
              placeholder="Search tag or summary..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-0 text-xs text-slate-900 placeholder-slate-400 focus:outline-none w-full font-sans"
            />
          </div>
        </div>
      </div>

      {/* ── Main Two-Pane Layout: List (Left) + Detail (Right) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left List (5 cols) */}
        <div className="lg:col-span-5 space-y-3 max-h-[750px] overflow-y-auto pr-1">
          {filteredAlerts.length === 0 ? (
            <div className="p-8 text-center text-slate-500 bg-white rounded-lg border border-slate-200">
              No alerts match the active filter criteria.
            </div>
          ) : (
            filteredAlerts.map((alt) => {
              const isSelected = alt.id === currentAlert?.id
              const severityBorderColor =
                alt.severity === 'critical'
                  ? 'border-l-red-600'
                  : alt.severity === 'high'
                  ? 'border-l-orange-500'
                  : alt.severity === 'medium'
                  ? 'border-l-amber-500'
                  : 'border-l-emerald-500'

              return (
                <div
                  key={alt.id}
                  onClick={() => setSelectedAlertId(alt.id)}
                  className={`p-3.5 rounded-lg border border-slate-200 transition-all cursor-pointer space-y-2 relative border-l-4 ${severityBorderColor} ${
                    isSelected
                      ? 'bg-slate-50/90 ring-1 ring-slate-300'
                      : 'bg-white hover:bg-slate-50/50 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <AlertSeverityBadge severity={alt.severity} />
                      <span className="font-mono font-bold text-xs text-slate-900">
                        {alt.equipmentTag}
                      </span>
                    </div>
                    <AlertStatusBadge status={alt.status} />
                  </div>

                  <h3 className="text-xs font-bold text-slate-900 leading-snug">
                    {alt.title}
                  </h3>

                  <p className="text-[11px] text-slate-600 line-clamp-2">
                    {alt.message}
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-100">
                    <span>{alt.bayId}</span>
                    <span>{alt.timestamp}</span>
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Right Detail View (7 cols) */}
        {currentAlert ? (
          <div className="lg:col-span-7 space-y-4">
            <Card>
              {/* Detail Header */}
              <div className="pb-4 border-b border-slate-200 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertSeverityBadge severity={currentAlert.severity} />
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                      {currentAlert.equipmentTag}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      {currentAlert.equipmentName}
                    </span>
                  </div>
                  <AlertStatusBadge status={currentAlert.status} />
                </div>

                <h2 className="text-base font-bold text-slate-900">
                  {currentAlert.title}
                </h2>

                <p className="text-xs text-slate-700 leading-relaxed font-sans">
                  {currentAlert.message}
                </p>

                {/* Workflow Status Actions */}
                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <span className="text-[11px] font-mono text-slate-500">Update Status:</span>
                  {(['ACKNOWLEDGED', 'INVESTIGATING', 'MITIGATED', 'RESOLVED'] as const).map(
                    (nextSt) => (
                      <button
                        key={nextSt}
                        onClick={() => updateAlertStatus(currentAlert.id, nextSt)}
                        className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors cursor-pointer ${currentAlert.status === nextSt
                          ? 'bg-slate-800 text-white font-bold'
                          : 'bg-white hover:bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                      >
                        {nextSt}
                      </button>
                    )
                  )}
                </div>
              </div>

              {/* Signal Deltas Table: Highest value demo moment */}
              <div className="py-4 space-y-2 border-b border-slate-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold font-mono text-slate-800 uppercase tracking-wider">
                    Divergent Signal Deltas (Baseline vs Current)
                  </h3>
                  <span className="text-[10px] font-mono text-slate-500">
                    Sampled at {currentAlert.timestamp}
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="bg-slate-50 text-[10px] text-slate-500 uppercase border-b border-slate-200">
                        <th className="py-2 px-3">Telemetry Signal</th>
                        <th className="py-2 px-3">Baseline Nominal</th>
                        <th className="py-2 px-3">Current Value</th>
                        <th className="py-2 px-3 text-right">Delta (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {currentAlert.signalDeltas.map((s, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3 font-medium text-slate-900">
                            {s.signal}
                          </td>
                          <td className="py-2.5 px-3 text-slate-600">
                            {s.baseline} {s.unit}
                          </td>
                          <td className="py-2.5 px-3 font-bold text-slate-900">
                            {s.current} {s.unit}
                          </td>
                          <td className="py-2.5 px-3 text-right font-bold text-red-600">
                            +{s.deltaPercent.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* AI Diagnostic Explanation */}
              <div className="py-4 space-y-2 border-b border-slate-200">
                <div className="text-xs font-bold font-mono text-slate-800 flex items-center gap-1.5 uppercase tracking-wider">
                  <Cpu className="w-4 h-4 text-slate-600" />
                  <span>NOVA Root Cause Reasoning</span>
                </div>
                <p className="text-xs text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-200 leading-relaxed font-sans">
                  {currentAlert.aiExplanation}
                </p>
                <div className="text-[11px] font-mono text-slate-500 flex items-center gap-4 pt-1">
                  <span>
                    Historical Matches in Qdrant: <strong>{currentAlert.historicalMatchCount} incidents</strong>
                  </span>
                  <span>
                    Pre-mitigation Risk Score: <strong>{currentAlert.riskScore}/100</strong>
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => approveRecommendation()}
                  >
                    <CheckCircle2 className="w-4 h-4 mr-1.5" />
                    Approve Mitigation
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      handleAskNova(currentAlert.equipmentTag, currentAlert.title)
                    }
                  >
                    Ask NOVA Detailed Query
                  </Button>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleInspectInTwin(currentAlert.equipmentId)}
                >
                  <span>Fly to 3D Location</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </Card>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default AlertsPage
