'use client'

import { useEffect } from 'react'
import { useSessionReady } from '@/hooks/useSessionReady'
import { useSocketState } from '@/hooks/useSocketState'
import { socketService } from '@/services/socketService'

/**
 * Dono do socket do painel. Liga com a sessão pronta e desliga quando ela acaba ou o layout `(app)` sai da
 * tela; nenhuma tela chama `connect`/`disconnect`. Avisa quando o tempo real caiu: o Socket.IO continua
 * tentando sozinho, sem limite de tentativas.
 */
export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const sessionReady = useSessionReady()
  const { degraded } = useSocketState()

  useEffect(() => {
    if (!sessionReady) return
    socketService.connect()
    return () => socketService.disconnect()
  }, [sessionReady])

  return (
    <>
      {children}
      {sessionReady && degraded && (
        <div
          role="status"
          className="fixed bottom-4 right-4 z-50 rounded-lg border border-brand-border bg-brand-card/90 px-4 py-2 text-sm text-content-muted backdrop-blur-sm"
        >
          <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-status-warning" />
          Sem conexão em tempo real. Tentando reconectar...
        </div>
      )}
    </>
  )
}
