'use client'

import { useEffect } from 'react'
import { useSocketState } from '@/hooks/useSocketState'
import { socketService } from '@/services/socketService'
import { useChatStore } from '@/stores/useChatStore'

interface ChatRealtimeOptions {
  /** UUID da Instance aberta. */
  instanceId: string | undefined
  /** UUID da Conversation aberta. */
  openConversationId: string | undefined
}

/**
 * Declara o que o chat quer receber: a sala da Instance e a da Conversation aberta. O socket é do
 * `RealtimeProvider`; aqui não se liga nem se desliga nada. `{ok:false}` do backend (Instance de outro dono)
 * vira erro visível no store.
 */
export function useChatRealtime({ instanceId, openConversationId }: ChatRealtimeOptions) {
  const { connected: isConnected } = useSocketState()
  const setError = useChatStore((state) => state.setError)

  useEffect(() => {
    return socketService.subscribe((notice) => {
      if (notice.type !== 'denied') return
      setError(
        notice.action === 'subscribe_instance'
          ? 'Sem permissão para receber as mensagens desta instância em tempo real.'
          : 'Sem permissão para acompanhar esta conversa em tempo real.'
      )
    })
  }, [setError])

  useEffect(() => {
    if (!instanceId) return
    socketService.subscribeToInstance(instanceId)
    return () => socketService.leaveInstance(instanceId)
  }, [instanceId])

  useEffect(() => {
    if (!instanceId || !openConversationId) return
    socketService.joinConversation(instanceId, openConversationId)
    return () => socketService.leaveConversation(instanceId, openConversationId)
  }, [instanceId, openConversationId])

  return { isConnected }
}
