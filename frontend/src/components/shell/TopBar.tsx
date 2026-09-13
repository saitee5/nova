import React, { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import { useRealtimeStore } from '../../stores/useRealtimeStore'

export const TopBar: React.FC = () => {
  const [timeStr, setTimeStr] = useState('')
  const toggleCopilot = useRealtimeStore((s) => s.toggleCopilot)
  const isCopilotOpen = useRealtimeStore((s) => s.isCopilotOpen)

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setTimeStr(
        now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
        ' UTC'
      )
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header className="h-14 bg-white border-b border-slate-200 px-5 flex items-center justify-between z-20 shrink-0 select-none">
      {/* Left: Plant Unit & Live status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
          <span className="font-heading text-sm text-slate-900 tracking-tight">
            Petrochemical Complex
          </span>
        </div>
      </div>

      {/* Right: Clock & Ask NOVA CTA */}
      <div className="flex items-center gap-3 font-mono text-xs">
        {/* Clock */}
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-slate-700">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-[11px] font-mono font-medium">{timeStr || '12:00:00 UTC'}</span>
        </div>

        {/* Global Copilot Launcher CTA - Clean rounded pill styling */}
        <button
          onClick={toggleCopilot}
          className={`flex items-center gap-2 px-4 py-1.5 rounded-full font-sans text-xs font-bold transition-all cursor-pointer ${
            isCopilotOpen
              ? 'bg-orange-600 text-white border border-orange-700 shadow-xs'
              : 'bg-[#1E293B] hover:bg-slate-800 text-white border border-slate-800 shadow-xs'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
          <span>NOVA Copilot</span>
        </button>
      </div>
    </header>
  )
}
