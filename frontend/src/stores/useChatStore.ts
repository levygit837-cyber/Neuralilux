import { create } from 'zustand'
import type {
  ChatCounts,
  Conversation,
  ConversationCategory,
  Message,
  ThinkingEvent,
  ThinkingState,
} from '@/types/chat'
import { formatTimestamp } from '@/lib/utils'

interface ChatStore {
  conversations: Conversation[]
  messages: Record<string, Message[]>
  activeConversationId: string | null
  typingIndicators: Record<string, boolean>
  thinkingEvents: Record<string, ThinkingEvent>
  /** Filtro e busca da lista; o backend aplica os dois. */
  category: ConversationCategory
  search: string
  /** Total de Conversations do filtro no servidor; a lista pode ter só as primeiras páginas. */
  totalConversations: number
  isLoadingMore: boolean
  /** A Conversation aberta foi escolhida pelo usuário (e não pela seleção automática da primeira). */
  isActiveExplicit: boolean
  /** Null até a primeira resposta de `/conversations/counts`. */
  counts: ChatCounts | null
  /**
   * A Conversation aberta quando um filtro ou a busca a tira da lista: sem isto o chat fecharia
   * sozinho. Só existe enquanto ela estiver aberta e fora da lista.
   */
  pinnedConversation: Conversation | null
  isSyncing: boolean
  isLoadingConversations: boolean
  isLoadingMessages: boolean
  isSending: boolean
  error: string | null
  
  // Actions
  setConversations: (conversations: Conversation[], total: number) => void
  appendConversations: (conversations: Conversation[], total: number) => void
  upsertConversation: (conversation: Conversation) => void
  setMessages: (conversationId: string, messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (tempId: string, message: Message) => void
  updateMessageStatus: (messageId: string, status: Message['status']) => void
  /** Escolha do usuário: a Conversation passa a contar como lida ao ser aberta. */
  setActiveConversation: (conversationId: string | null) => void
  /** Seleção automática da primeira da lista: não conta como leitura. */
  autoSelectConversation: (conversationId: string | null) => void
  setTyping: (conversationId: string, isTyping: boolean) => void
  setLoadingConversations: (loading: boolean) => void
  setLoadingMessages: (loading: boolean) => void
  setSending: (sending: boolean) => void
  setError: (error: string | null) => void
  updateConversationLastMessage: (conversationId: string, message: string, at: Date) => void
  setConversationHandoff: (conversationId: string, humanHandoff: boolean, assignedTo?: string | null) => void
  resetUnreadCount: (conversationId: string) => void
  setCategory: (category: ConversationCategory) => void
  setSearch: (search: string) => void
  setCounts: (counts: ChatCounts) => void
  setSyncing: (syncing: boolean) => void
  setLoadingMore: (loading: boolean) => void
  // Thinking actions
  setThinkingState: (conversationId: string, state: ThinkingState, summary?: string) => void
  appendThinkingToken: (conversationId: string, token: string) => void
  collapseThinking: (conversationId: string, summary?: string) => void
  clearThinking: (conversationId: string) => void
  cancelClearTimer: (conversationId: string) => void
  reset: () => void
  // Internal timer tracking
  thinkingClearTimers: Record<string, ReturnType<typeof setTimeout> | null>
}

/** Mais recente primeiro. `timestamp` é só o texto da lista; a ordem vem de `lastMessageAt`. */
function sortConversations(conversations: Conversation[]): Conversation[] {
  const time = (conversation: Conversation) =>
    conversation.lastMessageAt ? new Date(conversation.lastMessageAt).getTime() : 0
  return [...conversations].sort((a, b) => time(b) - time(a))
}

/** A Conversation pelo UUID ou pelo `remote_jid`, na lista ou, se saiu dela por um filtro, a aberta. */
export function findConversation(state: ChatStore, ref: string | null | undefined): Conversation | undefined {
  if (!ref) return undefined
  const match = (item: Conversation) => item.id === ref || item.remoteJid === ref
  const listed = state.conversations.find(match)
  if (listed) return listed
  return state.pinnedConversation && match(state.pinnedConversation) ? state.pinnedConversation : undefined
}

export const selectActiveConversation = (state: ChatStore) => findConversation(state, state.activeConversationId)

/** A aberta que o filtro tirou da lista fica fixada; se voltou, a da lista vale. */
function pinnedAfter(state: ChatStore, conversations: Conversation[]): Conversation | null {
  const stillListed = conversations.some((item) => item.id === state.activeConversationId)
  return stillListed ? null : (selectActiveConversation(state) ?? null)
}

export const useChatStore = create<ChatStore>((set, get) => ({
  conversations: [],
  messages: {},
  activeConversationId: null,
  typingIndicators: {},
  thinkingEvents: {},
  thinkingClearTimers: {},
  category: 'all',
  search: '',
  counts: null,
  totalConversations: 0,
  isLoadingMore: false,
  isActiveExplicit: false,
  pinnedConversation: null,
  isSyncing: false,
  isLoadingConversations: false,
  isLoadingMessages: false,
  isSending: false,
  error: null,

  setConversations: (conversations, total) =>
    set((state) => ({
      conversations: sortConversations(conversations),
      totalConversations: total,
      pinnedConversation: pinnedAfter(state, conversations),
    })),

  appendConversations: (conversations, total) =>
    set((state) => {
      const known = new Set(state.conversations.map((item) => item.id))
      const merged = [...state.conversations, ...conversations.filter((item) => !known.has(item.id))]
      return {
        conversations: sortConversations(merged),
        totalConversations: total,
        pinnedConversation: pinnedAfter(state, merged),
      }
    }),

  upsertConversation: (conversation) =>
    set((state) => {
      const exists = state.conversations.some((item) => item.id === conversation.id)
      // A fixada está fora da lista filtrada de propósito: atualiza só a cópia fixada.
      if (!exists && state.pinnedConversation?.id === conversation.id) return { pinnedConversation: conversation }
      const next = exists
        ? state.conversations.map((item) => (item.id === conversation.id ? conversation : item))
        : [...state.conversations, conversation]
      return { conversations: sortConversations(next) }
    }),
  
  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [conversationId]: messages },
    })),

  addMessage: (message) =>
    set((state) => {
      const currentMessages = state.messages[message.conversationId] || []
      if (currentMessages.some((item) => item.id === message.id)) {
        return state
      }

      return {
        messages: {
          ...state.messages,
          [message.conversationId]: [...currentMessages, message],
        },
      }
    }),

  updateMessage: (tempId, message) =>
    set((state) => {
      const current = state.messages[message.conversationId] || []
      // O evento realtime da própria mensagem pode chegar antes da resposta do POST: sem isto ela duplicaria.
      const arrivedFirst = current.some((msg) => msg.id === message.id && msg.id !== tempId)
      const next = arrivedFirst
        ? current.filter((msg) => msg.id !== tempId)
        : current.map((msg) => (msg.id === tempId ? message : msg))
      return { messages: { ...state.messages, [message.conversationId]: next } }
    }),

  updateMessageStatus: (messageId, status) =>
    set((state) => {
      const newMessages = { ...state.messages }
      Object.keys(newMessages).forEach((convId) => {
        newMessages[convId] = newMessages[convId].map((msg) =>
          msg.id === messageId ? { ...msg, status } : msg
        )
      })
      return { messages: newMessages }
    }),

  setActiveConversation: (conversationId) =>
    set((state) => ({
      activeConversationId: conversationId,
      isActiveExplicit: conversationId !== null,
      pinnedConversation: state.pinnedConversation?.id === conversationId ? state.pinnedConversation : null,
    })),

  autoSelectConversation: (conversationId) =>
    set((state) => ({
      activeConversationId: conversationId,
      isActiveExplicit: false,
      pinnedConversation: state.pinnedConversation?.id === conversationId ? state.pinnedConversation : null,
    })),

  setTyping: (conversationId, isTyping) =>
    set((state) => ({
      typingIndicators: {
        ...state.typingIndicators,
        [conversationId]: isTyping,
      },
    })),

  setLoadingConversations: (loading) => set({ isLoadingConversations: loading }),
  setLoadingMessages: (loading) => set({ isLoadingMessages: loading }),
  setSending: (sending) => set({ isSending: sending }),
  setError: (error) => set({ error }),

  updateConversationLastMessage: (conversationId, message, at) =>
    set((state) => ({
      conversations: sortConversations(
        state.conversations.map((conv) =>
          conv.id === conversationId
            ? { ...conv, lastMessage: message, timestamp: formatTimestamp(at), lastMessageAt: at.toISOString() }
            : conv
        )
      ),
    })),

  setConversationHandoff: (conversationId, humanHandoff, assignedTo = null) => {
    const patch = (conv: Conversation) =>
      conv.id === conversationId
        ? { ...conv, humanHandoff, handoffAssignedTo: humanHandoff ? assignedTo : null }
        : conv
    set((state) => ({
      conversations: state.conversations.map(patch),
      pinnedConversation: state.pinnedConversation && patch(state.pinnedConversation),
    }))
  },

  resetUnreadCount: (conversationId) => {
    const patch = (conv: Conversation) => (conv.id === conversationId ? { ...conv, unreadCount: 0 } : conv)
    set((state) => ({
      conversations: state.conversations.map(patch),
      pinnedConversation: state.pinnedConversation && patch(state.pinnedConversation),
    }))
  },

  setCategory: (category) => set({ category }),
  setSearch: (search) => set({ search }),
  setCounts: (counts) => set({ counts }),
  setSyncing: (syncing) => set({ isSyncing: syncing }),
  setLoadingMore: (loading) => set({ isLoadingMore: loading }),

  setThinkingState: (conversationId, state, summary) =>
    set((prev) => ({
      thinkingEvents: {
        ...prev.thinkingEvents,
        [conversationId]: {
          conversationId,
          state,
          tokens: state === 'indicator' ? [] : (prev.thinkingEvents[conversationId]?.tokens || []),
          summary,
          startedAt: state === 'indicator' ? new Date() : prev.thinkingEvents[conversationId]?.startedAt,
        },
      },
    })),

  appendThinkingToken: (conversationId, token) =>
    set((prev) => {
      const existing = prev.thinkingEvents[conversationId]
      if (!existing || existing.state === 'idle' || existing.state === 'collapsed') return prev

      return {
        thinkingEvents: {
          ...prev.thinkingEvents,
          [conversationId]: {
            ...existing,
            state: 'streaming',
            tokens: [...(existing.tokens || []), token],
          },
        },
      }
    }),

  collapseThinking: (conversationId, summary) =>
    set((prev) => {
      const existing = prev.thinkingEvents[conversationId]
      if (!existing) return prev

      return {
        thinkingEvents: {
          ...prev.thinkingEvents,
          [conversationId]: {
            ...existing,
            state: 'collapsed',
            summary: summary || existing.summary || (existing.tokens || []).join(' ').slice(0, 120),
          },
        },
      }
    }),

  clearThinking: (conversationId) =>
    set((prev) => {
      const { [conversationId]: _, ...rest } = prev.thinkingEvents
      const { [conversationId]: __, ...timerRest } = prev.thinkingClearTimers
      return { thinkingEvents: rest, thinkingClearTimers: timerRest }
    }),

  cancelClearTimer: (conversationId) => {
    const state = get()
    const timer = state.thinkingClearTimers[conversationId]
    if (timer) {
      clearTimeout(timer)
      set((prev) => {
        const { [conversationId]: _, ...rest } = prev.thinkingClearTimers
        return { thinkingClearTimers: rest }
      })
    }
  },

  reset: () => {
    // Clear all pending timers before reset
    const state = get()
    Object.values(state.thinkingClearTimers).forEach((timer) => {
      if (timer) clearTimeout(timer)
    })
    set({
      conversations: [],
      messages: {},
      activeConversationId: null,
      typingIndicators: {},
      thinkingEvents: {},
      thinkingClearTimers: {},
      category: 'all',
      search: '',
      counts: null,
      totalConversations: 0,
      isLoadingMore: false,
      isActiveExplicit: false,
      pinnedConversation: null,
      isSyncing: false,
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSending: false,
      error: null,
    })
  },
}))
