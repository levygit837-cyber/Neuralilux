'use client'

import { useSyncExternalStore } from 'react'
import { socketService, type SocketState } from '@/services/socketService'

const SERVER_STATE: SocketState = { connected: false, degraded: false }

/** Estado da conexão realtime do painel (um só socket, do `RealtimeProvider`). */
export function useSocketState(): SocketState {
  return useSyncExternalStore(socketService.subscribeState, socketService.getState, () => SERVER_STATE)
}
