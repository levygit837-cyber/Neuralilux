'use client'

import { useEffect, useState } from 'react'
import { socketService } from '@/services/socketService'
import { useChatStore } from '@/stores/useChatStore'

interface ChatRealtimeOptions {
  token: string | null
  instanceName: string | undefined
  /** `remote_jid` da Conversation aberta; a sala do backend usa esse nome. */
  openConversationJid: string | undefined
}

/**
 * Liga o Socket.IO do backend (autenticado com o Bearer) e entra nas salas da Instance e da
 * Conversation aberta. `{ok:false}` do backend (Instance de outro dono) vira erro visível no store.
 */
export function useChatRealtime({ token, instanceName, openConversationJid }: ChatRealtimeOptions) {
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
    if (!token) return
    socketService.connect(token)
    return () => socketService.disconnect()
  }, [token])

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
