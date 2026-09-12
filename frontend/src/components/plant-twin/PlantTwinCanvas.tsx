import React, { Suspense, useState, useMemo } from 'react'
import * as THREE from 'three'
import { Canvas } from '@react-three/fiber'
import { PlantScene } from './PlantScene'
import { TwinCamera } from './camera/TwinCamera'
import { EquipmentDrawer } from './drawer/EquipmentDrawer'
import { useTwinStore } from './store/useTwinStore'
import {
  Search,
  RotateCcw,
  ShieldCheck,
  Zap,
  Activity,
  Flame,
  Layers,
} from 'lucide-react'
import { getRiskState } from './utils/riskUtils'
import { RiskTier } from './types'

import { useRealtimeStore } from '../../stores/useRealtimeStore'

interface PlantTwinCanvasProps {
  onToggleView?: (view: '2D' | '3D') => void
  currentView?: '2D' | '3D'
}

export const PlantTwinCanvas: React.FC<PlantTwinCanvasProps> = ({
  onToggleView,
  currentView = '3D',
}) => {
  const bays = useTwinStore((s) => s.bays)
  const baseEquipmentList = useTwinStore((s) => s.equipmentList)
  const realtimeEquipment = useRealtimeStore((s) => s.equipment)
  const throughputRate = useRealtimeStore((s) => s.throughputRate)
  const powerConsumptionMw = useRealtimeStore((s) => s.powerConsumptionMw)
  const co2EmissionsRate = useRealtimeStore((s) => s.co2EmissionsRate)
  const safetyStatus = useRealtimeStore((s) => s.safetyStatus)
  const fetchLivePlantData = useRealtimeStore((s) => s.fetchLivePlantData)

  const selectedBayId = useTwinStore((s) => s.selectedBayId)
  const selectedEquipmentId = useTwinStore((s) => s.selectedEquipmentId)
  const selectBay = useTwinStore((s) => s.selectBay)
  const selectEquipment = useTwinStore((s) => s.selectEquipment)
  const resetToOverview = useTwinStore((s) => s.resetToOverview)

  const [searchQuery, setSearchQuery] = useState('')
  const [activeRiskFilter, setActiveRiskFilter] = useState<RiskTier | 'ALL'>('ALL')

  // Auto-fetch live plant state on mount
  React.useEffect(() => {
    fetchLivePlantData()
  }, [fetchLivePlantData])

  // Merge spatial 3D coordinates with live backend equipment state
  const equipmentList = useMemo(() => {
    return baseEquipmentList.map((item) => {
      const live = realtimeEquipment[item.id]
      if (!live) return item
      return {
        ...item,
        status: live.status,
        riskScore: live.riskScore,
        anomalyDetected: live.anomalyDetected,
        telemetry: { ...item.telemetry, ...live.telemetry },
        activeAlerts: live.activeAlerts,
      }
    })
  }, [baseEquipmentList, realtimeEquipment])

  const selectedBay = useMemo(
    () => bays.find((b) => b.id === selectedBayId),
    [bays, selectedBayId]
  )

  // Search matches filtered by risk
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return []
    const q = searchQuery.toLowerCase()
    return equipmentList.filter((e) => {
      const matchText = e.tag.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)
      if (activeRiskFilter === 'ALL') return matchText
      return matchText && getRiskState(e) === activeRiskFilter
    })
  }, [equipmentList, searchQuery, activeRiskFilter])

  return (
    <div className="relative w-full h-full min-h-[680px] bg-slate-100 overflow-hidden font-sans select-none flex flex-col">
      {/* ─── TOP CONTROL & TELEMETRY BAR ─── */}
      <div className="z-20 bg-white border-b border-slate-200 text-slate-800 px-4 py-2 flex flex-wrap items-center justify-between gap-4 shadow-2xs">
        {/* Plant Twin Header & Global KPIs */}
        <div className="flex items-center gap-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-900 tracking-wide flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-orange-500" />
                Petrochemical Complex — 3D Live Twin
              </span>
              <span className="flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                ONLINE
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono">
              Real-time Spatial Intelligence & Predictive Risk Telemetry
            </p>
          </div>

          {/* KPI Badges */}
          <div className="hidden lg:flex items-center gap-2.5 font-mono text-xs border-l border-slate-200 pl-4">
            <div className="px-2.5 py-1 rounded bg-slate-50 border border-slate-200 flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-slate-500 text-[10px]">THROUGHPUT</span>
              <span className="font-bold text-slate-900">{throughputRate.toLocaleString()} t/h</span>
            </div>
            <div className="px-2.5 py-1 rounded bg-slate-50 border border-slate-200 flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-slate-500 text-[10px]">POWER</span>
              <span className="font-bold text-slate-900">{powerConsumptionMw} MW</span>
            </div>
            <div className="px-2.5 py-1 rounded bg-slate-50 border border-slate-200 flex items-center gap-2">
              <Flame className="w-3.5 h-3.5 text-orange-500" />
              <span className="text-slate-500 text-[10px]">CO₂</span>
              <span className="font-bold text-slate-900">{co2EmissionsRate} t/h</span>
            </div>
            <div className="px-2.5 py-1 rounded bg-slate-50 border border-slate-200 flex items-center gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-slate-500 text-[10px]">SAFETY</span>
              <span className={`font-bold ${safetyStatus === 'Alert' ? 'text-red-700' : safetyStatus === 'Warning' ? 'text-amber-700' : 'text-emerald-700'}`}>
                {safetyStatus}
              </span>
            </div>
          </div>
        </div>

        {/* Right Controls: Search, 2D/3D Toggle */}
        <div className="flex items-center gap-3">
          {/* Search Box */}
          <div className="relative">
            <div className="flex items-center bg-slate-50 border border-slate-300 rounded-md px-2.5 py-1.5 focus-within:border-orange-500 transition-colors w-48 sm:w-60">
              <Search className="w-3.5 h-3.5 text-slate-400 mr-2 shrink-0" />
              <input
                type="text"
                placeholder="Search equipment or tag..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent border-0 text-xs text-slate-900 placeholder-slate-400 focus:outline-none w-full font-mono"
              />
            </div>

            {/* Search Dropdown */}
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-xl max-h-56 overflow-y-auto z-50">
                {searchResults.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      selectEquipment(item.id)
                      setSearchQuery('')
                    }}
                    className="w-full text-left px-3 py-2 text-xs hover:bg-orange-50/50 border-b last:border-0 border-slate-100 flex items-center justify-between cursor-pointer"
                  >
                    <div>
                      <span className="font-mono font-bold text-orange-600 mr-2">
                        {item.tag}
                      </span>
                      <span className="text-slate-700">{item.name}</span>
                    </div>
                    <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                      {item.bayId}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 2D / 3D View Switcher */}
          {onToggleView && (
            <div className="flex items-center bg-slate-100 p-0.5 rounded-md border border-slate-200 text-xs font-mono">
              <button
                onClick={() => onToggleView('2D')}
                className={`px-3 py-1 rounded transition-colors cursor-pointer ${
                  currentView === '2D'
                    ? 'bg-white text-slate-900 font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                2D View
              </button>
              <button
                onClick={() => onToggleView('3D')}
                className={`px-3 py-1 rounded transition-colors cursor-pointer ${
                  currentView === '3D'
                    ? 'bg-orange-500 text-white font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                3D View
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ─── SECONDARY NAVIGATION: 6 BAYS QUICK STRIP ─── */}
      <div className="z-10 bg-slate-50/90 border-b border-slate-200 px-4 py-1.5 flex items-center justify-between overflow-x-auto gap-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mr-2 hidden sm:inline">
            Plant Bays:
          </span>
          {bays.map((bay) => {
            const isSelected = bay.id === selectedBayId
            return (
              <button
                key={bay.id}
                onClick={() => selectBay(bay.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-white text-slate-900 border-2 font-bold shadow-xs'
                    : 'bg-white/60 hover:bg-white text-slate-600 border border-slate-200'
                }`}
                style={{
                  borderColor: isSelected ? bay.colorTheme : '#E2E8F0',
                }}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: bay.colorTheme }}
                />
                <span>{bay.code}</span>
              </button>
            )
          })}
        </div>

        {/* Back to Overview Fly-out button */}
        {(selectedBayId || selectedEquipmentId) && (
          <button
            onClick={resetToOverview}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-orange-50 hover:bg-orange-100 text-orange-800 border border-orange-200 text-xs font-mono font-semibold transition-all shrink-0 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Back to Overview</span>
          </button>
        )}
      </div>

      {/* ─── 3D WEBGL CANVAS ─── */}
      <div className="flex-1 w-full h-full relative cursor-grab active:cursor-grabbing">
        <Canvas
          shadows
          camera={{
            position: [0, 115, 130],
            fov: 42,
            near: 0.5,
            far: 1000,
          }}
          gl={{
            antialias: true,
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: 1.15,
          }}
        >
          {/* Light Neutral Fog / Background */}
          <color attach="background" args={['#F1F5F9']} />

          {/* Clean Industrial Ambient & Daylight Sun */}
          <ambientLight intensity={0.9} color="#FFFFFF" />
          <directionalLight
            position={[80, 140, 70]}
            intensity={1.8}
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-bias={-0.0001}
          />
          <directionalLight position={[-80, 60, -60]} intensity={0.5} color="#CBD5E1" />

          {/* Smooth Lerping Camera */}
          <TwinCamera />

          {/* Procedural 3D Plant Layout & Equipment */}
          <Suspense fallback={null}>
            <PlantScene />
          </Suspense>
        </Canvas>

        {/* ─── IN-CANVAS HUD OVERLAYS ─── */}
        {/* Floating Quick Legend / Filter controls at bottom left */}
        <div className="absolute bottom-4 left-4 z-10 bg-white/95 backdrop-blur-md border border-slate-200 rounded-lg p-3 text-xs text-slate-700 font-mono shadow-md space-y-2 pointer-events-auto">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">
              Filter by Risk
            </span>
            {activeRiskFilter !== 'ALL' && (
              <button
                onClick={() => setActiveRiskFilter('ALL')}
                className="text-[10px] text-orange-600 hover:underline cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const).map((tier) => (
              <button
                key={tier}
                onClick={() =>
                  setActiveRiskFilter(activeRiskFilter === tier ? 'ALL' : tier)
                }
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] transition-all cursor-pointer ${
                  activeRiskFilter === tier
                    ? 'bg-slate-800 text-white font-bold'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    tier === 'LOW'
                      ? 'bg-emerald-500'
                      : tier === 'MEDIUM'
                      ? 'bg-amber-500'
                      : tier === 'HIGH'
                      ? 'bg-orange-600'
                      : 'bg-red-500 animate-pulse'
                  }`}
                />
                <span className="capitalize">{tier.toLowerCase()}</span>
              </button>
            ))}
          </div>
          <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-100">
            • Click any bay to fly-in • Click equipment to inspect
          </div>
        </div>

        {/* Selected Bay Bottom Banner */}
        {selectedBay && (
          <div className="absolute bottom-4 right-4 z-10 bg-white/95 backdrop-blur-md border border-slate-200 rounded-lg px-4 py-3 shadow-lg max-w-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: selectedBay.colorTheme }}
                  />
                  <span className="font-bold text-sm text-slate-900">
                    {selectedBay.code} — {selectedBay.name}
                  </span>
                </div>
                {selectedBay.subtitle && (
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {selectedBay.subtitle}
                  </p>
                )}
              </div>
              <button
                onClick={resetToOverview}
                className="text-xs font-mono text-orange-600 hover:text-orange-700 underline underline-offset-2 shrink-0 cursor-pointer"
              >
                Overview ↑
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ─── 2D EQUIPMENT DETAIL DRAWER ─── */}
      <EquipmentDrawer />
    </div>
  )
}
