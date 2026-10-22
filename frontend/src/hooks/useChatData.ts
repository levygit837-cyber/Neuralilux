'use client'

import { useCallback, useEffect, useRef } from 'react'
import { chatService } from '@/services/chatService'
import { socketService } from '@/services/socketService'
import { useChatStore } from '@/stores/useChatStore'
import { POLLING_INTERVAL } from '@/lib/constants'
import { generateTempId } from '@/lib/utils'
import type { Message } from '@/types/chat'

const errorText = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

/**
 * Conversations e Messages da Instance, lidos do backend. Com o socket fora do ar, o polling
 * mantém a tela viva; com ele conectado, quem atualiza são os eventos.
 */
export function useChatData(instanceId: string | undefined, isConnected: boolean) {
  const conversations = useChatStore((state) => state.conversations)
  const activeConversationId = useChatStore((state) => state.activeConversationId)
  const isSending = useChatStore((state) => state.isSending)
  const store = useChatStore.getState
  const activeConversation = conversations.find((item) => item.id === activeConversationId)
  // Instance atual: uma resposta que volta depois da troca não pode sobrescrever a lista nova.
  const instanceRef = useRef(instanceId)

  const loadConversations = useCallback(
    async (silent = false) => {
      if (!instanceId) return
      const { setLoadingConversations, setConversations, setError } = store()
      const isCurrent = () => instanceRef.current === instanceId
      if (!silent) setLoadingConversations(true)
      try {
        const items = await chatService.getConversations(instanceId)
        if (isCurrent()) setConversations(items)
      } catch (error) {
        if (!silent && isCurrent()) setError(errorText(error, 'Nao foi possivel carregar as conversas'))
      } finally {
        if (!silent && isCurrent()) setLoadingConversations(false)
      }
    },
    [instanceId, store]
  )

  useEffect(() => {
    instanceRef.current = instanceId
    void loadConversations()
    // Outra Instance (ou saída da tela): nada da anterior pode continuar no store.
    return () => store().reset()
  }, [instanceId, loadConversations, store])

  // Primeira mensagem de um Contact novo: o evento chega antes de a Conversation estar na lista.
  useEffect(
    () =>
      socketService.subscribe((notice) => {
        if (notice.type === 'unknown_conversation') void loadConversations(true)
      }),
    [loadConversations]
  )

  useEffect(() => {
    if (isConnected) return
    const timer = setInterval(() => void loadConversations(true), POLLING_INTERVAL)
    return () => clearInterval(timer)
  }, [isConnected, loadConversations])

  // A Conversation aberta sempre existe na lista; sem lista, nada aberto.
  useEffect(() => {
    if (conversations.length === 0) {
      if (activeConversationId) store().setActiveConversation(null)
      return
    }
    if (!conversations.some((item) => item.id === activeConversationId)) {
      store().setActiveConversation(conversations[0].id)
    }
  }, [conversations, activeConversationId, store])

  // Messages da Conversation aberta. Depende do id: um evento que mexe na lista não recarrega.
  useEffect(() => {
    const conversation = store().conversations.find((item) => item.id === activeConversationId)
    if (!conversation) return
    let cancelled = false

    const load = async (silent: boolean) => {
      const { setLoadingMessages, setMessages, resetUnreadCount, setError } = store()
      if (!silent) setLoadingMessages(true)
      try {
        const messages = await chatService.getMessages(conversation)
        if (cancelled) return
        setMessages(conversation.id, messages)
        resetUnreadCount(conversation.id)
      } catch (error) {
        if (!silent && !cancelled) setError(errorText(error, 'Nao foi possivel carregar as mensagens desse contato'))
      } finally {
        if (!silent && !cancelled) setLoadingMessages(false)
      }
    }

    void load(false)
    const timer = isConnected ? undefined : setInterval(() => void load(true), POLLING_INTERVAL)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [activeConversationId, isConnected, store])

  /** Envia a Message já exibida na lista; se o POST falhar, ela fica `failed` para tentar de novo. */
  const deliver = useCallback(
    async (message: Message) => {
      const { updateMessage, updateMessageStatus, updateConversationLastMessage, setSending, setError } = store()
      setSending(true)
      setError(null)
      try {
        const messageId = await chatService.sendMessage(message.conversationId, message.content)
        updateMessage(message.id, { ...message, id: messageId || message.id, status: 'sent' })
        updateConversationLastMessage(message.conversationId, message.content, message.timestamp)
      } catch (error) {
        updateMessageStatus(message.id, 'failed')
        setError(errorText(error, 'Nao foi possivel enviar a mensagem'))
      } finally {
        setSending(false)
      }
    },
    [store]
  )

  const sendMessage = useCallback(
    async (content: string) => {
      if (!activeConversation || isSending) return
      const message: Message = {
        id: generateTempId(),
        conversationId: activeConversation.id,
        content,
        timestamp: new Date(),
        isOutgoing: true,
        status: 'sending',
        messageType: 'text',
      }
      store().addMessage(message)
      await deliver(message)
    },
    [activeConversation, isSending, store, deliver]
  )

  const retryMessage = useCallback(
    async (messageId: string) => {
      if (!activeConversation || isSending) return
      const failed = store().messages[activeConversation.id]?.find(
        (item) => item.id === messageId && item.status === 'failed'
      )
      if (!failed) return
      const retrying: Message = { ...failed, timestamp: new Date(), status: 'sending' }
      store().updateMessage(failed.id, retrying)
      await deliver(retrying)
    },
    [activeConversation, isSending, store, deliver]
  )

  return { activeConversation, sendMessage, retryMessage }
}
