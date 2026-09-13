import React, { useState } from 'react'
import {
  History,
  Search,
  CheckCircle2,
  FileText,
  Database,
  Layers,
  Cpu,
  ShieldCheck,
} from 'lucide-react'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { StatCard } from '../components/common/MetricCard'
import { useRealtimeStore } from '../stores/useRealtimeStore'

interface HistoricalIncidentRecord {
  id: string
  title: string
  date: string
  equipmentTag: string
  similarityPercent: number
  summary: string
  rootCause: string
  actionTaken: string
  resolutionTimeHours: number
  signalComparison: {
    signal: string
    unit: string
    currentIncident: number
    historicalIncident: number
    variancePercent: number
  }[]
}

const HISTORICAL_INCIDENTS: HistoricalIncidentRecord[] = [
  {
    id: 'INC-2024-01-14',
    title: 'Furnace F-301A Localized Coking & Pass Impingement',
    date: 'January 14, 2024',
    equipmentTag: 'F-301A',
    similarityPercent: 94,
    summary:
      'Pass 4 radiant tube skin temperature peaked at 1,058°C with concurrent burner B-102 draft damper hunting.',
    rootCause:
      'Heavy coking inside radiant coil pass 4 due to feed naphtha boiling range shift, causing localized velocity drop.',
    actionTaken:
      'Injected 12% dilution steam boost to pass 4, trimmed fuel gas pressure to 2.4 bar, and initiated hot steam/air decoke procedure.',
    resolutionTimeHours: 4.5,
    signalComparison: [
      {
        signal: 'Pass 4 Radiant Skin Temp',
        unit: '°C',
        currentIncident: 1064.2,
        historicalIncident: 1058.0,
        variancePercent: 0.6,
      },
      {
        signal: 'Dilution Steam Flow Rate',
        unit: 'kg/h',
        currentIncident: 1420.0,
        historicalIncident: 1450.0,
        variancePercent: -2.1,
      },
      {
        signal: 'Burner Acoustic RMS Vibration',
        unit: 'mm/s',
        currentIncident: 5.6,
        historicalIncident: 5.4,
        variancePercent: 3.7,
      },
      {
        signal: 'Convection Damper Position Bias',
        unit: '%',
        currentIncident: 6.0,
        historicalIncident: 6.5,
        variancePercent: -7.6,
      },
    ],
  },
  {
    id: 'INC-2023-11-02',
    title: 'Cracked Gas Compressor K-301 Stage 3 Vibration Trip',
    date: 'November 2, 2023',
    equipmentTag: 'K-301',
    similarityPercent: 88,
    summary:
      'High quench effluent temperature (415°C) led to liquid condensation carryover, generating 6.2 mm/s radial displacement on bearing DE.',
    rootCause:
      'Quench water circulating pump cavitation starved quench tower tray 4 spray nozzles.',
    actionTaken:
      'Swapped to standby quench booster pump P-302B, purged suction separator vessel, and increased demister wash flow rate.',
    resolutionTimeHours: 2.0,
    signalComparison: [
      {
        signal: 'Radial Shaft Vibration',
        unit: 'mm/s',
        currentIncident: 6.8,
        historicalIncident: 6.2,
        variancePercent: 9.6,
      },
      {
        signal: 'Inlet Suction Temperature',
        unit: '°C',
        currentIncident: 88.4,
        historicalIncident: 84.0,
        variancePercent: 5.2,
      },
      {
        signal: 'Discharge Pressure',
        unit: 'bar',
        currentIncident: 32.5,
        historicalIncident: 31.8,
        variancePercent: 2.2,
      },
    ],
  },
  {
    id: 'INC-2023-04-10',
    title: 'Furnace F-301 Burner Tip Flame Impingement Replacement',
    date: 'April 10, 2023',
    equipmentTag: 'F-301A',
    similarityPercent: 79,
    summary:
      'Excess draft oscillation led to burner flame lift-off and uneven temperature distribution along bottom coil passes.',
    rootCause: 'Fuel gas tail gas blend density fluctuation without heating value compensation.',
    actionTaken: 'Enriched fuel gas with methane supply and replaced ceramic burner tip.',
    resolutionTimeHours: 6.0,
    signalComparison: [
      {
        signal: 'Radiant Coil Skin Temp',
        unit: '°C',
        currentIncident: 1064.2,
        historicalIncident: 1042.0,
        variancePercent: 2.1,
      },
      {
        signal: 'Excess O2 in Flue Gas',
        unit: '%',
        currentIncident: 1.1,
        historicalIncident: 1.4,
        variancePercent: -21.4,
      },
    ],
  },
]

export const HistoryPage: React.FC = () => {
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(
    HISTORICAL_INCIDENTS[0].id
  )
  const [searchQuery, setSearchQuery] = useState('')
  const openCopilot = useRealtimeStore((s) => s.openCopilot)
  const approveRecommendation = useRealtimeStore((s) => s.approveRecommendation)

  const currentIncident =
    HISTORICAL_INCIDENTS.find((inc) => inc.id === selectedIncidentId) ||
    HISTORICAL_INCIDENTS[0]

  const handleAskNova = () => {
    openCopilot({
      tag: currentIncident.equipmentTag,
      prompt: `Compare current incident on ${currentIncident.equipmentTag} with historical match ${currentIncident.id} (${currentIncident.similarityPercent}% similarity). Explain why the historical action succeeded and whether we should apply it now.`,
    })
  }

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12 font-sans">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <History className="w-5 h-5 text-slate-700" />
            Historical Intelligence & Incident Retrieval
          </h1>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Vector search across Qdrant memory for past plant deviations and proven mitigations
          </p>
        </div>
      </div>

      {/* ── Top Stat Cards (Matsetu Style) ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          variant="navy"
          label="Historical Records"
          value="9.2K+"
          unit="Incidents"
          icon={<Database className="w-5 h-5 text-white" />}
          subtext="Indexed in Qdrant DB"
        />
        <StatCard
          variant="teal"
          label="Top Vector Match"
          value={`${currentIncident.similarityPercent}%`}
          unit="Cosine"
          icon={<ShieldCheck className="w-5 h-5 text-white" />}
          trendDelta="High confidence"
          trendDirection="up"
          subtext={currentIncident.id}
        />
        <StatCard
          variant="gray"
          label="Average Mitigation Time"
          value="2.8h"
          unit="MTTR"
          icon={<Layers className="w-5 h-5 text-slate-900" />}
          subtext="Resolution duration"
        />
        <StatCard
          variant="gold"
          label="Correlated Equipment"
          value={currentIncident.equipmentTag}
          unit="Target"
          icon={<Cpu className="w-5 h-5 text-white" />}
          subtext="Direct procedure match"
        />
      </div>

      {/* ── Semantic Search Input Bar ── */}
      <div className="bg-white p-3 rounded-lg border border-slate-200 flex items-center gap-3">
        <div className="flex-1 flex items-center bg-slate-50 border border-slate-300 rounded-md px-3 py-2 text-xs">
          <Search className="w-4 h-4 text-slate-400 mr-2 shrink-0" />
          <input
            type="text"
            placeholder="Search symptoms or semantic query (e.g. 'radiant coil skin temp hotspot with burner resonance')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-0 text-slate-900 placeholder-slate-400 focus:outline-none w-full font-sans"
          />
        </div>
        <Button variant="secondary" size="md">
          <span>Search</span>
        </Button>
      </div>

      {/* ── Two-Pane Layout: Incident Matches (Left) + Detailed Comparison (Right) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left List: Similar Incident Cards (5 cols) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="text-[11px] font-mono text-slate-500 font-semibold uppercase px-1">
            Top Matches (Similarity &gt; 75%)
          </div>

          {HISTORICAL_INCIDENTS.map((inc) => {
            const isSelected = inc.id === currentIncident.id
            const borderAccent =
              inc.similarityPercent >= 90
                ? 'border-l-emerald-600'
                : inc.similarityPercent >= 80
                ? 'border-l-teal-600'
                : 'border-l-slate-400'

            return (
              <div
                key={inc.id}
                onClick={() => setSelectedIncidentId(inc.id)}
                className={`p-3.5 rounded-lg border border-slate-200 transition-all cursor-pointer space-y-2 relative border-l-4 ${borderAccent} ${
                  isSelected
                    ? 'bg-slate-50/90 ring-1 ring-slate-300'
                    : 'bg-white hover:bg-slate-50/50 hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                    {inc.id}
                  </span>
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
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
        <div className="lg:col-span-7 space-y-4">
          <Card>
            {/* Header */}
            <div className="pb-4 border-b border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">

                  <span className="text-xs font-mono text-slate-500">
                    {currentIncident.date}
                  </span>
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

            {/* ── Signal Comparison Table (Clean Matsetu Tabular Styling) ── */}
            <div className="py-4 space-y-2 border-b border-slate-200">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold font-mono text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-slate-600" />
                  <span>Current Live Telemetry vs. Historical Incident Signals</span>
                </h3>
                <span className="text-[10px] font-mono text-slate-500">
                  Signal Variance
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead>
                    <tr className="bg-slate-50 text-[11px] font-mono text-slate-500 uppercase border-b border-slate-200">
                      <th className="py-3 px-3.5 font-semibold">Signal Name</th>
                      <th className="py-3 px-3.5 font-semibold text-slate-900">Current Live Event</th>
                      <th className="py-3 px-3.5 font-semibold text-slate-700">Historical Match ({currentIncident.id})</th>
                      <th className="py-3 px-3.5 text-right font-semibold">Divergence (%)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-xs">
                    {currentIncident.signalComparison.map((row, idx) => {
                      const absVar = Math.abs(row.variancePercent)
                      const varColor =
                        absVar > 15
                          ? 'text-red-600 bg-red-50/50'
                          : absVar > 5
                          ? 'text-amber-600 bg-amber-50/50'
                          : 'text-slate-600 bg-slate-50/50'

                      return (
                        <tr key={idx} className="hover:bg-slate-50/70 transition-colors">
                          <td className="py-2.5 px-3.5 font-sans font-medium text-slate-900">
                            {row.signal}
                          </td>
                          <td className="py-2.5 px-3.5 font-bold text-slate-900">
                            {row.currentIncident} {row.unit}
                          </td>
                          <td className="py-2.5 px-3.5 text-slate-600">
                            {row.historicalIncident} {row.unit}
                          </td>
                          <td className="py-2.5 px-3.5 text-right font-bold">
                            <span className={`px-2 py-0.5 rounded ${varColor}`}>
                              {row.variancePercent > 0 ? `+${row.variancePercent}%` : `${row.variancePercent}%`}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

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
                <span className="font-mono font-bold text-[11px] text-slate-700 uppercase">
                  Successful Resolution Action Taken:
                </span>
                <p className="text-slate-800 bg-slate-50 p-2.5 rounded border border-slate-200 font-sans leading-relaxed">
                  {currentIncident.actionTaken}
                </p>
                <span className="text-[10px] font-mono text-slate-400 block pt-0.5">
                  Resolution time: {currentIncident.resolutionTimeHours} hours to safe normal
                </span>
              </div>
            </div>

            {/* Actions CTA: Only ONE Primary CTA in Orange */}
            <div className="pt-4 flex flex-wrap items-center justify-between gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={handleAskNova}
              >
                Apply Historical Procedure
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={() => approveRecommendation()}
              >
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                Approve & Execute Proven Mitigation
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default HistoryPage
