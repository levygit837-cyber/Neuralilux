import { create } from 'zustand'
import type { AgentMessage } from '@/types/agent'

interface AgentState {
  messages: AgentMessage[]
  isTyping: boolean
  isLoading: boolean
  error: string | null

  // Actions
  addMessage: (message: AgentMessage) => void
  setMessages: (messages: AgentMessage[]) => void
  setTyping: (isTyping: boolean) => void
  setLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

const initialState = {
  messages: [],
  isTyping: false,
  isLoading: false,
  error: null,
}

export const useAgentStore = create<AgentState>((set) => ({
  ...initialState,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setMessages: (messages) => set({ messages }),

  setTyping: (isTyping) => set({ isTyping }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}))