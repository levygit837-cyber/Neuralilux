'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { chatService } from '@/services/chatService'
import { socketService } from '@/services/socketService'
import { selectActiveConversation, useChatStore } from '@/stores/useChatStore'
import { CONVERSATION_PAGE_SIZE, POLLING_INTERVAL } from '@/lib/constants'
import { generateTempId } from '@/lib/utils'
import type { Conversation, Message } from '@/types/chat'

const errorText = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

/** Intervalo mínimo entre duas atualizações de contadores disparadas por eventos. */
const COUNTS_THROTTLE_MS = 1000

const activityTime = (conversation: Conversation) =>
  conversation.lastMessageAt ? new Date(conversation.lastMessageAt).getTime() : 0

/**
 * Atualização silenciosa traz só a primeira página. Se o usuário já carregou mais páginas, as
 * Conversations mais antigas que a última da página nova continuam na lista.
 */
function mergeFirstPage(fresh: Conversation[], current: Conversation[]): Conversation[] {
  if (fresh.length < CONVERSATION_PAGE_SIZE || current.length <= fresh.length) return fresh
  const cutoff = activityTime(fresh[fresh.length - 1])
  const ids = new Set(fresh.map((item) => item.id))
  return [...fresh, ...current.filter((item) => !ids.has(item.id) && activityTime(item) <= cutoff)]
}

/**
 * Conversations, contadores e Messages da Instance, lidos do backend. Com o socket fora do ar, o
 * polling mantém a tela viva; com ele conectado, quem atualiza são os eventos.
 */
export function useChatData(instanceId: string | undefined, isConnected: boolean) {
  const activeConversationId = useChatStore((state) => state.activeConversationId)
  const hasConversations = useChatStore((state) => state.conversations.length > 0)
  const category = useChatStore((state) => state.category)
  const search = useChatStore((state) => state.search)
  const isSending = useChatStore((state) => state.isSending)
  const isActiveExplicit = useChatStore((state) => state.isActiveExplicit)
  const activeConversation = useChatStore(selectActiveConversation)
  const store = useChatStore.getState
  // Instance atual: uma resposta que volta depois da troca não pode sobrescrever a lista nova.
  const instanceRef = useRef(instanceId)
  // Sobe a cada carga da lista; só a mais recente grava o resultado e limpa o estado de carregando.
  const listGeneration = useRef(0)
  // Instance, filtro e busca em vigor; "Carregar mais" de uma consulta anterior é descartado.
  const queryKey = `${instanceId ?? ''}|${category}|${search}`
  const queryRef = useRef(queryKey)
  const countsGeneration = useRef(0)
  const lastCountsAt = useRef(0)
  const countsTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  // Sobe quando o histórico é importado: a Conversation aberta recarrega suas Messages.
  const [syncTick, setSyncTick] = useState(0)

  const loadConversations = useCallback(
    async (silent = false) => {
      if (!instanceId) return
      const { setLoadingConversations, setLoadingMore, setConversations, setError } = store()
      const generation = ++listGeneration.current
      const isCurrent = () => instanceRef.current === instanceId && listGeneration.current === generation
      if (!silent) {
        setLoadingConversations(true)
        setLoadingMore(false)
      }
      try {
        const page = await chatService.getConversations(instanceId, { category, search })
        if (!isCurrent()) return
        setConversations(silent ? mergeFirstPage(page.conversations, store().conversations) : page.conversations, page.total)
      } catch (error) {
        if (!silent && isCurrent()) setError(errorText(error, 'Nao foi possivel carregar as conversas'))
      } finally {
        // Quem venceu limpa o carregando, mesmo silencioso: a carga com spinner que ele substituiu não o faria.
        if (isCurrent()) setLoadingConversations(false)
      }
    },
    [instanceId, category, search, store]
  )

  /** Próxima página da lista atual (`skip` = quantas já estão carregadas). */
  const loadMoreConversations = useCallback(async () => {
    const state = store()
    if (!instanceId || state.isLoadingMore || state.conversations.length >= state.totalConversations) return
    const key = queryRef.current
    const isCurrent = () => queryRef.current === key
    state.setLoadingMore(true)
    try {
      const page = await chatService.getConversations(instanceId, {
        category,
        search,
        skip: state.conversations.length,
      })
      if (isCurrent()) store().appendConversations(page.conversations, page.total)
    } catch (error) {
      if (isCurrent()) store().setError(errorText(error, 'Nao foi possivel carregar mais conversas'))
    } finally {
      if (isCurrent()) store().setLoadingMore(false)
    }
  }, [instanceId, category, search, store])

  const loadCounts = useCallback(async () => {
    if (!instanceId) return
    const generation = ++countsGeneration.current
    lastCountsAt.current = Date.now()
    try {
      const counts = await chatService.getCounts(instanceId)
      if (instanceRef.current === instanceId && countsGeneration.current === generation) store().setCounts(counts)
    } catch {
      // Os contadores são acessório: sem eles a lista continua usável, então não há banner.
    }
  }, [instanceId, store])

  // Os eventos chegam em rajada: agrupa as atualizações em uma por intervalo.
  const refreshLatest = useRef<() => void>(() => undefined)
  useEffect(() => {
    refreshLatest.current = () => {
      void loadCounts()
      // Com filtro ou busca, a Conversation que mudou pode ter entrado ou saído da lista.
      if (category !== 'all' || search.trim()) void loadConversations(true)
    }
  }, [loadCounts, loadConversations, category, search])

  const scheduleRefresh = useCallback(() => {
    if (countsTimer.current) return
    const wait = Math.max(0, COUNTS_THROTTLE_MS - (Date.now() - lastCountsAt.current))
    countsTimer.current = setTimeout(() => {
      countsTimer.current = undefined
      refreshLatest.current()
    }, wait)
  }, [])

  useEffect(() => {
    instanceRef.current = instanceId
    return () => {
      clearTimeout(countsTimer.current)
      countsTimer.current = undefined
      // Outra Instance (ou saída da tela): nada da anterior pode continuar no store.
      store().reset()
    }
  }, [instanceId, store])

  // Filtro, busca ou Instance novos: recarrega a lista.
  useEffect(() => {
    queryRef.current = queryKey
    void loadConversations()
  }, [queryKey, loadConversations])

  useEffect(() => {
    void loadCounts()
  }, [loadCounts])

  /** A Conversation aberta está lida: zera a cópia local e avisa o servidor. */
  const markOpenRead = useCallback(
    (conversationId: string) => {
      store().resetUnreadCount(conversationId)
      chatService
        .markRead(conversationId)
        .then(scheduleRefresh)
        .catch(() => undefined)
    },
    [store, scheduleRefresh]
  )

  useEffect(
    () =>
      socketService.subscribe((notice) => {
        // Primeira mensagem de um Contact novo: o evento chega antes de a Conversation estar na lista.
        if (notice.type === 'reconnected') {
          // O que chegou durante a queda se perdeu: refaz lista, contadores e as Messages da Conversation aberta.
          void loadConversations(true)
          void loadCounts()
          setSyncTick((tick) => tick + 1)
        } else if (notice.type === 'unknown_conversation') {
          void loadConversations(true)
          scheduleRefresh()
        } else if (notice.type === 'conversation_activity') {
          // O backend soma `unread_count` mesmo na Conversation que o usuário abriu: marca de novo como lida.
          const { activeConversationId: openId, isActiveExplicit: explicit } = store()
          if (explicit && notice.conversationId === openId) markOpenRead(notice.conversationId)
          else scheduleRefresh()
        }
      }),
    [loadConversations, loadCounts, scheduleRefresh, markOpenRead, store]
  )

  useEffect(() => {
    if (isConnected) return
    const timer = setInterval(() => {
      void loadConversations(true)
      void loadCounts()
    }, POLLING_INTERVAL)
    return () => clearInterval(timer)
  }, [isConnected, loadConversations, loadCounts])

  // A Conversation aberta existe na lista (ou fixada, se o filtro a tirou); sem nenhuma, escolhe a primeira.
  useEffect(() => {
    const state = store()
    if (selectActiveConversation(state)) return
    const next = state.conversations[0]?.id ?? null
    if (next !== activeConversationId) state.autoSelectConversation(next)
  }, [hasConversations, activeConversationId, activeConversation, store])

  // Só a escolha do usuário marca como lida; a primeira da lista, aberta sozinha, não.
  useEffect(() => {
    if (!isActiveExplicit) return
    const open = selectActiveConversation(store())
    if (open && open.unreadCount > 0) markOpenRead(open.id)
  }, [activeConversationId, isActiveExplicit, markOpenRead, store])

  // Messages da Conversation aberta. Depende do id: um evento que mexe na lista não recarrega.
  useEffect(() => {
    const conversation = selectActiveConversation(store())
    if (!conversation) return
    let cancelled = false

    const load = async (silent: boolean) => {
      const { setLoadingMessages, setMessages, resetUnreadCount, setError } = store()
      if (!silent) setLoadingMessages(true)
      try {
        const messages = await chatService.getMessages(conversation)
        if (cancelled) return
        setMessages(conversation.id, messages)
        const { activeConversationId: openId, isActiveExplicit: explicit } = store()
        if (explicit && openId === conversation.id) resetUnreadCount(conversation.id)
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
  }, [activeConversationId, isConnected, syncTick, store])

  /** Importa o histórico da Evolution e recarrega lista, contadores e a Conversation aberta. */
  const syncHistory = useCallback(async () => {
    if (!instanceId || store().isSyncing) return
    const { setSyncing, setError } = store()
    setSyncing(true)
    setError(null)
    try {
      await chatService.syncHistory(instanceId)
      if (instanceRef.current !== instanceId) return
      await Promise.all([loadConversations(true), loadCounts()])
      setSyncTick((tick) => tick + 1)
    } catch (error) {
      if (instanceRef.current === instanceId) setError(errorText(error, 'Nao foi possivel sincronizar o historico'))
    } finally {
      if (instanceRef.current === instanceId) setSyncing(false)
    }
  }, [instanceId, loadConversations, loadCounts, store])

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

  return { activeConversation, sendMessage, retryMessage, syncHistory, loadMoreConversations }
}
