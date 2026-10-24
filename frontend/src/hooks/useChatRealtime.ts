'use client'

import { useEffect, useState } from 'react'
import { socketService } from '@/services/socketService'
import { useChatStore } from '@/stores/useChatStore'

interface ChatRealtimeOptions {
  /** Sessão pronta (hidratada e logada): só então o socket conecta. */
  enabled: boolean
  instanceName: string | undefined
  /** `remote_jid` da Conversation aberta; a sala do backend usa esse nome. */
  openConversationJid: string | undefined
}

/**
 * Liga o Socket.IO do backend (autenticado pelo cookie de sessão) e entra nas salas da Instance e da
 * Conversation aberta. `{ok:false}` do backend (Instance de outro dono) vira erro visível no store.
 */
export function useChatRealtime({ enabled, instanceName, openConversationJid }: ChatRealtimeOptions) {
  const [isConnected, setIsConnected] = useState(false)
  const setError = useChatStore((state) => state.setError)

  useEffect(() => {
    return socketService.subscribe((notice) => {
      switch (notice.type) {
        case 'connection':
          setIsConnected(notice.connected)
          break
        case 'denied':
          setError(
            notice.action === 'subscribe_instance'
              ? 'Sem permissão para receber as mensagens desta instância em tempo real.'
              : 'Sem permissão para acompanhar esta conversa em tempo real.'
          )
          break
      }
    })
  }, [setError])

  useEffect(() => {
    if (!enabled) return
    socketService.connect()
    return () => socketService.disconnect()
  }, [enabled])

  useEffect(() => {
    if (!instanceName) return
    socketService.subscribeToInstance(instanceName)
    return () => socketService.leaveInstance(instanceName)
  }, [instanceName])

  useEffect(() => {
    if (!instanceName || !openConversationJid) return
    socketService.joinConversation(instanceName, openConversationJid)
    return () => socketService.leaveConversation(instanceName, openConversationJid)
  }, [instanceName, openConversationJid])

  return { isConnected }
}
