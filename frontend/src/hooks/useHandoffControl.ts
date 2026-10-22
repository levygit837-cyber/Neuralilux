'use client'

import { useCallback, useState } from 'react'
import { chatService, type HandoffState } from '@/services/chatService'
import { useChatStore } from '@/stores/useChatStore'

/** Assumir e devolver ao Agent a Conversation aberta. O estado final vem da resposta e dos eventos realtime. */
export function useHandoffControl() {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (conversationId: string, action: (id: string) => Promise<HandoffState>) => {
    setPending(true)
    setError(null)
    try {
      const state = await action(conversationId)
      useChatStore.getState().setConversationHandoff(conversationId, state.human_in_loop, state.assigned_to)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível atualizar o atendimento.')
    } finally {
      setPending(false)
    }
  }, [])

  const take = useCallback((conversationId: string) => run(conversationId, chatService.takeControl), [run])
  const release = useCallback((conversationId: string) => run(conversationId, chatService.releaseControl), [run])

  return { pending, error, take, release }
}
