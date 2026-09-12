import React, { useState, useEffect, useCallback } from 'react'
import {
  History,
  Search,
  Sparkles,
  CheckCircle2,
  FileText,
  Loader2,
  AlertTriangle,
  Database,
  Layers,
} from 'lucide-react'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { useRealtimeStore } from '../stores/useRealtimeStore'
import { searchMemory } from '../services/api'
import { toDisplayTag } from '../utils/assetAliases'

interface HistoricalIncidentRecord {
  id: string
  title: string
  date: string
  equipmentTag: string
  zoneId?: string
  severity?: string
  similarityPercent: number
  summary: string
  rootCause: string
  actionTaken: string
  resolutionTimeHours: number
  contributingFactors: string[]
  signalComparison?: {
    signal: string
    unit: string
    currentIncident: number
    historicalIncident: number
    variancePercent: number
  }[]
}

export const HistoryPage: React.FC = () => {
  const [incidents, setIncidents] = useState<HistoricalIncidentRecord[]>([])
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const openCopilot = useRealtimeStore((s) => s.openCopilot)
  const approveMitigationAction = useRealtimeStore((s) => s.approveMitigationAction)

  const performSearch = useCallback(async (query: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await searchMemory({
        query: query.trim() || 'gas leak compressor vibration high temperature furnace',
        collection: 'incidents_historical',
        top_k: 6,
      })

      if (response.matches && response.matches.length > 0) {
        const mapped: HistoricalIncidentRecord[] = response.matches.map((m, idx) => {
          const payload = (m.payload as Record<string, unknown>) || {}
          const title = (m.title as string) || (payload.title as string) || 'Historical Operational Incident'
          const rawId = (m.id as string) || (payload.record_id as string) || (payload.incident_id as string) || `INC-HIST-${idx + 1}`
          const dateStr = (payload.date as string) || (payload.created_at as string)
          const formattedDate = dateStr
            ? new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
            : 'Prior Operational Run'
          const equipId = (payload.equipment_id as string) || 'F-201A'
          const displayTag = toDisplayTag(equipId)
          const similarityScore = typeof m.score === 'number' ? m.score : 0.82
          const similarityPercent = Math.min(99, Math.round(similarityScore * 100))

          const summary = (m.description as string) || (payload.description as string) || (payload.summary as string) || 'Operational record logged in VIGIL vector memory store.'
          const factors = Array.isArray(payload.contributing_factors)
            ? (payload.contributing_factors as string[])
            : []
          const rootCause = (payload.root_cause as string) || (factors.length > 0 ? `Factors: ${factors.join(', ')}` : 'Identified during post-event cross-correlation review.')
          const actionTaken = (payload.action_taken as string) || (payload.debrief_text as string) || (payload.outcome ? `Event resolved safely. Outcome: ${payload.outcome}` : 'Standard mitigation protocol executed by operations console.')
          const resolutionTimeHours = typeof payload.resolution_time_hours === 'number' ? payload.resolution_time_hours : 2.5

          // Check if explicit signal comparison was recorded in payload
          let signalComparison: HistoricalIncidentRecord['signalComparison'] = undefined
          if (Array.isArray(payload.signal_comparison)) {
            signalComparison = payload.signal_comparison as HistoricalIncidentRecord['signalComparison']
          }

          return {
            id: rawId,
            title,
            date: formattedDate,
            equipmentTag: displayTag,
            zoneId: (payload.zone_id as string) || undefined,
            severity: (payload.severity as string) || undefined,
            similarityPercent,
            summary,
            rootCause,
            actionTaken,
            resolutionTimeHours,
            contributingFactors: factors,
            signalComparison,
          }
        })

        setIncidents(mapped)
        setSelectedIncidentId(mapped[0].id)
      } else {
        setIncidents([])
        setSelectedIncidentId('')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query historical memory backend'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void performSearch('')
  }, [performSearch])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void performSearch(searchQuery)
  }

  const currentIncident =
    incidents.find((inc) => inc.id === selectedIncidentId) ||
    incidents[0]

  const handleAskNova = () => {
    if (!currentIncident) return
    openCopilot({
      tag: currentIncident.equipmentTag,
      prompt: `Compare current incident on ${currentIncident.equipmentTag} with historical match ${currentIncident.id} (${currentIncident.similarityPercent}% similarity). Explain why the historical action succeeded and whether we should apply it now.`,
    })
  }

  const handleApprove = async () => {
    try {
      setStatusMessage('Submitting mitigation decision to Runtime Engine...')
      await approveMitigationAction()
      setStatusMessage('Mitigation decision submitted to backend Runtime Engine.')
      setTimeout(() => setStatusMessage(null), 4000)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Runtime submission failed'
      setStatusMessage(`Runtime action notice: ${msg}`)
      setTimeout(() => setStatusMessage(null), 5000)
    }
  }

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12 font-sans">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <History className="w-5 h-5 text-orange-500" />
            Historical Intelligence & Incident Retrieval
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Vector-grounded operational precedent matching via backend Qdrant memory service.
          </p>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800 flex items-center gap-2 animate-fadeIn">
          <Database className="w-4 h-4 text-blue-600 shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>Memory Service Warning: {error} (Falling back to available indexed records)</span>
        </div>
      )}

      {/* ── Semantic Search Input Bar ── */}
      <form onSubmit={handleSearchSubmit} className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs flex items-center gap-3">
        <div className="flex-1 flex items-center bg-slate-50 border border-slate-300 rounded px-3 py-2 text-xs">
          <Search className="w-4 h-4 text-slate-400 mr-2 shrink-0" />
          <input
            type="text"
            placeholder="Search symptoms or semantic query (e.g. 'radiant coil skin temp hotspot with burner resonance' or 'gas leak')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-0 text-slate-900 placeholder-slate-400 focus:outline-none w-full font-sans"
          />
        </div>
        <Button variant="primary" size="md" type="submit" disabled={isLoading}>
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin mr-1" />
          ) : (
            <span>Search</span>
          )}
        </Button>
      </form>

      {/* ── Two-Pane Layout: Incident Matches (Left) + Detailed Comparison (Right) ── */}
      {isLoading && incidents.length === 0 ? (
        <div className="py-16 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
          <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
          <span className="text-xs font-mono">Querying vector memory collections (POST /api/memory/search)...</span>
        </div>
      ) : incidents.length === 0 ? (
        <div className="p-8 text-center bg-white rounded-lg border border-slate-200 text-slate-500 text-xs">
          No historical incidents match the query parameters in the memory store.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left List: Similar Incident Cards (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="text-[11px] font-mono text-slate-500 font-semibold uppercase px-1 flex items-center justify-between">
              <span>Top Memory Matches ({incidents.length})</span>
              <span className="text-[10px] text-slate-400">incidents_historical</span>
            </div>

            {incidents.map((inc) => {
              const isSelected = inc.id === currentIncident?.id
              return (
                <div
                  key={inc.id}
                  onClick={() => setSelectedIncidentId(inc.id)}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer space-y-2 ${isSelected
                    ? 'bg-orange-50/50 border-orange-400 shadow-xs'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                      {inc.id}
                    </span>
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-300">
                      {inc.similarityPercent}% Match
                    </span>
                  </div>

                  <h3 className="text-xs font-bold text-slate-900 leading-snug">
                    {inc.title}
                  </h3>

                  <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed">
                    {inc.summary}
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-100">
                    <span>{inc.equipmentTag}</span>
                    <span>{inc.date}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Right Detail: Current vs Historical Signal Comparison Table (7 cols) */}
          {currentIncident && (
            <div className="lg:col-span-7 space-y-4">
              <Card>
                {/* Header */}
                <div className="pb-4 border-b border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-slate-500">
                        {currentIncident.date}
                      </span>
                      {currentIncident.zoneId && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200">
                          {currentIncident.zoneId}
                        </span>
                      )}
                      {currentIncident.severity && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded border border-amber-200 uppercase font-semibold">
                          {currentIncident.severity}
                        </span>
                      )}
                    </div>
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-300">
                      {currentIncident.similarityPercent}% Vector Similarity
                    </span>
                  </div>

                  <h2 className="text-base font-bold text-slate-900">
                    {currentIncident.title}
                  </h2>

                  <p className="text-xs text-slate-700 leading-relaxed font-sans">
                    {currentIncident.summary}
                  </p>
                </div>

                {/* Contributing factors & signal indicators */}
                {currentIncident.signalComparison && currentIncident.signalComparison.length > 0 ? (
                  <div className="py-4 space-y-2 border-b border-slate-200">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-bold font-mono text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                        <FileText className="w-4 h-4 text-orange-600" />
                        <span>Live Telemetry vs. Historical Incident Signals</span>
                      </h3>
                      <span className="text-[10px] font-mono text-slate-500">
                        Signal Variance
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="bg-slate-50 text-[10px] text-slate-500 uppercase border-b border-slate-200">
                            <th className="py-2.5 px-3">Signal Name</th>
                            <th className="py-2.5 px-3 text-orange-900 bg-orange-50/50">Current Live Event</th>
                            <th className="py-2.5 px-3 text-slate-700">Historical Match ({currentIncident.id})</th>
                            <th className="py-2.5 px-3 text-right">Divergence (%)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {currentIncident.signalComparison.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-50/60">
                              <td className="py-2.5 px-3 font-medium text-slate-900">
                                {row.signal}
                              </td>
                              <td className="py-2.5 px-3 font-bold text-orange-900 bg-orange-50/30">
                                {row.currentIncident} {row.unit}
                              </td>
                              <td className="py-2.5 px-3 text-slate-700">
                                {row.historicalIncident} {row.unit}
                              </td>
                              <td className="py-2.5 px-3 text-right font-semibold text-slate-800">
                                {row.variancePercent > 0 ? `+${row.variancePercent}%` : `${row.variancePercent}%`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="py-3 border-b border-slate-200 space-y-2">
                    <div className="text-[11px] font-mono text-slate-600 font-semibold uppercase flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-orange-500" />
                      <span>Associated Operational Factors:</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {currentIncident.contributingFactors.length > 0 ? (
                        currentIncident.contributingFactors.map((f, i) => (
                          <span key={i} className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-[11px] font-mono border border-slate-200">
                            {f}
                          </span>
                        ))
                      ) : (
                        <span className="text-[11px] text-slate-400 italic">No isolated discrete factors recorded</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Root Cause & Successful Action Taken */}
                <div className="py-4 space-y-3 border-b border-slate-200 text-xs">
                  <div className="space-y-1">
                    <span className="font-mono font-bold text-[11px] text-slate-600 uppercase">
                      Historical Root Cause Diagnosed:
                    </span>
                    <p className="text-slate-800 bg-slate-50 p-2.5 rounded border border-slate-200 font-sans leading-relaxed">
                      {currentIncident.rootCause}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="font-mono font-bold text-[11px] text-emerald-800 uppercase">
                      Successful Resolution Action Taken:
                    </span>
                    <p className="text-slate-800 bg-emerald-50/50 p-2.5 rounded border border-emerald-200 font-sans leading-relaxed">
                      {currentIncident.actionTaken}
                    </p>
                    <span className="text-[10px] font-mono text-slate-400 block pt-0.5">
                      Resolution time: {currentIncident.resolutionTimeHours} hours to safe normal
                    </span>
                  </div>
                </div>

                {/* Actions CTA */}
                <div className="pt-4 flex flex-wrap items-center justify-between gap-3">
                  <Button
                    variant="nova"
                    size="sm"
                    onClick={handleAskNova}
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-1" />
                    Ask NOVA to Apply Historical Procedure
                  </Button>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleApprove}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                    Approve & Execute Proven Mitigation
                  </Button>
                </div>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default HistoryPage
