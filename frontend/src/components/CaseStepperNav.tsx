/**
 * frontend/src/components/CaseStepperNav.tsx
 *
 * Stepper navigation bar for the case detail view.
 *
 * Props (Saishree will own internals — scaffold interface only):
 *   currentStage   — active pipeline stage (from store / CaseLayout)
 *   reachedStages  — set of stages the case has already passed through
 *
 * Rules:
 *   - Active tab: highlighted with ring + font-semibold
 *   - Unreached stages: opacity-40, pointer-events-none
 *   - No store reads inside this component (prop-driven only)
 */
import type { PipelineStage } from '../types/api'

const STAGES: { key: PipelineStage | 'overview'; label: string }[] = [
  { key: 'overview',   label: 'Overview'  },
  { key: 'signals',    label: 'Signals'   },
  { key: 'retrieval',  label: 'Retrieval' },
  { key: 'voice',      label: 'Voice'     },
  { key: 'confirm',    label: 'Confirm'   },
  { key: 'audit',      label: 'Audit'     },
  { key: 'memory',     label: 'Memory'    },
]

interface CaseStepperNavProps {
  currentStage: PipelineStage | null
  reachedStages: Set<PipelineStage | 'overview'>
}

export function CaseStepperNav({
  currentStage,
  reachedStages,
}: CaseStepperNavProps) {
  return (
    <nav
      className="flex gap-1 border-b border-gray-700 px-4"
      aria-label="Case pipeline steps"
    >
      {STAGES.map(({ key, label }) => {
        const isActive = key === currentStage
        const isReached = reachedStages.has(key)
        const isDisabled = !isReached && !isActive

        return (
          <button
            key={key}
            type="button"
            disabled={isDisabled}
            aria-current={isActive ? 'step' : undefined}
            className={[
              'px-3 py-2 text-sm rounded-t-md transition-all',
              isActive
                ? 'font-semibold ring-1 ring-blue-400 text-blue-300 bg-gray-800'
                : 'text-gray-400 hover:text-gray-200',
              isDisabled ? 'opacity-40 pointer-events-none' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {label}
          </button>
        )
      })}
    </nav>
  )
}
