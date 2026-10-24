'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { instanceService, type InstanceStatus } from '@/services/instanceService'
import { socketService } from '@/services/socketService'
import { useSessionReady } from '@/hooks/useSessionReady'

const STATUS_POLL_MS = 3000
const QR_REFRESH_MS = 20000

const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

/**
 * Estado de conexão e QR code de uma Instance. O QR vem de `POST /instances/{name}/connect` e o
 * estado de `GET /instances/{name}/status`; `qr_code_update` e `connection_status_update` do
 * Socket.IO adiantam os dois. O polling cobre o socket fora do ar. O socket é do `RealtimeProvider`: aqui só se
 * entra e sai da sala da Instance (`instanceId`), sem ligar nem desligar a conexão.
 */
export function useInstanceConnection(instanceName: string | undefined, instanceId: string | undefined) {
  const queryClient = useQueryClient()
  const sessionReady = useSessionReady()
  const [status, setStatus] = useState<InstanceStatus>('disconnected')
  const [qrCode, setQrCode] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isWatching, setIsWatching] = useState(false)
  const statusRef = useRef(status)

  // Instances em cache (Configurações, Instâncias, Instance ativa) mostram o status daqui: mudou, refaz.
  const invalidateInstances = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.instances }),
    [queryClient]
  )

  const applyStatus = useCallback(
    (next: InstanceStatus) => {
      const changed = statusRef.current !== next
      statusRef.current = next
      setStatus(next)
      if (next === 'connected') {
        setQrCode(null)
        setIsWatching(false)
      }
      if (changed) void invalidateInstances()
    },
    [invalidateInstances]
  )

  const requestQr = useCallback(async () => {
    if (!instanceName) return
    const result = await instanceService.connect(instanceName)
    applyStatus(result.status === 'connected' ? 'connected' : 'connecting')
    if (result.qrCode) setQrCode(result.qrCode)
  }, [instanceName, applyStatus])

  const connect = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      await requestQr()
      setIsWatching(true)
    } catch (e) {
      setError(messageOf(e, 'Erro ao conectar.'))
    } finally {
      setIsLoading(false)
    }
  }, [requestQr])

  const disconnect = useCallback(async () => {
    if (!instanceName) return
    setIsLoading(true)
    setError(null)
    try {
      await instanceService.logout(instanceName)
      applyStatus('disconnected')
      // O logout muda o estado no backend mesmo que o status local já fosse 'disconnected'.
      void invalidateInstances()
      setQrCode(null)
      setIsWatching(false)
    } catch (e) {
      setError(messageOf(e, 'Erro ao desconectar.'))
    } finally {
      setIsLoading(false)
    }
  }, [instanceName, applyStatus, invalidateInstances])

  // Ao abrir: lê o estado; se não está conectada, já pede o QR.
  useEffect(() => {
    if (!instanceName) return
    let cancelled = false

    const init = async () => {
      try {
        const current = await instanceService.getStatus(instanceName)
        if (cancelled) return
        applyStatus(current)
        if (current !== 'connected') {
          await requestQr()
          if (!cancelled) setIsWatching(true)
        }
      } catch (e) {
        if (!cancelled) setError(messageOf(e, 'Erro ao consultar a instância.'))
      }
    }

    void init()
    return () => {
      cancelled = true
    }
  }, [instanceName, applyStatus, requestQr])

  // Eventos do nosso Socket.IO.
  useEffect(() => {
    if (!instanceId || !sessionReady) return
    socketService.subscribeToInstance(instanceId)

    const unsubscribe = socketService.subscribe((notice) => {
      if (notice.type === 'qr_code') {
        setError(null)
        setQrCode(notice.qrCode)
        applyStatus('connecting')
      } else if (notice.type === 'instance_status') {
        setError(null)
        applyStatus(notice.status)
      } else if (notice.type === 'denied' && notice.action === 'subscribe_instance') {
        setError('Sem permissão para acompanhar esta instância em tempo real.')
      }
    })

    return () => {
      unsubscribe()
      socketService.leaveInstance(instanceId)
    }
  }, [instanceId, sessionReady, applyStatus])

  // Enquanto espera a leitura do QR: confere o estado e renova o QR que expirou.
  useEffect(() => {
    if (!instanceName || !isWatching) return

    const poll = setInterval(() => {
      instanceService
        .getStatus(instanceName)
        .then(applyStatus)
        .catch(() => undefined)
    }, STATUS_POLL_MS)
    const refresh = setInterval(() => {
      if (statusRef.current !== 'connected') requestQr().catch(() => undefined)
    }, QR_REFRESH_MS)

    return () => {
      clearInterval(poll)
      clearInterval(refresh)
    }
  }, [instanceName, isWatching, applyStatus, requestQr])

  return { status, qrCode, isLoading, error, connect, disconnect }
}
