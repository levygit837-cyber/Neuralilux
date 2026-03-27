import { create } from 'zustand'
import type { Message, Conversation, TypingIndicator } from '@/types/chat'

interface ChatStore {
  conversations: Conversation[]
  messages: Record<string, Message[]>
  activeConversationId: string | null
  typingIndicators: Record<string, boolean>
  isLoadingConversations: boolean
  isLoadingMessages: boolean
  isSending: boolean
  error: string | null
  
  // Actions
  setConversations: (conversations: Conversation[]) => void
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
  reset: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  conversations: [],
  messages: {},
  activeConversationId: null,
  typingIndicators: {},
  isLoadingConversations: false,
  isLoadingMessages: false,
  isSending: false,
  error: null,

  setConversations: (conversations) => set({ conversations }),
  
  setMessages: (conversationId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [conversationId]: messages },
    })),

  addMessage: (message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [message.conversationId]: [
          ...(state.messages[message.conversationId] || []),
          message,
        ],
      },
    })),

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
    set({ activeConversationId: conversationId }),

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

  reset: () =>
    set({
      conversations: [],
      messages: {},
      activeConversationId: null,
      typingIndicators: {},
      isLoadingConversations: false,
      isLoadingMessages: false,
      isSending: false,
      error: null,
    }),
}))
