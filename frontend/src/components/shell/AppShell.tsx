import React from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { NovaCopilot } from '../copilot/NovaCopilot'
import { useRealtimeStore } from '../../stores/useRealtimeStore'
import { useGlobalWebSocket } from '../../ws/useGlobalWebSocket'
import { X, AlertTriangle } from 'lucide-react'

export const AppShell: React.FC = () => {
  useGlobalWebSocket('global-ops')
  const toastNotifications = useRealtimeStore((s) => s.toastNotifications)
  const dismissToast = useRealtimeStore((s) => s.dismissToast)

  return (
    <div className="flex h-screen w-screen bg-slate-50 text-slate-900 overflow-hidden font-sans select-none">
      {/* Dense Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* TopBar with Live Indicators & Copilot Launcher */}
        <TopBar />

        {/* Page Container */}
        <main className="flex-1 overflow-y-auto relative bg-slate-50 p-6">
          <Outlet />

          {/* Toast Notification Banner (for high/critical events) */}
          {toastNotifications.length > 0 && (
            <div className="fixed bottom-5 right-6 z-40 space-y-2 max-w-sm pointer-events-auto">
              {toastNotifications.map((t) => (
                <div
                  key={t.id}
                  className="bg-white border-l-4 border-red-500 rounded-lg p-3 shadow-xl border border-slate-200 flex items-start justify-between gap-3 animate-in slide-in-from-bottom"
                >
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-slate-900">{t.title}</h4>
                      <p className="text-xs text-slate-600 mt-0.5">{t.message}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => dismissToast(t.id)}
                    className="text-slate-400 hover:text-slate-600 p-0.5"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Global Persistent Copilot Drawer */}
      <NovaCopilot />
    </div>
  )
}

export default AppShell
