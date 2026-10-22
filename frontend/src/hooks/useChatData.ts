'use client'

import { useCallback, useEffect } from 'react'
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

  const loadConversations = useCallback(
    async (silent = false) => {
      if (!instanceId) return
      const { setLoadingConversations, setConversations, setError } = store()
      if (!silent) setLoadingConversations(true)
      try {
        setConversations(await chatService.getConversations(instanceId))
      } catch (error) {
        if (!silent) setError(errorText(error, 'Nao foi possivel carregar as conversas'))
      } finally {
        if (!silent) setLoadingConversations(false)
      }
    },
    [instanceId, store]
  )

  useEffect(() => {
    void loadConversations()
  }, [loadConversations])

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
        if (!silent) setError(errorText(error, 'Nao foi possivel carregar as mensagens desse contato'))
      } finally {
        if (!silent && !cancelled) setLoadingMessages(false)
      }
    }

    void load(false)
    const timer = isConnected ? null : setInterval(() => void load(true), POLLING_INTERVAL)
    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
    }
  }, [activeConversationId, isConnected, store])

  const sendMessage = useCallback(
    async (content: string) => {
      if (!activeConversation || isSending) return
      const { addMessage, updateMessage, updateMessageStatus, updateConversationLastMessage, setSending, setError } = store()

      const tempId = generateTempId()
      const sentAt = new Date()
      const temp: Message = {
        id: tempId,
        conversationId: activeConversation.id,
        content,
        timestamp: sentAt,
        isOutgoing: true,
        status: 'sending',
        messageType: 'text',
      }
      addMessage(temp)
      setSending(true)
      setError(null)

      try {
        const messageId = await chatService.sendMessage(activeConversation.id, content)
        updateMessage(tempId, { ...temp, id: messageId || tempId, status: 'sent' })
        updateConversationLastMessage(activeConversation.id, content, sentAt)
      } catch (error) {
        updateMessageStatus(tempId, 'pending')
        setError(errorText(error, 'Nao foi possivel enviar a mensagem'))
      } finally {
        setSending(false)
      }
    },
    [activeConversation, isSending, store]
  )

  return { activeConversation, sendMessage }
}
