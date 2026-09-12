/**
 * frontend/src/services/websocket.ts
 *
 * CaseWebSocket — native WebSocket wrapper with typed message envelopes,
 * exponential-backoff auto-reconnect (max 5 retries), and status callbacks.
 *
 * No `any`. All message parsing is done through WsEnvelope discriminated union.
 */
import type { WsEnvelope, WsStatus } from '../types/api'

type MessageHandler = (msg: WsEnvelope) => void
type StatusHandler = (status: WsStatus) => void

const WS_HOST: string =
  (import.meta.env.VITE_WS_HOST as string | undefined) ??
  (typeof window !== 'undefined'
    ? `${window.location.hostname}:8000`
    : 'localhost:8000')

const MAX_RETRIES = 5
const BASE_DELAY_MS = 1_000

function isWsEnvelope(raw: unknown): raw is WsEnvelope {
  return (
    typeof raw === 'object' &&
    raw !== null &&
    'type' in raw &&
    typeof (raw as Record<string, unknown>).type === 'string'
  )
}

export class CaseWebSocket {
  private readonly sessionId: string
  private ws: WebSocket | null = null
  private messageHandlers: MessageHandler[] = []
  private statusHandlers: StatusHandler[] = []
  private retryCount = 0
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false

  constructor(sessionId: string) {
    this.sessionId = sessionId
  }

  // ── Public API ──────────────────────────────────────────────────────── //

  connect(): void {
    this.intentionalClose = false
    this._open()
  }

  disconnect(): void {
    this.intentionalClose = true
    this._clearRetryTimer()
    this.ws?.close()
    this.ws = null
  }

  onMessage(handler: MessageHandler): void {
    this.messageHandlers.push(handler)
  }

  onStatus(handler: StatusHandler): void {
    this.statusHandlers.push(handler)
  }

  // ── Internal ────────────────────────────────────────────────────────── //

  private _open(): void {
    const url = `ws://${WS_HOST}/ws/session/${this.sessionId}`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.retryCount = 0
      this._emitStatus('connected')
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(event.data) as unknown
      } catch {
        console.warn('[CaseWebSocket] non-JSON message received')
        return
      }
      if (isWsEnvelope(parsed)) {
        this.messageHandlers.forEach((h) => h(parsed as WsEnvelope))
      }
    }

    ws.onerror = () => {
      // onerror always precedes onclose — let onclose handle reconnect
    }

    ws.onclose = () => {
      if (this.intentionalClose) return
      this._scheduleReconnect()
    }
  }

  private _scheduleReconnect(): void {
    if (this.retryCount >= MAX_RETRIES) {
      this._emitStatus('disconnected')
      return
    }
    this._emitStatus('reconnecting')
    const delay = BASE_DELAY_MS * 2 ** this.retryCount
    this.retryCount += 1
    this.retryTimer = setTimeout(() => {
      this._open()
    }, delay)
  }

  private _clearRetryTimer(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer)
      this.retryTimer = null
    }
  }

  private _emitStatus(status: WsStatus): void {
    this.statusHandlers.forEach((h) => h(status))
  }
}
