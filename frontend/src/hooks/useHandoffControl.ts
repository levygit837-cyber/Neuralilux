'use client'

import { useCallback, useState } from 'react'
import { chatService, type HandoffState } from '@/services/chatService'
import { useChatStore } from '@/stores/useChatStore'

interface Call {
  /** Conversation a que o estado pertence. */
  id: string | null
  pending: boolean
  error: string | null
}

const IDLE: Call = { id: null, pending: false, error: null }

/**
 * Assumir e devolver ao Agent a Conversation aberta. O estado final vem da resposta e dos eventos realtime.
 * `pending` e `error` pertencem à Conversation em que a chamada começou: ao abrir outra, somem sem efeito
 * nenhum, e a resposta atrasada da anterior não altera o que a nova mostra.
 */
export function useHandoffControl(conversationId: string | null) {
  const [call, setCall] = useState<Call>(IDLE)

  const run = useCallback(async (id: string, action: (id: string) => Promise<HandoffState>) => {
    setCall({ id, pending: true, error: null })
    let error: string | null = null
    try {
      const state = await action(id)
      useChatStore.getState().setConversationHandoff(id, state.human_in_loop, state.assigned_to)
    } catch (e) {
      error = e instanceof Error ? e.message : 'Não foi possível atualizar o atendimento.'
    }
    // Só fecha a chamada se ela ainda é a mais recente; uma chamada nova (outra Conversation) já a substituiu.
    setCall((current) => (current.id === id ? { id, pending: false, error } : current))
  }, [])

  const take = useCallback((id: string) => run(id, chatService.takeControl), [run])
  const release = useCallback((id: string) => run(id, chatService.releaseControl), [run])

  const own = conversationId !== null && call.id === conversationId
  return { pending: own && call.pending, error: own ? call.error : null, take, release }
}
