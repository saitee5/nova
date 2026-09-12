import React from 'react'
import {
  createBrowserRouter,
  RouterProvider,
  Outlet,
  useParams,
} from 'react-router-dom'
import { AppShell } from './components/shell/AppShell'
import { CommandCenterPage } from './pages/CommandCenterPage'
import { DigitalTwinPage } from './pages/DigitalTwinPage'
import { AlertsPage } from './pages/AlertsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { EquipmentPage } from './pages/EquipmentPage'
import { HistoryPage } from './pages/HistoryPage'
import RiskOverview from './pages/RiskOverview'
import { CaseStepperNav } from './components/CaseStepperNav'
import { useCaseStore } from './store/useCaseStore'
import { useSessionSocket } from './ws/useSessionSocket'
import type { PipelineStage } from './types/api'

// ── Demo Control Placeholder ─────────────────────────────────────────── //

function DemoControl() {
  return (
    <div className="p-8 text-slate-700 bg-white min-h-screen">
      <h2 className="text-xl font-bold mb-2">Demo Control Panel</h2>
      <p className="text-sm text-slate-500">Pipeline trigger suite</p>
    </div>
  )
}

// ── Stage placeholder factory ─────────────────────────────────────────── //

function StagePlaceholder({ stage }: { stage: PipelineStage }) {
  return (
    <div className="p-8 text-slate-600 text-sm">
      <span className="font-mono text-orange-600 font-semibold">{stage}</span> panel — in session
    </div>
  )
}

// ── CaseLayout ────────────────────────────────────────────────────────── //

const ORDERED_STAGES: Array<PipelineStage | 'overview'> = [
  'overview',
  'signals',
  'retrieval',
  'voice',
  'confirm',
  'audit',
  'memory',
]

function CaseLayout() {
  const { id: caseId = '' } = useParams<{ id: string }>()
  const currentStage = useCaseStore((s) => s.currentStage)

  useSessionSocket(caseId)

  const reachedStages = React.useMemo<Set<PipelineStage | 'overview'>>(() => {
    const reached = new Set<PipelineStage | 'overview'>(['overview'])
    if (currentStage === null) return reached
    for (const stage of ORDERED_STAGES) {
      reached.add(stage)
      if (stage === currentStage) break
    }
    return reached
  }, [currentStage])

  return (
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-900">
      <CaseStepperNav currentStage={currentStage} reachedStages={reachedStages} />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}

// ── Router ────────────────────────────────────────────────────────────── //

const router = createBrowserRouter([
  {
    path: '/',
    element: <RiskOverview />,
  },
  {
    path: '/overview',
    element: <RiskOverview />,
  },
  {
    element: <AppShell />,
    children: [
      { path: 'command-center', element: <CommandCenterPage /> },
      { path: 'app', element: <CommandCenterPage /> },
      { path: 'simulation', element: <CommandCenterPage /> },
      { path: 'digital-twin', element: <DigitalTwinPage /> },
      { path: 'alerts', element: <AlertsPage /> },
      { path: 'alerts/:id', element: <AlertsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'equipment', element: <EquipmentPage /> },
      { path: 'equipment/:id', element: <EquipmentPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'history/:id', element: <HistoryPage /> },
    ],
  },
  {
    path: '/twin',
    element: <DigitalTwinPage />,
  },
  {
    path: '/demo',
    element: <DemoControl />,
  },
  {
    path: '/case/:id',
    element: <CaseLayout />,
    children: [
      { path: 'signals', element: <StagePlaceholder stage="signals" /> },
      { path: 'retrieval', element: <StagePlaceholder stage="retrieval" /> },
      { path: 'voice', element: <StagePlaceholder stage="voice" /> },
      { path: 'confirm', element: <StagePlaceholder stage="confirm" /> },
      { path: 'audit', element: <StagePlaceholder stage="audit" /> },
      { path: 'memory', element: <StagePlaceholder stage="memory" /> },
    ],
  },
])

// ── ErrorBoundary ─────────────────────────────────────────────────────── //

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

class ErrorBoundary extends React.Component<
  React.PropsWithChildren,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : String(error),
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-red-600 bg-red-50 min-h-screen">
          <h1 className="text-xl font-bold mb-2">Something went wrong</h1>
          <pre className="text-sm text-slate-600">{this.state.message}</pre>
        </div>
      )
    }
    return this.props.children
  }
}

// ── App root ──────────────────────────────────────────────────────────── //

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  )
}
