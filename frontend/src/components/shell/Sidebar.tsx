import React from 'react'
import { NavLink, Link } from 'react-router-dom'
import {
  LayoutDashboard,
  Layers,
  AlertTriangle,
  Activity,
  Cpu,
  History,
  ExternalLink,
} from 'lucide-react'
import { useRealtimeStore } from '../../stores/useRealtimeStore'

export const Sidebar: React.FC = () => {
  const alerts = useRealtimeStore((s) => s.alerts)
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status !== 'RESOLVED').length

  const navItems = [
    { label: 'Command Center', path: '/command-center', icon: LayoutDashboard },
    { label: '3D Digital Twin', path: '/digital-twin', icon: Layers },
    {
      label: 'Alerts & Incidents',
      path: '/alerts',
      icon: AlertTriangle,
      badge: criticalCount > 0 ? criticalCount : undefined,
    },
    { label: 'Risk Analytics', path: '/analytics', icon: Activity },
    { label: 'Equipment Explorer', path: '/equipment', icon: Cpu },
    { label: 'Historical Intelligence', path: '/history', icon: History },
  ]

  return (
    <aside className="w-60 bg-white border-r border-slate-200 flex flex-col justify-between select-none shrink-0 z-30">
      <div>
        {/* Brand Header */}
        <Link
          to="/"
          title="Return to NOVA Homepage"
          className="h-14 px-4 flex items-center gap-2.5 border-b border-slate-200 bg-slate-50/50 hover:bg-slate-100 transition-colors group cursor-pointer"
        >
          <div className="w-8 h-8 rounded-lg bg-[#1E293B] flex items-center justify-center text-white font-heading text-base shadow-none transition-transform">
            N
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-heading text-slate-900 tracking-tight text-sm">NOVA</span>
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-slate-100 text-slate-700 border border-slate-200">
                v2.4
              </span>
            </div>
            <p className="text-[10px] font-subheading tracking-wider text-slate-400 leading-none uppercase">OPERATOR INTELLIGENCE</p>
          </div>
        </Link>

        {/* Navigation Links */}
        <nav className="p-3 space-y-1">
          <div className="px-2 py-1 text-xs font-subheading uppercase tracking-wider text-slate-400 font-semibold">
            Plant Operations
          </div>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-orange-50 text-orange-900 font-bold border border-orange-200 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                  }`
                }
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span className="font-sans font-medium">{item.label}</span>
                </div>
                {item.badge !== undefined && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-red-100 text-red-700 border border-red-200 animate-pulse">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* Footer / Original Homepage Link & Plant Status */}
      <div className="p-3 border-t border-slate-200 bg-slate-50/50 space-y-2">
        <NavLink
          to="/"
          className="flex items-center justify-between px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-medium transition-colors border border-dashed border-slate-300"
        >
          <span className="font-sans">Homepage & Overview</span>
          <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
        </NavLink>

        <div className="p-2.5 rounded-xl bg-white border border-slate-200 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-mono text-[11px] font-semibold text-slate-700">Bay 1–6 Online</span>
          </div>
          <span className="text-[10px] font-mono text-slate-400">100% telemetry</span>
        </div>
      </div>
    </aside>
  )
}
