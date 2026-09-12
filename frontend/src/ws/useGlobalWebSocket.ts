/**
 * frontend/src/ws/useGlobalWebSocket.ts
 *
 * Global WebSocket hook for NOVA AppShell.
 * Connects to the backend WebSocket session, sets system health connection status,
 * and routes real-time telemetry/alarm/risk/episode/runtime events directly into useRealtimeStore.
 */
import { useEffect, useRef } from 'react'
import { CaseWebSocket } from '../services/websocket'
import { useRealtimeStore } from '../stores/useRealtimeStore'

export function useGlobalWebSocket(sessionId = 'global-ops'): void {
  const handleWsMessage = useRealtimeStore((s) => s.handleWsMessage)
  const socketRef = useRef<CaseWebSocket | null>(null)

  useEffect(() => {
    const socket = new CaseWebSocket(sessionId)
    socketRef.current = socket

    socket.onStatus((status) => {
      useRealtimeStore.setState((state) => ({
        systemHealth: {
          ...state.systemHealth,
          telemetryWs: status,
        },
      }))
    })

    socket.onMessage((msg) => {
      handleWsMessage(msg)
    })

    socket.connect()

    return () => {
      socket.disconnect()
      socketRef.current = null
    }
  }, [sessionId, handleWsMessage])
}
