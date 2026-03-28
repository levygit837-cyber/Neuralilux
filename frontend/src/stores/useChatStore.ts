import { create } from 'zustand'
import type { Message, Conversation, TypingIndicator, ThinkingEvent, ThinkingState } from '@/types/chat'

interface ChatStore {
  conversations: Conversation[]
  messages: Record<string, Message[]>
  activeConversationId: string | null
  typingIndicators: Record<string, boolean>
  thinkingEvents: Record<string, ThinkingEvent>
  isLoadingConversations: boolean
  isLoadingMessages: boolean
  isSending: boolean
  error: string | null
  
  // Actions
  setConversations: (conversations: Conversation[]) => void
  upsertConversation: (conversation: Conversation) => void
  setMessages: (conversationId: string, messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (tempId: string, message: Message) => void
  updateMessageStatus: (messageId: string, status: Message['status']) => void
  setActiveConversation: (conversationId: string | null) => void
  setTyping: (conversationId: string, isTyping: boolean) => void
  setLoadingConversations: (loading: boolean) => void
  setLoadingMessages: (loading: boolean) => void
  setSending: (sending: boolean) => void
  setError: (error: string | null) => void
  updateConversationLastMessage: (conversationId: string, message: string, timestamp: string) => void
  incrementUnreadCount: (conversationId: string) => void
  resetUnreadCount: (conversationId: string) => void
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

export const useChatStore = create<ChatStore>((set, get) => ({
  conversations: [],
  messages: {},
  activeConversationId: null,
  typingIndicators: {},
  thinkingEvents: {},
  thinkingClearTimers: {},
  isLoadingConversations: false,
  isLoadingMessages: false,
  isSending: false,
  error: null,

  setConversations: (conversations) => set({ conversations }),

  upsertConversation: (conversation) =>
    set((state) => {
      const existingIndex = state.conversations.findIndex((item) => item.id === conversation.id)

      if (existingIndex === -1) {
        return {
          conversations: [conversation, ...state.conversations],
        }
      }

      const nextConversations = [...state.conversations]
      nextConversations.splice(existingIndex, 1)
      return {
        conversations: [conversation, ...nextConversations],
      }
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
      const conversationMessages = state.messages[message.conversationId] || []
      return {
        messages: {
          ...state.messages,
          [message.conversationId]: conversationMessages.map((msg) =>
            msg.id === tempId ? message : msg
          ),
        },
      }
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
    set((state) => {
      if (!conversationId) {
        return { activeConversationId: null }
      }

      // Find the selected conversation and move it to the top
      const conversationIndex = state.conversations.findIndex(
        (conv) => conv.id === conversationId
      )

      if (conversationIndex <= 0) {
        // Already at top or not found, just set active
        return { activeConversationId: conversationId }
      }

      // Move selected conversation to the top
      const selectedConversation = state.conversations[conversationIndex]
      const remainingConversations = state.conversations.filter(
        (conv) => conv.id !== conversationId
      )

      return {
        activeConversationId: conversationId,
        conversations: [selectedConversation, ...remainingConversations],
      }
    }),

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

  updateConversationLastMessage: (conversationId, message, timestamp) =>
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? { ...conv, lastMessage: message, timestamp }
          : conv
      ),
    })),

  incrementUnreadCount: (conversationId) =>
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? { ...conv, unreadCount: conv.unreadCount + 1 }
          : conv
      ),
    })),

  resetUnreadCount: (conversationId) =>
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId ? { ...conv, unreadCount: 0 } : conv
      ),
    })),

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
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSending: false,
      error: null,
    })
  },
}))
