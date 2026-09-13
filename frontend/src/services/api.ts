/**
 * frontend/src/services/api.ts
 *
 * Typed HTTP client for the NOVA / VIGIL REST API.
 * Base URL: VITE_API_URL env var, falls back to http://localhost:8000.
 * Single coherent API access layer with typed domain contracts.
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
import { toCanonicalAssetId } from '../utils/assetAliases'

import type {
  Plant,
  Unit,
  Asset,
  Sensor,
  PlantState,
  ProcessTelemetry,
  Alarm,
  MaintenanceRecord,
  Permit,
  IndustrialRiskAssessment,
  OperationalEpisode,
  CopilotQueryRequest,
  CopilotQueryResponse,
  MemorySearchRequest,
  MemorySearchResponse,
  TimeseriesPoint,
  AlarmAcknowledgeResponse,
  RiskSnapshot,
} from '../types/industrial'

import type {
  RuntimeCase,
  RuntimeResult,
  TransitionRequest,
  SelectActionRequest,
  DecisionRequest,
  ResolveRequest,
  CloseRequest,
  TimelineEvent,
  RuntimeAuditRecord,
} from '../types/runtime'

const BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

// ── Core fetch helpers ───────────────────────────────────────────────────── //

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

// ── Industrial Domain Endpoints ──────────────────────────────────────────── //

export function getPlants(): Promise<Plant[]> {
  return apiGet<Plant[]>('/api/plants')
}

export function getUnits(): Promise<Unit[]> {
  return apiGet<Unit[]>('/api/units')
}

export function getAssets(): Promise<Asset[]> {
  return apiGet<Asset[]>('/api/assets')
}

export function getSensors(): Promise<Sensor[]> {
  return apiGet<Sensor[]>('/api/sensors')
}

export function getPlantState(): Promise<PlantState> {
  return apiGet<PlantState>('/api/plant-state')
}

export function getTelemetry(assetId?: string): Promise<ProcessTelemetry[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  return apiGet<ProcessTelemetry[]>(`/api/telemetry${query}`)
}

export function getTelemetryTimeseries(
  assetId: string,
  tag?: string,
  limit = 50,
): Promise<TimeseriesPoint[]> {
  const params = new URLSearchParams({ asset_id: assetId, limit: String(limit) })
  if (tag) params.append('tag', tag)
  return apiGet<TimeseriesPoint[]>(`/api/telemetry/timeseries?${params.toString()}`)
}

export function getAlarms(assetId?: string): Promise<Alarm[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  return apiGet<Alarm[]>(`/api/alarms${query}`)
}

export function acknowledgeAlarm(
  alarmId: string,
  operator = 'lead_operator',
  notes = 'Acknowledged via NOVA Web Interface',
): Promise<AlarmAcknowledgeResponse> {
  return apiPost<AlarmAcknowledgeResponse>(`/api/alarms/${encodeURIComponent(alarmId)}/acknowledge`, {
    operator,
    notes,
  })
}

export function getMaintenance(assetId?: string): Promise<MaintenanceRecord[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  return apiGet<MaintenanceRecord[]>(`/api/maintenance${query}`)
}

export function getPermits(assetId?: string): Promise<Permit[]> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  return apiGet<Permit[]>(`/api/permits${query}`)
}

export function getOccupancy(): Promise<Record<string, number>> {
  return apiGet<Record<string, number>>('/api/occupancy')
}

export function getRisk(assetId?: string): Promise<IndustrialRiskAssessment> {
  const query = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
  return apiGet<IndustrialRiskAssessment>(`/api/risk${query}`)
}

export function getRiskHistory(assetId?: string, limit = 30): Promise<RiskSnapshot[]> {
  const canonical = assetId ? toCanonicalAssetId(assetId) : 'F-201A'
  return apiGet<RiskSnapshot[]>(`/api/risk/history?asset_id=${encodeURIComponent(canonical)}&limit=${limit}`)
}

export function getEpisodes(): Promise<OperationalEpisode[]> {
  return apiGet<OperationalEpisode[]>('/api/episodes')
}

export function getEpisode(episodeId: string): Promise<OperationalEpisode> {
  return apiGet<OperationalEpisode>(`/api/episodes/${encodeURIComponent(episodeId)}`)
}

export function queryCopilot(req: CopilotQueryRequest): Promise<CopilotQueryResponse> {
  return apiPost<CopilotQueryResponse>('/api/copilot/query', req)
}

export function searchMemory(req: MemorySearchRequest): Promise<MemorySearchResponse> {
  return apiPost<MemorySearchResponse>('/api/memory/search', req)
}

export function getAuditTrail(limit = 50): Promise<Array<Record<string, unknown>>> {
  return apiGet<Array<Record<string, unknown>>>(`/api/audit?limit=${limit}`)
}

// ── Runtime / HITL Endpoints ────────────────────────────────────────────── //

export function getRuntimeCases(state?: string): Promise<RuntimeCase[]> {
  const query = state ? `?state=${encodeURIComponent(state)}` : ''
  return apiGet<RuntimeCase[]>(`/api/runtime/cases${query}`)
}

export function getRuntimeCase(caseId: string): Promise<RuntimeResult> {
  return apiGet<RuntimeResult>(`/api/runtime/cases/${encodeURIComponent(caseId)}`)
}

export function transitionRuntimeCase(
  caseId: string,
  req: TransitionRequest,
): Promise<RuntimeCase> {
  return apiPost<RuntimeCase>(`/api/runtime/cases/${encodeURIComponent(caseId)}/transition`, req)
}

export function selectRuntimeAction(
  caseId: string,
  req: SelectActionRequest,
): Promise<RuntimeCase> {
  return apiPost<RuntimeCase>(`/api/runtime/cases/${encodeURIComponent(caseId)}/select-action`, req)
}

export function decideRuntimeCase(
  caseId: string,
  req: DecisionRequest,
): Promise<RuntimeCase> {
  return apiPost<RuntimeCase>(`/api/runtime/cases/${encodeURIComponent(caseId)}/decision`, req)
}

export function resolveRuntimeCase(
  caseId: string,
  req: ResolveRequest,
): Promise<RuntimeCase> {
  return apiPost<RuntimeCase>(`/api/runtime/cases/${encodeURIComponent(caseId)}/resolve`, req)
}

export function closeRuntimeCase(
  caseId: string,
  req: CloseRequest,
): Promise<RuntimeCase> {
  return apiPost<RuntimeCase>(`/api/runtime/cases/${encodeURIComponent(caseId)}/close`, req)
}

export function getRuntimeTimeline(caseId: string): Promise<TimelineEvent[]> {
  return apiGet<TimelineEvent[]>(`/api/runtime/cases/${encodeURIComponent(caseId)}/timeline`)
}

export function getRuntimeAudit(caseId: string): Promise<RuntimeAuditRecord[]> {
  return apiGet<RuntimeAuditRecord[]>(`/api/runtime/cases/${encodeURIComponent(caseId)}/audit`)
}

// ── Legacy / Pipeline Endpoints (Preserved for compatibility) ────────────── //

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
