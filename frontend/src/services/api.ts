/**
 * frontend/src/services/api.ts
 *
 * Typed HTTP client for the VIGIL REST API.
 * Base URL: VITE_API_URL env var, falls back to http://localhost:8000.
 * No `any` — generics throughout.
 */
import type {
  AuditEntry,
  AuthResult,
  Case,
  CollectionRecords,
  DemoStatus,
  RetrievalResponse,
  VoiceStatus,
  ZoneStatus,
} from '../types/api'

const BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

// ── Core fetch helpers ───────────────────────────────────────────────────── //

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body: unknown = await res.json()
      if (
        typeof body === 'object' &&
        body !== null &&
        'detail' in body &&
        typeof (body as Record<string, unknown>).detail === 'string'
      ) {
        message = (body as Record<string, string>).detail
      }
    } catch {
      // ignore JSON parse failure — use the status text
    }
    throw new Error(message)
  }

  return res.json() as Promise<T>
}

export function apiGet<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'GET' })
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// ── Named API fetchers ───────────────────────────────────────────────────── //

export function getCases(): Promise<Case[]> {
  return apiGet<Case[]>('/api/cases')
}

export function getCase(caseId: string): Promise<Case> {
  return apiGet<Case>(`/api/cases/${caseId}`)
}

export function getCaseAudit(caseId: string): Promise<AuditEntry[]> {
  return apiGet<AuditEntry[]>(`/api/cases/${caseId}/audit`)
}

export function postAuthorize(
  caseId: string,
  decision: 'yes' | 'no',
): Promise<AuthResult> {
  return apiPost<AuthResult>(`/api/cases/${caseId}/authorize`, { decision })
}

export function getZones(): Promise<ZoneStatus[]> {
  return apiGet<ZoneStatus[]>('/api/zones')
}

export function getRetrieval(caseId: string): Promise<RetrievalResponse> {
  return apiGet<RetrievalResponse>(`/api/retrieval/${caseId}`)
}

export function getVoiceStatus(caseId: string): Promise<VoiceStatus> {
  return apiGet<VoiceStatus>(`/api/voice/${caseId}/status`)
}

export function getMemoryCollection(name: string): Promise<CollectionRecords> {
  return apiGet<CollectionRecords>(`/api/memory/collections/${name}`)
}

export async function playScenario(scenarioId: string): Promise<void> {
  await apiPost<unknown>(`/api/demo/scenarios/${scenarioId}/play`, {})
}

export async function resetScenario(scenarioId: string): Promise<void> {
  await apiPost<unknown>(`/api/demo/scenarios/${scenarioId}/reset`, {})
}

export function getDemoStatus(): Promise<DemoStatus> {
  return apiGet<DemoStatus>('/api/demo/status')
}
